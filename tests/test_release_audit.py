import runpy
import subprocess
from pathlib import Path

import pytest

AUDIT = runpy.run_path(str(Path(__file__).parents[1] / "scripts/release/audit.py"))


@pytest.mark.parametrize("name", [
    "project-private/notes.md", "docs/AGENTS.md", "local-data/results.json",
    "examples/.env.production", "examples/run.sqlite-wal", "../README.md",
])
def test_rejects_internal_and_runtime_files(name):
    with pytest.raises(ValueError):
        AUDIT["check"](name, b"example")


@pytest.mark.parametrize("data", [
    b"ghp_" + b"x" * 36,
    b"github_pat_" + b"x" * 40,
    b"sk-" + b"x" * 32,
    b"https://" + b"user:password@example.org",
    b"/data/" + b"L123456/project",
    b"http://" + b"192.168.4.10:9000",
])
def test_rejects_secrets_and_private_deployment_without_echoing_values(data):
    with pytest.raises(ValueError) as exc:
        AUDIT["check"]("docs/config.md", data)
    assert data.decode() not in str(exc.value)
    assert "docs/config.md" in str(exc.value)


def test_accepts_public_templates():
    AUDIT["check"]("examples/.env.example", b"MODEL_API_KEY=\n")
    AUDIT["check"]("docs/setup.md", b"http://127.0.0.1:18766 https://api.deepseek.com")


def test_reviewed_synthetic_fixture_does_not_allow_other_credential_urls():
    fixture = b"https://" + b"user:secret@example.org"
    AUDIT["check"]("tests/test_http_tools.py", fixture)
    with pytest.raises(ValueError):
        AUDIT["check"]("docs/config.md", fixture)
    with pytest.raises(ValueError):
        AUDIT["check"]("tests/test_http_tools.py", fixture.replace(b"secret", b"other-password"))


def test_history_scan_rejects_secret_removed_from_current_tree(tmp_path):
    git = ["git", "-c", f"safe.directory={tmp_path}", "-C", str(tmp_path),
           "-c", "user.name=Test", "-c", "user.email=test@example.invalid"]

    def run(*args):
        return subprocess.run([*git, *args], check=True, capture_output=True)

    run("init")
    readme = tmp_path / "README.md"
    readme.write_text("temporary " + "ghp_" + "x" * 36)
    run("add", "README.md")
    run("commit", "-m", "first")
    readme.write_text("public content")
    run("add", "README.md")
    run("commit", "-m", "remove value")
    AUDIT["check"]("README.md", readme.read_bytes())
    with pytest.raises(ValueError, match="credential-like content"):
        AUDIT["audit_git_history"](tmp_path)
