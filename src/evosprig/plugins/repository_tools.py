"""Deployment-bound Git worktrees, revision-checked edits and named checks."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import tempfile
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Literal

from pydantic import Field

from evosprig.core.protocols import ExecutionError, Tool, ToolRejectedError
from evosprig.core.spec import Contract, canonical_json, digest


class RepositoryToolConfig(Contract):
    kind: Literal["repository"] = "repository"
    name: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_.-]{0,127}$")
    operation: Literal["open", "list", "read", "write", "diff", "check"]
    repository_env: str = Field(pattern=r"^[A-Za-z_][A-Za-z0-9_]*$")
    base: str = Field(default="HEAD", pattern=r"^[A-Za-z0-9][A-Za-z0-9_./-]*$")
    checks: dict[str, list[str]] = Field(default_factory=dict)
    editable_paths: list[str] = Field(default_factory=list)
    timeout_seconds: float = Field(default=120, gt=0, le=1800)
    max_file_bytes: int = Field(default=200_000, ge=1, le=1_000_000)
    max_output_bytes: int = Field(default=60_000, ge=1024, le=1_000_000)


def atomic_json(path, data):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(canonical_json(data), encoding="utf-8")
    os.replace(temporary, path)


class RepositoryWorkspace:
    def __init__(self, config, state, scope):
        self.config = config
        self.git_executable = shutil.which("git")
        if not self.git_executable:
            raise ValueError("Repository tools require Git on the worker's PATH")
        source = os.environ.get(config.repository_env)
        if not source or not Path(source).is_dir():
            raise ValueError("Configure repository_env with an existing local Git repository")
        self.repository = Path(source).resolve()
        self.root = Path(state) / digest([scope.key, str(self.repository)])
        self.root.mkdir(parents=True, exist_ok=True)

    def command(self, argv, cwd):
        # Test children receive a small environment; model and deployment secrets
        # are not inherited. Run the worker in a container for untrusted code.
        environment = {key: os.environ[key] for key in ("PATH", "SYSTEMROOT", "LD_LIBRARY_PATH") if key in os.environ}
        environment.update(GIT_TERMINAL_PROMPT="0", GIT_CONFIG_NOSYSTEM="1",
                           GIT_CONFIG_GLOBAL=os.devnull, PYTHONDONTWRITEBYTECODE="1")
        process = subprocess.Popen(argv, cwd=cwd, env=environment, stdin=subprocess.DEVNULL,
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT, start_new_session=True)
        data = bytearray()
        def drain():
            with process.stdout:
                while block := process.stdout.read(65536):
                    remaining = self.config.max_output_bytes + 1 - len(data)
                    if remaining > 0:
                        data.extend(block[:remaining])
        reader = threading.Thread(target=drain, daemon=True)
        reader.start()
        timed_out = False
        try:
            process.wait(timeout=self.config.timeout_seconds)
        except subprocess.TimeoutExpired:
            timed_out = True
        finally:
            # Also reap background children left by an exited check process.
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait()
            reader.join(timeout=5)
        if reader.is_alive():
            raise ExecutionError("A check child kept its output stream open after termination")
        return {"exit_code": process.returncode, "timed_out": timed_out,
                "output": data[:self.config.max_output_bytes].decode("utf-8", errors="replace"),
                "truncated": len(data) > self.config.max_output_bytes}

    def git(self, *args, cwd=None, success=True):
        directory = cwd or self.repository
        result = self.command([self.git_executable, "-c", "core.hooksPath=" + os.devnull,
                               "-c", "safe.directory=" + str(directory), *args], directory)
        if success and (result["exit_code"] or result["timed_out"] or result["truncated"]):
            raise ExecutionError("Git operation failed: " + result["output"][:2000])
        return result

    @contextmanager
    def locked(self, workspace):
        if not re.fullmatch(r"[0-9a-f]{64}", workspace):
            raise ToolRejectedError("workspace", "Use the workspace ID returned by repository.open")
        with (self.root / (workspace + ".lock")).open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            yield

    def path(self, workspace):
        metadata = self.root / (workspace + ".json")
        if not re.fullmatch(r"[0-9a-f]{64}", workspace) or not metadata.is_file():
            raise ToolRejectedError("workspace", "Workspace does not exist in this project scope")
        record = json.loads(metadata.read_text())
        if record.get("status") != "ready":
            raise ExecutionError("Workspace creation needs reconciliation")
        return self.root / workspace

    def file(self, workspace, path, *, writing=False):
        base = self.path(workspace)
        parts = Path(path).parts
        if not parts or Path(path).is_absolute() or any(part in {"..", ".git"} for part in parts):
            raise ToolRejectedError("path", "Use a file path inside the worktree")
        target = base
        for part in parts:
            target = target / part
            if target.is_symlink():
                raise ToolRejectedError("path", "Symbolic links cannot be accessed through repository tools")
        if not target.resolve().is_relative_to(base.resolve()):
            raise ToolRejectedError("path", "File must stay inside the worktree")
        if writing and self.config.editable_paths and not any(
            path == entry or entry.endswith("/") and path.startswith(entry)
            for entry in self.config.editable_paths
        ):
            raise ToolRejectedError("path", "This file is outside the configured editable paths")
        return target

    def open(self, *, idempotency_key):
        workspace = digest(["worktree", idempotency_key])
        with self.locked(workspace):
            metadata = self.root / (workspace + ".json")
            directory = self.root / workspace
            if metadata.exists():
                record = json.loads(metadata.read_text())
            else:
                commit = self.git("rev-parse", "--verify", self.config.base + "^{commit}")["output"].strip()
                record = {"workspace": workspace, "base_commit": commit, "status": "creating"}
                atomic_json(metadata, record)
            if not directory.exists():
                self.git("worktree", "add", "--detach", str(directory), record["base_commit"])
            actual = self.git("rev-parse", "HEAD", cwd=directory)["output"].strip()
            if actual != record["base_commit"]:
                raise ExecutionError("Workspace HEAD changed; reconcile the worktree before resuming")
            record["status"] = "ready"
            atomic_json(metadata, record)
            return record

    def list(self, workspace):
        result = self.git("ls-files", "-co", "--exclude-standard", "-z", cwd=self.path(workspace))
        return {"files": sorted(set(result["output"].rstrip("\0").split("\0"))) if result["output"] else []}

    def read(self, workspace, path):
        target = self.file(workspace, path)
        if not target.exists():
            return {"path": path, "exists": False, "sha256": None, "content": ""}
        if not target.is_file() or target.stat().st_size > self.config.max_file_bytes:
            raise ToolRejectedError("file_size", "Select a UTF-8 file within the configured size limit")
        data = target.read_bytes()
        return {"path": path, "exists": True, "sha256": hashlib.sha256(data).hexdigest(), "content": data.decode("utf-8")}

    def write(self, workspace, path, content, expected_sha256, *, idempotency_key):
        data = content.encode("utf-8")
        if len(data) > self.config.max_file_bytes:
            raise ToolRejectedError("file_size", "Edit exceeds the configured file size limit")
        intent = digest([path, content, expected_sha256])
        receipt = self.root / (digest([workspace, idempotency_key]) + ".edit.json")
        with self.locked(workspace):
            target = self.file(workspace, path, writing=True)
            new_hash = hashlib.sha256(data).hexdigest()
            current = self.read(workspace, path)["sha256"]
            if receipt.exists():
                saved = json.loads(receipt.read_text())
                if saved["intent"] != intent:
                    raise ExecutionError("Edit operation ID was reused for different content")
                if saved["status"] == "done":
                    return saved["output"]
                if current not in {expected_sha256, new_hash}:
                    raise ExecutionError("Interrupted edit conflicts with a later change; reconcile the file")
            else:
                if current != expected_sha256:
                    raise ToolRejectedError("revision_conflict", "Read the current file before editing it")
                atomic_json(receipt, {"intent": intent, "status": "writing"})
            if current != new_hash:
                target.parent.mkdir(parents=True, exist_ok=True)
                with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as stream:
                    temporary = Path(stream.name)
                    try:
                        stream.write(data)
                        stream.flush()
                        if target.exists():
                            os.chmod(temporary, target.stat().st_mode & 0o777)
                        os.replace(temporary, target)
                    finally:
                        temporary.unlink(missing_ok=True)
            output = {"path": path, "sha256": new_hash}
            atomic_json(receipt, {"intent": intent, "status": "done", "output": output})
            return output

    def diff(self, workspace):
        cwd = self.path(workspace)
        result = self.git("diff", "--no-ext-diff", "--no-textconv", "--binary", "HEAD", cwd=cwd)
        parts = [result["output"]]
        untracked = self.git("ls-files", "--others", "--exclude-standard", "-z", cwd=cwd)["output"]
        for path in filter(None, untracked.split("\0")):
            self.file(workspace, path)
            patch = self.git("diff", "--no-ext-diff", "--no-textconv", "--no-index", "--binary", "--", os.devnull, path,
                             cwd=cwd, success=False)
            if patch["exit_code"] not in {0, 1} or patch["timed_out"] or patch["truncated"]:
                raise ExecutionError("Could not collect the new-file patch")
            parts.append(patch["output"])
        patch = "".join(parts)
        if len(patch.encode()) > self.config.max_output_bytes:
            raise ToolRejectedError("patch_size", "Patch exceeds the configured output limit")
        return {"patch": patch, "sha256": hashlib.sha256(patch.encode()).hexdigest()}

    def check(self, workspace, check, *, idempotency_key):
        argv = self.config.checks.get(check)
        if not argv or not all(isinstance(arg, str) and arg for arg in argv):
            raise ToolRejectedError("check", "Choose a configured check: " + ", ".join(self.config.checks))
        receipt = self.root / (digest([workspace, idempotency_key]) + ".check.json")
        intent = digest([check, argv])
        with self.locked(workspace):
            cwd = self.path(workspace)
            if receipt.exists():
                saved = json.loads(receipt.read_text())
                if saved["intent"] != intent:
                    raise ExecutionError("Check operation ID was reused for another command")
                if saved["status"] != "done":
                    raise ExecutionError("Check was interrupted; inspect its effects before retrying")
                return saved["output"]
            atomic_json(receipt, {"status": "running", "intent": intent})
            before = self.diff(workspace)["sha256"]
            result = self.command(argv, cwd)
            after = self.diff(workspace)["sha256"]
            result.update(check=check, passed=result["exit_code"] == 0 and not result["timed_out"] and before == after,
                          patch_sha256=before, modified_by_check=before != after)
            atomic_json(receipt, {"status": "done", "intent": intent, "output": result})
            return result


def repository_tool(config, state, scope):
    store = RepositoryWorkspace(config, state, scope)
    text = {"type": "string", "minLength": 1}
    fields = {} if config.operation == "open" else {"workspace": text}
    if config.operation in {"read", "write"}:
        fields["path"] = text
    if config.operation == "write":
        fields.update(content={"type": "string"}, expected_sha256={"type": ["string", "null"]})
    if config.operation == "check":
        fields["check"] = {"enum": list(config.checks)}
        if not config.checks:
            raise ValueError("A check tool requires at least one named command")
    writes = config.operation in {"open", "write", "check"}
    return Tool(config.name, "Repository " + config.operation + " in a managed worktree.",
                {"type": "object", "properties": fields, "required": list(fields), "additionalProperties": False},
                {"type": "object"}, getattr(store, config.operation),
                side_effect="write" if writes else "read_only", idempotent=writes,
                timeout_seconds=config.timeout_seconds + 30)
