"""CLI entrypoints for evaluation and improvement; the runtime remains shared."""

import asyncio
import json
from pathlib import Path

import yaml

from evosprig.config import make_models, make_tools
from evosprig.core.journal import Scope
from evosprig.core.runtime import Runtime
from evosprig.core.spec import load_spec
from evosprig.core.version import compile_agent
from evosprig.evaluation.budget import BudgetMeter, ExperimentBudget
from evosprig.evaluation.runner import Evaluator
from evosprig.evaluation.suite import EvalSuite
from evosprig.plugins.mock import MockProvider
from evosprig.plugins.sqlite_studies import StudyStore

from .gate import ReleaseGate
from .study import StudyConfig


def add_commands(commands):
    for name in ("evaluate", "improve"):
        parser = commands.add_parser(name)
        parser.add_argument("spec", type=Path)
        parser.add_argument("--suite", type=Path, required=True)
        parser.add_argument("--workspace", type=Path, default=Path(".evosprig"))
        parser.add_argument("--profile", type=Path)
        parser.add_argument("--mock", action="store_true")
        parser.add_argument("--max-evaluations", type=int, default=100)
        parser.add_argument("--max-model-calls", type=int, default=200)
        parser.add_argument("--max-total-tokens", type=int, default=200000)
        parser.add_argument("--timeout", type=float, default=600)
        if name == "evaluate":
            parser.add_argument(
                "--split", choices=["search", "selection", "release", "test"], default="release"
            )
        else:
            parser.add_argument("--method", choices=["opro", "gepa", "evoprompt_ga", "evoprompt_de", "self_refine", "ace"], required=True)
            parser.add_argument("--resource", action="append", required=True)
            parser.add_argument("--rounds", type=int, default=3)
            parser.add_argument("--population-size", type=int, default=4)
            parser.add_argument("--max-candidates", type=int, default=24)
            parser.add_argument("--max-metric-calls", type=int, default=30)
            parser.add_argument("--proposal-output-tokens", type=int, default=1024)
            parser.add_argument("--min-gain", type=float, default=0)
            parser.add_argument("--min-samples", type=int, default=2)
            parser.add_argument("--seed", type=int, default=0)
    for name in ("studies", "versions", "release", "rollback", "export-version"):
        parser = commands.add_parser(name)
        parser.add_argument("project")
        parser.add_argument("--workspace", type=Path, default=Path(".evosprig"))
        if name == "release":
            parser.add_argument("--study", required=True)
            parser.add_argument("--revision", type=int, required=True)
        if name in {"rollback", "export-version"}:
            parser.add_argument("version_id")
        if name == "rollback":
            parser.add_argument("--revision", type=int, required=True)
        if name == "export-version":
            parser.add_argument("--profile", type=Path)
            parser.add_argument("--out", type=Path, required=True)


def run_command(args):
    store = StudyStore(args.workspace / "studies.sqlite")
    if args.command in {"studies", "versions", "release", "rollback", "export-version"}:
        scope = Scope(args.project)
        if args.command == "studies":
            result = store.studies(scope)
        elif args.command == "versions":
            result = {
                "release": store.release(scope),
                "candidates": store.candidates(scope),
                "history": store.history(scope),
            }
        elif args.command == "release":
            record = store.study(scope, args.study)
            result = record["result"]
            if record["status"] != "completed" or not result or not result["gate"]["passed"]:
                raise ValueError("study has no candidate that passed release validation")
            result = store.publish(
                scope,
                result["selected_version"],
                expected_revision=args.revision,
                expected_base=result["base_version"],
                reason="manual validated candidate",
                evidence={"study_id": args.study, "gate": result["gate"]},
            )
        elif args.command == "rollback":
            result = store.publish(
                scope,
                args.version_id,
                expected_revision=args.revision,
                reason="manual rollback",
                rollback=True,
            )
        else:
            from evosprig.exporters.python import export_python

            bindings = (
                yaml.safe_load(args.profile.read_text()).get("tools", {}) if args.profile else {}
            )
            result = export_python(
                store.get(scope, args.version_id), args.out, tool_bindings=bindings
            )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    spec = load_spec(args.spec)
    base = compile_agent(spec, args.spec.parent)
    suite = EvalSuite.model_validate(yaml.safe_load(args.suite.read_text()))
    scope = Scope(spec.id)
    store.put(scope, base)
    store.put_suite(scope, suite)
    models = make_models(spec, args.profile, args.mock)
    tools = make_tools(args.workspace, scope, profile=args.profile)
    budget = ExperimentBudget(
        max_evaluations=args.max_evaluations,
        max_model_calls=args.max_model_calls,
        max_total_tokens=args.max_total_tokens,
        max_seconds=args.timeout,
        max_candidates=getattr(args, "max_candidates", 5),
        proposal_output_tokens=getattr(args, "proposal_output_tokens", 1024),
    )
    if args.command == "evaluate":
        meter = BudgetMeter(budget)
        evaluator = Evaluator(
            args.workspace / "evaluation", models, meter, tool_bindings=tools.bindings
        )
        result = asyncio.run(
            evaluator.evaluate(
                base,
                getattr(suite, args.split),
                suite.metric,
                suite_id=suite.suite_id,
                split=args.split,
            )
        )
        store.report(scope, result)
        result["experiment_usage"] = meter.snapshot()
    else:
        from evosprig.server.studies import StudyWorker

        config = StudyConfig(
            method=args.method,
            allowed_resources=args.resource,
            budget=budget,
            rounds=args.rounds,
            population_size=args.population_size,
            max_metric_calls=args.max_metric_calls,
            seed=args.seed,
            gate=ReleaseGate(min_gain=args.min_gain, min_samples=args.min_samples),
        )
        proposer = MockProvider() if args.mock else next(iter(models.values()), None)
        if proposer is None:
            raise ValueError("improvement needs a model binding for its proposer")
        metadata = Runtime(models)._engine.model_metadata()
        proposer_metadata = Runtime({"proposer": proposer})._engine.model_metadata()["proposer"]
        record = store.create_study(
            scope,
            base.version_id,
            suite.suite_id,
            config.model_dump(),
            {"models": metadata, "proposer": proposer_metadata, "tools": tools.bindings},
        )
        worker = StudyWorker(store, args.workspace / "evaluation")
        asyncio.run(worker._work(record))
        result = store.study(scope, record["id"])
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if isinstance(result, dict) and result.get("status") in {
        "failed",
        "canceled",
        "budget_exhausted",
        "interrupted",
    }:
        raise SystemExit(1)
