"""Bounded real-model integration evidence for OPRO and official GEPA.

The report distinguishes authored smoke cases from empirical benchmark evaluation.
Credentials are read from the environment or hidden terminal input, never written.
"""

import argparse
import asyncio
import getpass
import json
import os
from pathlib import Path

import yaml

from evosprig.config import make_models, make_tools
from evosprig.core.journal import Scope
from evosprig.core.runtime import Runtime
from evosprig.core.spec import load_spec
from evosprig.core.version import compile_agent, compile_snapshot
from evosprig.evaluation.budget import BudgetMeter, ExperimentBudget
from evosprig.evaluation.runner import Evaluator
from evosprig.evaluation.suite import EvalSuite
from evosprig.evolution.gate import ReleaseGate
from evosprig.evolution.study import StudyConfig
from evosprig.plugins.sqlite_studies import StudyStore
from evosprig.server.studies import StudyWorker


async def main(args):
    root = Path(__file__).resolve().parents[1] / "examples/research-assistant"
    spec = load_spec(root / "agent.yaml")
    base = compile_agent(spec, root)
    suite = EvalSuite.model_validate(yaml.safe_load((root / "suite.yaml").read_text()))
    scope = Scope(spec.id)
    workspace = args.workspace.resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    store = StudyStore(workspace / "studies.sqlite")
    store.put(scope, base)
    store.put_suite(scope, suite)
    models = make_models(spec)
    tools = make_tools(workspace, scope)
    metadata = Runtime(models)._engine.model_metadata()
    bindings = {"models": metadata, "proposer": metadata["main"], "tools": tools.bindings}
    report = {
        "kind": "real-model-integration-smoke",
        "model": next(iter(models.values())).model_id,
        "base_version": base.version_id,
        "suite_id": suite.suite_id,
        "split_counts": {
            split: len(getattr(suite, split))
            for split in ("search", "selection", "release", "test")
        },
        "methods": {},
        "currency_cost": None,
        "limitations": "Nine authored cases; deterministic exact-string rubric plus required tool receipts; each split has few samples. Results demonstrate execution, not general optimization effectiveness. No automatic release.",
    }

    def save():
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")

    save()
    for method in ("opro", "gepa"):
        config = StudyConfig(
            method=method,
            allowed_resources=["instructions"],
            rounds=1,
            max_metric_calls=12,
            budget=ExperimentBudget(
                max_evaluations=28,
                max_model_calls=72,
                max_total_tokens=120000,
                max_seconds=900.0,
                max_candidates=2,
                proposal_output_tokens=1536,
            ),
            gate=ReleaseGate(min_samples=2),
        )
        record = store.create_study(
            scope, base.version_id, suite.suite_id, config.model_dump(), bindings
        )
        print(
            json.dumps({"method": method, "study_id": record["id"], "state": "starting"}),
            flush=True,
        )
        worker = StudyWorker(store, workspace / "evaluation")
        task = asyncio.create_task(worker._work(record))
        while not task.done():
            await asyncio.wait({task}, timeout=20)
            state = store.study(scope, record["id"])
            print(
                json.dumps({"method": method, "state": state["status"], "usage": state["usage"]}),
                flush=True,
            )
        await task
        final = store.study(scope, record["id"])
        report["methods"][method] = {
            "study_id": record["id"],
            "status": final["status"],
            "error": final["error"],
            "result": final["result"],
            "budget": config.budget.model_dump(),
        }
        save()
        if final["status"] != "completed":
            raise RuntimeError("real evolution study did not complete: " + method)
    manual = compile_snapshot(
        spec, {"instructions": (root / "prompts/manual-baseline.md").read_text()}
    )
    store.put(scope, manual)
    meter = BudgetMeter(
        ExperimentBudget(
            max_evaluations=4, max_model_calls=12, max_total_tokens=16000, max_seconds=180.0
        )
    )
    evaluator = Evaluator(workspace / "evaluation", models, meter, tool_bindings=tools.bindings)
    report["manual_baseline"] = {"version_id": manual.version_id, "reports": {}}
    for split in ("release", "test"):
        evaluation = await evaluator.evaluate(
            manual, getattr(suite, split), suite.metric, suite_id=suite.suite_id, split=split
        )
        store.report(scope, evaluation)
        report["manual_baseline"]["reports"][split] = {
            key: value for key, value in evaluation.items() if key != "samples"
        }
    report["manual_baseline"]["usage"] = meter.snapshot()
    save()
    print(json.dumps({"status": "completed", "report": str(args.report)}), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--prompt-key", action="store_true")
    args = parser.parse_args()
    if args.prompt_key:
        os.environ["DEEPSEEK_API_KEY"] = getpass.getpass("DeepSeek API key (hidden): ")
    try:
        asyncio.run(main(args))
    finally:
        if args.prompt_key:
            os.environ.pop("DEEPSEEK_API_KEY", None)
