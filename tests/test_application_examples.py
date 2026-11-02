import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from evosprig.core.spec import load_spec
from evosprig.core.version import compile_agent
from evosprig.exporters.python import export_python

ROOT = Path(__file__).resolve().parents[1]


def run_demo(name, workspace, *args):
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "examples" / name / "run_demo.py"),
            "--workspace",
            str(workspace),
            *args,
        ],
        capture_output=True,
        text=True,
        timeout=90,
        cwd=ROOT,
    )
    assert result.returncode == 0, result.stderr
    return json.loads((workspace / "report.json").read_text())


def test_video_approvals_recovery_single_shot_retake_and_recompose(tmp_path):
    result = run_demo("video-studio", tmp_path / "video")
    assert result["status"] == "succeeded"
    assert (
        result["media_jobs"] == 11
    )  # Assets + three frames + three clips + compose + retake frame/clip + recompose.
    assert result["model_calls"] == 1
    before, after = result["timeline_before"]["shots"], result["timeline_after"]["shots"]
    assert before["arrival"] == after["arrival"]
    assert before["departure"] == after["departure"]
    assert before["discovery"]["take_id"] != after["discovery"]["take_id"]
    assert result["film"]["uri"].startswith("fixture://compose/")
    assert after["discovery"]["run_id"] == result["retake_run_id"]


@pytest.mark.parametrize("scenario,refunds", [("approved", 1), ("denied", 0), ("answer", 0)])
def test_support_human_decision_controls_transaction(tmp_path, scenario, refunds):
    result = run_demo("customer-support", tmp_path / scenario, "--scenario", scenario)
    assert result["status"] == "succeeded"
    assert result["refunds"] == refunds
    assert (result["output"]["receipt"] is not None) == bool(refunds)


def test_research_team_retrieves_cites_and_runs_three_roles(tmp_path):
    result = run_demo("research-team", tmp_path / "team")
    assert result["status"] == "succeeded"
    assert result["model_calls"] == 3
    assert "[no evidence]" not in result["output"]["text"]
    assert "[" in result["output"]["text"]


def test_personal_memory_persists_and_selects_current_fact(tmp_path):
    first = run_demo("personal-memory", tmp_path / "memory")
    second = run_demo("personal-memory", tmp_path / "memory")
    assert first == second
    assert first["historical_project"] == "Orion"
    assert first["output"]["text"] == "Alice now works on Atlas."


@pytest.mark.parametrize(
    "example", ["video-studio", "customer-support", "research-team", "personal-memory"]
)
def test_example_exports_include_all_declared_runtime_capabilities(tmp_path, example):
    root = ROOT / "examples" / example
    version = compile_agent(load_spec(root / "agent.yaml"), root)
    profile = root / "deployment.example.yaml"
    bindings = yaml.safe_load(profile.read_text())["tools"] if profile.exists() else {}
    export_python(version, tmp_path / example, tool_bindings=bindings)
    assert (tmp_path / example / "agent.yaml").is_file()
