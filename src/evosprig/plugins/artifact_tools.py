"""Reusable document, simulation and page-layout tools with workspace-owned outputs."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Literal

from pydantic import Field

from evosprig.core.protocols import Tool
from evosprig.core.spec import Contract


class ArtifactToolConfig(Contract):
    kind: Literal["artifact"] = "artifact"
    name: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_.-]{0,127}$")
    version: Literal["1"] = "1"
    operation: Literal["table", "office", "spice", "comic"]


def obj(**fields):
    return {"type": "object", "properties": fields, "required": list(fields), "additionalProperties": False}


TEXT = {"type": "string", "maxLength": 12000}
ROW = obj(period={"type": "string", "maxLength": 100}, revenue={"type": "number", "minimum": 0},
          cost={"type": "number", "minimum": 0}, orders={"type": "integer", "minimum": 0})
ROWS = {"type": "array", "items": ROW, "minItems": 1, "maxItems": 1000}
SCHEMAS = {
    "table": obj(rows=ROWS),
    "office": obj(rows=ROWS, title=TEXT, summary=TEXT,
                  recommendations={"type": "array", "items": TEXT, "maxItems": 8}),
    "spice": obj(netlist={"type": "string", "minLength": 1, "maxLength": 16000},
                 analysis={"enum": ["ac", "transient"]},
                 target={"type": "object"}),
    "comic": obj(title=TEXT, panels={"type": "array", "minItems": 1, "maxItems": 12,
                "items": obj(image={"type": "string", "maxLength": 2000}, caption=TEXT,
                             dialogue=TEXT)}),
}


def artifact_tool(config, workspace, scope):
    tenant = hashlib.sha256(json.dumps([scope.tenant, scope.user, scope.project]).encode()).hexdigest()[:24]
    root = Path(workspace) / "artifacts" / tenant

    def invoke(**arguments):
        key = arguments.pop("idempotency_key", None)
        if config.operation == "table":
            from .office_artifacts import analyze

            return analyze(arguments["rows"])
        digest = hashlib.sha256(json.dumps([config.operation, key, arguments], sort_keys=True).encode()).hexdigest()[:24]
        destination = root / digest
        receipt = destination / "result.json"
        if receipt.is_file():
            return json.loads(receipt.read_text())
        destination.mkdir(parents=True, exist_ok=True)
        if config.operation == "office":
            from .office_artifacts import create_office

            result = create_office(destination, **arguments)
        elif config.operation == "spice":
            from .spice_artifacts import simulate

            result = simulate(destination, **arguments)
        else:
            from .comic_artifacts import compose

            result = compose(destination, **arguments)
        # Failed simulations remain repairable and never masquerade as valid deliverables.
        result["directory"] = str(destination.resolve())
        temporary = destination / ("result-" + str(os.getpid()) + ".tmp")
        temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2))
        temporary.replace(receipt)
        return result

    return Tool(config.name, {
        "table": "Calculate revenue, costs, profit, margin and period changes from source rows.",
        "office": "Create an editable XLSX workbook, DOCX brief and PPTX deck using one calculation set.",
        "spice": "Run a bounded ngspice circuit simulation and return measured metrics and waveforms.",
        "comic": "Lay out existing panel images, captions and dialogue into a comic chapter.",
    }[config.operation], SCHEMAS[config.operation], {"type": "object"}, invoke,
        side_effect="read_only" if config.operation == "table" else "write",
        pure=config.operation == "table", idempotent=config.operation != "table", timeout_seconds=120)
