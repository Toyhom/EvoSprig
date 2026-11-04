import json
import os
import shutil
import zipfile
from pathlib import Path

import pytest
import yaml

from evosprig.config import make_tools
from evosprig.core.journal import Scope
from evosprig.core.spec import load_spec
from evosprig.core.version import compile_agent
from evosprig.exporters.importer import inspect_archive
from evosprig.exporters.python import export_python
from evosprig.plugins.office_artifacts import analyze, create_office
from evosprig.plugins.spice_artifacts import simulate

ROOT = Path(__file__).resolve().parents[1]
ROWS = [{"period": "A", "revenue": 0.3, "cost": 0.1, "orders": 1},
        {"period": "B", "revenue": 20, "cost": 5, "orders": 3}]


def test_office_formulas_cached_numbers_and_cross_file_values(tmp_path):
    openpyxl = pytest.importorskip("openpyxl")
    pytest.importorskip("docx")
    pytest.importorskip("pptx")
    pytest.importorskip("xlsxwriter")
    from docx import Document
    from pptx import Presentation

    result = create_office(tmp_path, ROWS, "Quarterly brief", "Profit {{profit}} from {{orders}} orders.", ["Review costs."])
    formulas = openpyxl.load_workbook(tmp_path / "analysis.xlsx", data_only=False)
    cached = openpyxl.load_workbook(tmp_path / "analysis.xlsx", data_only=True)
    assert formulas.active["E2"].value == "=B2-C2"
    assert cached.active["E2"].value == .2
    assert cached.active["E4"].value == analyze(ROWS)["profit"] == 15.2
    assert "15.20" in result["summary"]
    document = Document(tmp_path / "brief.docx")
    assert any("15.20" in p.text for p in document.paragraphs)
    deck = Presentation(tmp_path / "report.pptx")
    assert any("15.20" in shape.text for slide in deck.slides for shape in slide.shapes if shape.has_text_frame)
    formulas.close()
    cached.close()


@pytest.mark.parametrize("name", ["office-deliverables", "circuit-lab", "trade-followup", "comic-studio"])
def test_new_apps_compile_and_export_import(name, tmp_path):
    root = ROOT / "examples" / name
    version = compile_agent(load_spec(root / "agent.yaml"), root)
    bindings = yaml.safe_load((root / "deployment.example.yaml").read_text())["tools"]
    report = export_python(version, tmp_path / "export", tool_bindings=bindings)
    assert report["compatible"]
    assert (tmp_path / "export/src/evosprig/local_services.py").is_file()
    archive = tmp_path / "application.zip"
    with zipfile.ZipFile(archive, "w") as package:
        for file in (tmp_path / "export").rglob("*"):
            if file.is_file():
                package.write(file, file.relative_to(tmp_path / "export").as_posix())
    restored, _ = inspect_archive(archive.read_bytes())
    assert restored.version_id == version.version_id
    if name == "office-deliverables":
        assert "xlsxwriter" in (tmp_path / "export/requirements.lock").read_text()


async def test_artifacts_reuse_receipt_and_separate_user_workspaces(tmp_path):
    pytest.importorskip("xlsxwriter")
    pytest.importorskip("docx")
    pytest.importorskip("pptx")
    binding = {"office": {"kind": "artifact", "name": "office", "operation": "office"}}
    one = make_tools(tmp_path, Scope("reports", user="one"), bindings=binding)
    two = make_tools(tmp_path, Scope("reports", user="two"), bindings=binding)
    payload = {"rows": ROWS, "title": "A", "summary": "Profit {{profit}}", "recommendations": []}
    first = await one.resolve("office", "1").invoke(payload, operation_id="same")
    second = await one.resolve("office", "1").invoke(payload, operation_id="same")
    other = await two.resolve("office", "1").invoke(payload, operation_id="same")
    assert first == second and first["directory"] != other["directory"]
    assert zipfile.is_zipfile(Path(first["directory"]) / "analysis.xlsx")


def test_spice_refuses_includes_and_incomplete_voltage_source(tmp_path, monkeypatch):
    monkeypatch.setenv("EVOSPRIG_NGSPICE", "/unused")
    bad = simulate(tmp_path, "test\n.include /etc/passwd\n.end", "ac", {})
    assert not bad["ok"]
    bad = simulate(tmp_path, "test\nEamp out feedback 100k\n.end", "ac", {})
    assert not bad["ok"] and "six tokens" in bad["error"]


@pytest.mark.skipif(not (os.environ.get("EVOSPRIG_NGSPICE") or shutil.which("ngspice")), reason="ngspice is optional")
def test_real_rc_cutoff(tmp_path):
    result = simulate(tmp_path, "RC filter\nV1 in 0 AC 1\nR1 in out 1k\nC1 out 0 159n\n.end", "ac",
                      {"cutoff_hz": {"min": 950, "max": 1050}})
    assert result["ok"] and result["accepted"]
    assert result["samples"] > 200
    assert (tmp_path / "waveform.svg").is_file()
    json.dumps(result, allow_nan=False)
