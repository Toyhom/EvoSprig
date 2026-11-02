"""Exercise approvals, durable jobs, a single-shot retake and timeline replacement."""

import argparse
import asyncio
import json
from pathlib import Path

from build_agent import production, shot_builder
from offline import PLAN, MediaSimulator
from takes import TakeStore

from evosprig.core.protocols import ModelResponse
from evosprig.core.runtime import Runtime
from evosprig.core.spec import load_spec
from evosprig.core.version import compile_agent
from evosprig.plugins.mock import MockProvider
from evosprig.plugins.sqlite_journal import SQLiteJournal


async def drive(runtime, result):
    for _ in range(40):
        if result.status == "succeeded":
            return result
        if result.status not in {"waiting_input", "waiting_external"}:
            raise RuntimeError(result.error or result.status)
        for wait in result.waiting:
            if "schema" not in wait:
                continue
            inputs = wait["input"]
            if wait["path"].endswith("script_review"):
                response = inputs["plan"]
            elif wait["path"].endswith("frame_review"):
                response = inputs["frame"]
            else:
                response = {
                    "clips": [take["clip"] for _, take in sorted(inputs["takes"].items())],
                    "audio": [],
                    "subtitles": "",
                }
            runtime.journal.respond(result.run_id, wait["path"], response)
        # A new runtime object reads the same checkpoint after each pause.
        runtime = Runtime(
            runtime.models,
            runtime.tools,
            journal=SQLiteJournal(runtime.journal.path),
            allow_writes=True,
        )
        result = await runtime.resume(result.run_id)
    raise RuntimeError("offline workflow did not terminate")


async def demo(workspace):
    workspace = Path(workspace)
    workspace.mkdir(parents=True, exist_ok=True)
    simulator = MediaSimulator(workspace / "media.sqlite")
    model = MockProvider([ModelResponse(text=json.dumps(PLAN))])
    runtime = Runtime(
        {"main": model},
        simulator.registry(),
        journal=SQLiteJournal(workspace / "runs.sqlite"),
        allow_writes=True,
    )
    result = await drive(
        runtime,
        await runtime.run(
            compile_agent(production(), Path(__file__).parent),
            {"brief": "A librarian discovers a living book."},
        ),
    )
    takes = TakeStore(workspace / "takes.sqlite")
    for index, shot in enumerate(PLAN["shots"], 1):
        take = result.output["takes"][f"shot_{index}"]
        identifier = takes.add(shot["id"], result.run_id, take["clip"])
        takes.select(identifier, revision=takes.current()["revision"])
    before = takes.current()
    shot = {**PLAN["shots"][1], "camera": "macro push in"}
    retake = await drive(
        runtime,
        await runtime.run(
            compile_agent(shot_builder().build_spec()),
            {"shot": shot, "catalog": result.output["catalog"], "style": PLAN["style"]},
        ),
    )
    identifier = takes.add(shot["id"], retake.run_id, retake.output["clip"])
    after = takes.select(identifier, revision=before["revision"])
    composed = await drive(
        runtime,
        await runtime.run(
            compile_agent(load_spec(Path(__file__).with_name("compose-agent.yaml"))),
            {
                "clips": [after["shots"][shot["id"]]["clip"] for shot in PLAN["shots"]],
                "audio": [],
                "subtitles": "",
            },
        ),
    )
    report = {
        "mode": "offline-contract",
        "run_id": result.run_id,
        "retake_run_id": retake.run_id,
        "status": result.status,
        "media_jobs": len(simulator.jobs()),
        "timeline_before": before,
        "timeline_after": after,
        "film": composed.output["film"],
        "model_calls": len(model.requests),
        "automatic_review": True,
    }
    (workspace / "report.json").write_text(json.dumps(report, indent=2))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(asyncio.run(demo(args.workspace)), indent=2))
