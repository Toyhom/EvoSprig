"""Audit source and built archives against the product release allowlist."""

import argparse
import json
import re
import tarfile
import zipfile
from pathlib import Path

ROOT_FILES = {
    "README.md",
    "LICENSE",
    "NOTICE",
    "CHANGELOG.md",
    "CONTRIBUTING.md",
    "pyproject.toml",
    ".gitignore",
    ".dockerignore",
    "requirements-runtime.lock",
    "requirements-dev.lock",
    "THIRD_PARTY_NOTICES.md",
}
ROOT_DIRS = {"src", "docs", "examples", "tests", "spec", "scripts", "apps", ".github"}
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
SECRET = re.compile(rb"\bsk-[A-Za-z0-9_-]{16,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")


def check(name: str, data: bytes):
    parts = Path(name).parts
    if (
        any(part in {"project-private", "local-data"} for part in parts)
        or "AGENT_PLATFORM_META" in name
    ):
        raise ValueError(f"internal material: {name}")
    if any(part.startswith(".env") and part != ".env.example" for part in parts):
        raise ValueError(f"private environment file: {name}")
    if name.endswith((".sqlite", ".db", ".pyc", ".log")):
        raise ValueError(f"runtime artifact: {name}")
    if SECRET.search(data):
        raise ValueError(f"credential-like content: {name}")


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
    print(json.dumps({"status": "passed", "source_files": count, "artifacts": artifacts}, indent=2))


if __name__ == "__main__":
    main()
