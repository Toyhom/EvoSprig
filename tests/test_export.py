import ast
import hashlib
import json
import os
import runpy
import subprocess
import sys
from pathlib import Path

import pytest

from evosprig.core.version import compile_agent
from evosprig.exporters.python import export_python


def test_export_roundtrip_and_standalone_entry(spec, example_root, tmp_path):
    version = compile_agent(spec, example_root)
    destination = tmp_path / "export"
    report = export_python(version, destination)
    assert report["compatible"]
    built = runpy.run_path(str(destination / "build_agent.py"))["spec"]
    assert built.spec_hash == spec.spec_hash
    assert compile_agent(built, destination).version_id == version.version_id
    manifest = json.loads((destination / "manifest.json").read_text())
    for name, checksum in manifest.items():
        assert hashlib.sha256((destination / name).read_bytes()).hexdigest() == checksum
    environment = {**os.environ, "PYTHONPATH": str(destination / "src")}
    environment.pop("DEEPSEEK_API_KEY", None)
    result = subprocess.run(
        [sys.executable, "app.py", "--mock", "--input", '{"question":"hello world"}'],
        cwd=destination,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )
    assert json.loads(result.stdout)["status"] == "succeeded"
    assert all(
        "server" not in name and "private" not in name and not name.endswith("sqlite")
        for name in manifest
    )


def test_export_is_reproducible(spec, example_root, tmp_path):
    version = compile_agent(spec, example_root)
    export_python(version, tmp_path / "a")
    export_python(version, tmp_path / "b")
    assert (tmp_path / "a/manifest.json").read_bytes() == (
        tmp_path / "b/manifest.json"
    ).read_bytes()


def test_export_rejects_targets_and_unknown_plugins(spec, example_root, tmp_path):
    with pytest.raises(ValueError, match="target runtime"):
        export_python(compile_agent(spec, example_root), tmp_path / "bad", target="typescript")
    spec.tools["stats"].plugin = "custom.unknown"
    with pytest.raises(ValueError, match="no bundled exporter"):
        export_python(compile_agent(spec, example_root), tmp_path / "bad")
    assert not (tmp_path / "bad").exists()


def test_export_refuses_overwrite_and_resource_collision(spec, example_root, tmp_path):
    with pytest.raises(FileExistsError):
        export_python(compile_agent(spec, example_root), tmp_path)
    (tmp_path / "app.py").write_text("resource")
    spec.resources["instructions"].path = "app.py"
    with pytest.raises(ValueError, match="collides"):
        export_python(compile_agent(spec, tmp_path), tmp_path / "bad")
    assert not (tmp_path / "bad").exists()


def test_core_dependency_boundary():
    root = Path(__file__).parents[1] / "src/evosprig/core"
    forbidden = (
        "evosprig.plugins",
        "evosprig.server",
        "evosprig.exporters",
        "evosprig.evolution",
        "httpx",
        "fastapi",
        "sqlite3",
        "torch",
    )
    for file in root.glob("*.py"):
        for node in ast.walk(ast.parse(file.read_text())):
            names = (
                [alias.name for alias in node.names]
                if isinstance(node, ast.Import)
                else [node.module or ""]
                if isinstance(node, ast.ImportFrom)
                else []
            )
            assert not any(name.startswith(forbidden) for name in names), file


def test_memory_tool_export_starts_with_empty_data_and_runs_independently(tmp_path):
    from evosprig.sdk import Builder

    schema = {
        "type": "object",
        "properties": {"content": {"type": "string"}},
        "required": ["content"],
    }
    spec = (
        Builder("memory-example", schema, schema, spec_version="0.2")
        .tool("save", "memory.write")
        .node(
            "save",
            "tool",
            tool="save",
            inputs={"content": {"ref": "input.content"}, "source": {"value": "user:explicit"}},
            output_schema={"type": "object"},
        )
        .output(content={"ref": "nodes.save.output.content"})
        .execution(allow_side_effects=True)
        .build_spec()
    )
    target = tmp_path / "export"
    export_python(compile_agent(spec), target)
    assert not list(target.rglob("*.sqlite"))
    result = subprocess.run(
        [
            sys.executable,
            "app.py",
            "--mock",
            "--allow-writes",
            "--input",
            '{"content":"portable memory"}',
        ],
        cwd=target,
        env={**os.environ, "PYTHONPATH": str(target / "src")},
        check=True,
        text=True,
        capture_output=True,
    )
    assert json.loads(result.stdout)["output"] == {"content": "portable memory"}
