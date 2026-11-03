import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from evosprig.core.journal import Scope
from evosprig.core.protocols import ExecutionError, ToolRejectedError
from evosprig.plugins.repository_tools import (
    RepositoryToolConfig,
    RepositoryWorkspace,
    repository_tool,
)


@pytest.fixture
def store(tmp_path, monkeypatch):
    repo = tmp_path / "source"
    repo.mkdir()
    def git(*args):
        subprocess.run(["git", "-c", "safe.directory=" + str(repo), "-c", "user.name=Test", "-c", "user.email=test@example.com", *args],
                       cwd=repo, check=True, capture_output=True)
    git("init")
    (repo / "app.py").write_text("def add(a, b):\n    return a - b\n")
    (repo / "test_app.py").write_text("from app import add\nassert add(2, 3) == 5\n")
    git("add", ".")
    git("commit", "-m", "Initial")
    monkeypatch.setenv("TEST_REPOSITORY", str(repo))
    monkeypatch.setenv("SECRET_API_TOKEN", "do-not-forward")
    config = RepositoryToolConfig(name="repo.open", operation="open", repository_env="TEST_REPOSITORY",
        editable_paths=["app.py", "src/"], checks={"unit": [sys.executable, "test_app.py"]})
    return RepositoryWorkspace(config, tmp_path / "state", Scope("repo-app"))


def test_worktree_edit_check_diff_and_replay_preserve_source(store):
    first = store.open(idempotency_key="task-1")
    assert store.open(idempotency_key="task-1") == first
    workspace = first["workspace"]
    assert not store.check(workspace, "unit", idempotency_key="before")["passed"]
    original = store.read(workspace, "app.py")
    fixed = "def add(a, b):\n    return a + b\n"
    saved = store.write(workspace, "app.py", fixed, original["sha256"], idempotency_key="edit")
    assert store.write(workspace, "app.py", fixed, original["sha256"], idempotency_key="edit") == saved
    after = store.check(workspace, "unit", idempotency_key="after")
    assert after["passed"] and not after["modified_by_check"]
    patch = store.diff(workspace)
    assert after["patch_sha256"] == patch["sha256"] and "+    return a + b" in patch["patch"]
    assert (store.repository / "app.py").read_text() == original["content"]
    restarted = RepositoryWorkspace(store.config, store.root.parent, Scope("repo-app"))
    assert restarted.check(workspace, "unit", idempotency_key="after") == after
    another = store.open(idempotency_key="task-2")["workspace"]
    assert store.read(another, "app.py") == original
    with pytest.raises(ToolRejectedError, match="current file"):
        store.write(workspace, "app.py", "stale", original["sha256"], idempotency_key="stale")
    with pytest.raises(ExecutionError, match="different content"):
        store.write(workspace, "app.py", "changed", original["sha256"], idempotency_key="edit")


def test_paths_scope_and_deployment_limits(store):
    workspace = store.open(idempotency_key="task")["workspace"]
    for path in ["../secret", "/etc/passwd", ".git/config", "src/../../escape"]:
        with pytest.raises(ToolRejectedError):
            store.read(workspace, path)
    with pytest.raises(ToolRejectedError, match="editable"):
        store.write(workspace, "test_app.py", "pass", None, idempotency_key="test-edit")
    os.symlink(store.repository, store.path(workspace) / "linked")
    with pytest.raises(ToolRejectedError, match="Symbolic"):
        store.read(workspace, "linked/app.py")
    other = RepositoryWorkspace(store.config, store.root.parent, Scope("repo-app", tenant="another"))
    with pytest.raises(ToolRejectedError):
        other.read(workspace, "app.py")
    with pytest.raises(ToolRejectedError, match="configured check"):
        store.check(workspace, "arbitrary shell", idempotency_key="bad")


def test_new_file_patch_crash_receipt_and_bounded_test_process(store):
    workspace = store.open(idempotency_key="task")["workspace"]
    store.write(workspace, "src/new.py", "print('new')\n", None, idempotency_key="new")
    assert "src/new.py" in store.list(workspace)["files"]
    assert "+print('new')" in store.diff(workspace)["patch"]
    store.config.checks["environment"] = [sys.executable, "-c", "import os; print(os.getenv('SECRET_API_TOKEN', 'absent'))"]
    assert store.check(workspace, "environment", idempotency_key="env")["output"].strip() == "absent"
    store.config.timeout_seconds = 0.2
    store.config.checks["timeout"] = [sys.executable, "-c", "import time; time.sleep(30)"]
    assert store.check(workspace, "timeout", idempotency_key="timeout")["timed_out"]
    # An interrupted check is not silently executed a second time.
    receipt = next(path for path in store.root.glob("*.check.json") if json.loads(path.read_text())["output"]["check"] == "timeout")
    body = json.loads(receipt.read_text())
    body["status"] = "running"
    receipt.write_text(json.dumps(body))
    with pytest.raises(ExecutionError, match="interrupted"):
        store.check(workspace, "timeout", idempotency_key="timeout")


async def test_repository_bindings_use_runtime_tool_contract(store):
    config = store.config.model_copy(update={"operation": "open"})
    tool = repository_tool(config, store.root.parent, Scope("repo-app"))
    result = await tool.invoke({}, operation_id="native-open")
    assert result["status"] == "ready" and tool.side_effect == "write" and tool.idempotent


def test_missing_git_fails_while_configuring_tools(store, monkeypatch):
    monkeypatch.setenv("PATH", "")
    with pytest.raises(ValueError, match="require Git"):
        RepositoryWorkspace(store.config, store.root.parent, Scope("repo-app"))


async def test_repository_application_repairs_failed_check_and_resumes_review(store, tmp_path):
    import yaml

    from evosprig.config import make_tools
    from evosprig.core.protocols import ModelResponse, ToolCall
    from evosprig.core.runtime import Runtime
    from evosprig.core.spec import load_spec
    from evosprig.core.version import compile_agent
    from evosprig.plugins.mock import MockProvider
    from evosprig.plugins.sqlite_journal import SQLiteJournal

    class Engineer(MockProvider):
        attempts = 0

        async def complete(self, request):
            self.requests.append(request)
            system = request.messages[0]["content"]
            inputs = json.loads(request.messages[1]["content"])
            if "You coordinate" in system:
                result = {"plan": "Correct addition while preserving the two-argument function."}
            elif "You review" in system:
                result = {"accepted": inputs["checks"]["passed"], "feedback": "Check addition."}
            else:
                tools = [message for message in request.messages if message["role"] == "tool"]
                if not tools:
                    self.attempts += 1
                    if self.attempts == 1:
                        return ModelResponse(text=json.dumps({"summary": "Inspect the reported failure."}))
                    return ModelResponse(tool_calls=(ToolCall("read", "read", {"workspace": inputs["workspace"], "path": "app.py"}),))
                if len(tools) == 1:
                    read = json.loads(tools[0]["content"])
                    return ModelResponse(tool_calls=(ToolCall("edit", "write", {
                        "workspace": inputs["workspace"], "path": "app.py", "expected_sha256": read["sha256"],
                        "content": "def add(a, b):\n    return a + b\n"}),))
                result = {"summary": "Corrected addition."}
            return ModelResponse(text=json.dumps(result))

    root = Path(__file__).parents[1] / "examples/repository-agent"
    version = compile_agent(load_spec(root / "agent.yaml"), root)
    scope = Scope(version.spec.id)
    profile = tmp_path / "profile.yaml"
    profile.write_text(yaml.safe_dump({"tools": {"repository." + name: store.config.model_copy(update={
        "name": "repository." + name, "operation": name}).model_dump(mode="json")
        for name in ["open", "list", "read", "write", "diff", "check"]}}))
    model = Engineer()
    journal = SQLiteJournal(tmp_path / "runs.sqlite")
    def runtime():
        return Runtime({"main": model}, make_tools(tmp_path, scope, profile=profile), journal=journal, allow_writes=True)
    event = {"source": "repository:test", "event_id": "issue-1", "payload": {"body": "Fix addition"}}
    run_id = runtime().create_event_run(version, {"request": "Fix addition", "check": "unit"}, event)
    result = await runtime().resume(run_id)
    assert result.status == "waiting_input", result.error
    proposal = result.waiting[0]["input"]["proposal"]
    assert model.attempts == 2 and proposal["accepted"] and proposal["checks"]["passed"]
    assert "+    return a + b" in proposal["patch"]["patch"]
    assert (store.repository / "app.py").read_text() == "def add(a, b):\n    return a - b\n"
    count = len(model.requests)
    journal.respond(run_id, result.waiting[0]["path"], {"decision": "approve", "comment": "Reviewed"})
    done = await runtime().resume(run_id)
    assert done.status == "succeeded", done.error
    assert done.output["proposal"] == proposal and len(model.requests) == count
    assert runtime().create_event_run(version, {"request": "Changed mapping", "check": "unit"}, event) == run_id


def test_repository_application_exports_with_environment_bound_checkout(tmp_path):
    import runpy

    from evosprig.config import make_models
    from evosprig.core.spec import load_spec
    from evosprig.core.version import compile_agent
    from evosprig.exporters.python import export_python

    root = Path(__file__).parents[1] / "examples/repository-agent"
    configure = runpy.run_path(str(root / "configure.py"))["profile"]
    deployment = configure(command=["python", "-m", "pytest", "-q"], editable_paths=["src/"])
    version = compile_agent(load_spec(root / "agent.yaml"), root)
    target = tmp_path / "export"
    export_python(version, target, tool_bindings=deployment["tools"])
    assert (target / "src/evosprig/plugins/repository_tools.py").is_file()
    bindings = json.loads((target / "tool-bindings.json").read_text())
    assert bindings["repository.write"]["repository_env"] == "AGENT_REPOSITORY"
    assert bindings["repository.write"]["editable_paths"] == ["src/"]
    import yaml
    profile = tmp_path / "profile.yaml"
    profile.write_text(yaml.safe_dump(deployment))
    assert make_models(version.spec, profile)["main"].connection.json_mode == "without_tools"
