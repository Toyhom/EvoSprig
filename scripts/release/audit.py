"""Audit source and built archives against the product release allowlist."""

import argparse
import json
import re
import subprocess
import tarfile
import zipfile
from pathlib import Path

ROOT_FILES = {
    "README.md",
    "LICENSE",
    "NOTICE",
    "CHANGELOG.md",
    "CONTRIBUTING.md",
    "SECURITY.md",
    "pyproject.toml",
    ".gitignore",
    ".dockerignore",
    "requirements-runtime.lock",
    "requirements-dev.lock",
    "README.zh-CN.md",
}
ROOT_DIRS = {"src", "docs", "examples", "tests", "spec", "scripts", "apps", ".github"}
HISTORICAL_ROOT_FILES = {"THIRD_PARTY_NOTICES.md"}
SKIP = {
    ".git",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    "dist",
    "build",
    "test-results",
    "playwright-report",
}
SECRET = re.compile(
    rb"\b(?:sk-[A-Za-z0-9_-]{16,}|gh[pousr]_[A-Za-z0-9]{20,}|"
    rb"github_pat_[A-Za-z0-9_]{20,}|AKIA[A-Z0-9]{16})|"
    rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|"
    rb"https?://[^\s/@:]+:[^\s/@]+@"
)
PRIVATE_PATH = re.compile(rb"/(?:data/L[0-9]+|aoss[0-9]+|home/[^\s/]+/|root/)")
PRIVATE_URL = re.compile(
    rb"https?://(?:10\.\d+\.\d+\.\d+|192\.168\.\d+\.\d+|"
    rb"172\.(?:1[6-9]|2\d|3[01])\.\d+\.\d+)"
)


def check(name: str, data: bytes):
    parts = Path(name).parts
    if Path(name).is_absolute() or ".." in parts:
        raise ValueError(f"unsafe path: {name}")
    if (
        any(part in {"project-private", "local-data", "AGENTS.md"} for part in parts)
        or "AGENT_PLATFORM_META" in name
    ):
        raise ValueError(f"internal material: {name}")
    if any(part.startswith(".env") and part != ".env.example" for part in parts):
        raise ValueError(f"private environment file: {name}")
    if name.endswith((".sqlite", ".sqlite3", ".sqlite-wal", ".sqlite-shm", ".db", ".pyc", ".log")):
        raise ValueError(f"runtime artifact: {name}")
    # Reviewed synthetic rejection fixtures exist in the original public history.
    # Keep the exception exact and file-scoped; never exempt an entire test directory.
    fixture_name = name
    if len(parts) > 1 and re.fullmatch(r"evosprig-[0-9][A-Za-z0-9_.+-]*", parts[0]):
        fixture_name = Path(*parts[1:]).as_posix()
    if fixture_name == "tests/test_http_tools.py":
        data = data.replace(b"https://" + b"user:secret@example.org", b"https://example.org")
    if fixture_name == "tests/test_models.py":
        data = data.replace(b"https://" + b"secret:pass@example.com", b"https://example.com")
    if SECRET.search(data):
        raise ValueError(f"credential-like content: {name}")
    if PRIVATE_PATH.search(data) or PRIVATE_URL.search(data):
        raise ValueError(f"private deployment reference: {name}")


def audit_git_history(root: Path):
    """Scan every reachable committed tree, including files deleted from HEAD."""
    git = ["git", "-c", f"safe.directory={root.resolve()}", "-C", str(root)]

    def read(*args):
        return subprocess.check_output([*git, *args])

    commits = read("rev-list", "--all").decode().splitlines()
    seen = set()
    # One Git reader avoids spawning a process for every historical file.
    with subprocess.Popen([*git, "cat-file", "--batch"], stdin=subprocess.PIPE,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE) as objects:
        def blob(oid):
            objects.stdin.write(oid + b"\n")
            objects.stdin.flush()
            header = objects.stdout.readline().split()
            if len(header) != 3 or header[0] != oid or header[1] != b"blob":
                raise ValueError("Git returned an invalid historical object")
            size = int(header[2])
            data = objects.stdout.read(size)
            if len(data) != size or objects.stdout.read(1) != b"\n":
                raise ValueError("Git returned an incomplete historical object")
            return data

        for commit in commits:
            check("commit metadata", read("show", "-s", "--format=fuller", commit))
            for row in read("ls-tree", "-rz", commit).split(b"\0"):
                if not row:
                    continue
                meta, raw_name = row.split(b"\t", 1)
                mode, kind, oid = meta.split()
                name = raw_name.decode()
                parts = Path(name).parts
                if kind != b"blob" or mode == b"120000":
                    raise ValueError(f"Git link or submodule: {name}")
                if (
                    parts[0] not in ROOT_DIRS
                    and (len(parts) != 1 or name not in ROOT_FILES | HISTORICAL_ROOT_FILES)
                ) or any(part in SKIP or part.endswith(".egg-info") for part in parts):
                    raise ValueError(f"Git file is not allowlisted: {name}")
                if (oid, name) in seen:
                    continue
                seen.add((oid, name))
                check(name, blob(oid))
    for tag in read("for-each-ref", "--format=%(objectname)", "refs/tags").decode().splitlines():
        if read("cat-file", "-t", tag).strip() == b"tag":
            check("tag metadata", read("cat-file", "-p", tag))
    return {"commits": len(commits), "blob_paths": len(seen)}


def source_files(root: Path):
    for path in sorted(root.iterdir()):
        if path.name in SKIP:
            continue
        if path.is_symlink():
            raise ValueError(f"source symlink: {path.name}")
        if path.is_file():
            if path.name not in ROOT_FILES:
                raise ValueError(f"source file is not allowlisted: {path.name}")
            yield path
        elif path.name in ROOT_DIRS:
            yield from walk(path)
        else:
            raise ValueError(f"source directory is not allowlisted: {path.name}")


def walk(root):
    for path in sorted(root.iterdir()):
        if path.name in SKIP or path.name.endswith(".egg-info"):
            continue
        if path.is_symlink():
            raise ValueError(f"source symlink: {path.name}")
        if path.is_dir():
            yield from walk(path)
        else:
            yield path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--artifacts", type=Path)
    parser.add_argument("--git-history", action="store_true")
    args = parser.parse_args()
    count = 0
    for file in source_files(args.root):
        check(file.relative_to(args.root).as_posix(), file.read_bytes())
        count += 1
    artifacts = []
    if args.artifacts:
        for file in sorted(args.artifacts.iterdir()):
            if file.suffix in {".whl", ".zip"}:
                with zipfile.ZipFile(file) as archive:
                    for name in archive.namelist():
                        check(name, archive.read(name))
            elif file.name.endswith(".tar.gz"):
                with tarfile.open(file) as archive:
                    for member in archive:
                        if member.issym() or member.islnk():
                            raise ValueError("archive links are not allowed")
                        if member.isfile():
                            check(member.name, archive.extractfile(member).read())
            else:
                continue
            artifacts.append(file.name)
    history = audit_git_history(args.root) if args.git_history else None
    print(json.dumps({
        "status": "passed", "source_files": count, "artifacts": artifacts, "git_history": history,
    }, indent=2))


if __name__ == "__main__":
    main()
