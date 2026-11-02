"""Execute search, paired release validation and sealed reporting under one total cap."""

from __future__ import annotations

import asyncio

from pydantic import Field, model_validator

from evosprig.core.protocols import BudgetExceeded
from evosprig.core.spec import Contract
from evosprig.evaluation.budget import BudgetMeter, ExperimentBudget
from evosprig.evaluation.runner import Evaluator

from .context import EvolutionContext
from .gate import ReleaseGate
from .methods import Method


class StudyConfig(Contract):
    method: Method
    allowed_resources: list[str] = Field(min_length=1, max_length=32)
    budget: ExperimentBudget = Field(default_factory=ExperimentBudget)
    gate: ReleaseGate = Field(default_factory=ReleaseGate)
    rounds: int = Field(default=3, ge=1, le=100)
    max_metric_calls: int = Field(default=30, ge=1, le=100000)
    seed: int = Field(default=0, ge=0)
    population_size: int = Field(default=4, ge=4, le=32)
    instruction_candidates: int = Field(default=3, ge=2, le=16)
    demo_candidates: int = Field(default=3, ge=1, le=16)
    max_demos: int = Field(default=2, ge=0, le=8)
    demo_threshold: float = Field(default=0.8, ge=0, le=1, allow_inf_nan=False)

    @model_validator(mode="after")
    def unique_resources(self):
        if len(self.allowed_resources) != len(set(self.allowed_resources)):
            raise ValueError("editable resource names must be unique")
        return self


def combine_usage(search, validation):
    total = {}
    for key in search:
        if key in {"cost", "currency"}:
            total[key] = None
        else:
            total[key] = search[key] + validation.get(key, 0)
    return total


async def execute_study(
    *,
    base,
    suite,
    config,
    models,
    proposer,
    workspace,
    store,
    scope,
    job_id,
    tool_bindings=None,
    evaluation_config=None,
    mock=False,
    environment=None,
    scorers=None,
    on_event=None,
    on_usage=None,
    cancel=None,
):
    from evosprig.evaluation.deployment import evaluation_dependencies

    dependencies = evaluation_dependencies(evaluation_config, mock=mock)
    if environment is not None:
        dependencies["environment"] = environment
    if scorers is not None:
        dependencies["scorers"] = scorers
    validation_count = 2 * (len(suite.release) + len(suite.test))
    if config.budget.max_evaluations <= validation_count:
        raise ValueError("evaluation budget must cover search plus paired release/test validation")
    search_limits = config.budget.model_copy(
        update={
            "max_evaluations": config.budget.max_evaluations - validation_count,
            "max_model_calls": max(1, int(config.budget.max_model_calls * 0.6)),
            "max_total_tokens": max(1, int(config.budget.max_total_tokens * 0.6)),
            "max_seconds": config.budget.max_seconds * 0.6,
        }
    )
    search_meter = BudgetMeter(search_limits, on_change=on_usage)
    if cancel and cancel.is_set():
        search_meter.canceled.set()
    meters = [search_meter]

    async def monitor_cancel():
        while True:
            if cancel and cancel.is_set():
                for meter in meters:
                    meter.canceled.set()
                return
            await asyncio.sleep(0.05)

    watcher = asyncio.create_task(monitor_cancel())
    evaluator = Evaluator(
        workspace,
        models,
        search_meter,
        tool_bindings=tool_bindings,
        tenant=scope.tenant,
        **dependencies,
    )
    context = EvolutionContext(
        base=base,
        allowed=config.allowed_resources,
        view=suite.optimization_view(),
        metric=suite.metric,
        evaluator=evaluator,
        meter=search_meter,
        proposer=proposer,
        store=store,
        scope=scope,
        job_id=job_id,
        method=config.method,
        on_event=on_event,
    )
    try:
        if config.method == "opro":
            from .opro import optimize

            method_result = await optimize(context, rounds=config.rounds)
        elif config.method == "gepa":
            from .gepa import optimize

            method_result = await optimize(
                context, max_metric_calls=config.max_metric_calls, seed=config.seed
            )
        elif config.method == "mipro":
            from .mipro import optimize

            method_result = await optimize(
                context, rounds=config.rounds, seed=config.seed,
                instruction_candidates=config.instruction_candidates,
                demo_candidates=config.demo_candidates,
                max_demos=config.max_demos, demo_threshold=config.demo_threshold,
            )
        elif config.method.startswith("evoprompt_"):
            from .search import evoprompt

            method_result = await evoprompt(
                context,
                variant=config.method.rsplit("_", 1)[1],
                rounds=config.rounds,
                population_size=config.population_size,
                seed=config.seed,
            )
        elif config.method in {"ace", "self_refine"}:
            from .search import ace, self_refine

            method_result = await {"ace": ace, "self_refine": self_refine}[config.method](
                context, rounds=config.rounds
            )
        else:
            from . import extended

            if config.method in {"bootstrap_fewshot", "fewshot_search"}:
                method_result = await extended.bootstrap(
                    context,
                    rounds=config.rounds,
                    seed=config.seed,
                    random_search=config.method == "fewshot_search",
                )
            elif config.method == "promptbreeder":
                method_result = await extended.promptbreeder(
                    context,
                    rounds=config.rounds,
                    seed=config.seed,
                    population_size=config.population_size,
                )
            else:
                method_result = await getattr(extended, config.method)(
                    context, rounds=config.rounds, seed=config.seed
                )
        selected = context.version(method_result["selected"])
        store.put(scope, selected)
        search_usage = search_meter.snapshot()
        remaining = config.budget.model_copy(
            update={
                "max_evaluations": config.budget.max_evaluations - search_usage["evaluations"],
                "max_model_calls": config.budget.max_model_calls - search_usage["model_calls"],
                "max_total_tokens": config.budget.max_total_tokens
                - search_usage["input_tokens"]
                - search_usage["output_tokens"]
                - search_usage["reserved_tokens"],
                "max_seconds": config.budget.max_seconds - search_usage["elapsed_seconds"],
            }
        )
        validation_meter = BudgetMeter(
            remaining,
            on_change=lambda usage: on_usage(combine_usage(search_usage, usage))
            if on_usage
            else None,
        )
        meters.append(validation_meter)
        if cancel and cancel.is_set():
            validation_meter.canceled.set()
        validation = Evaluator(
            workspace,
            models,
            validation_meter,
            tool_bindings=tool_bindings,
            tenant=scope.tenant,
            **dependencies,
        )
        reports = {}
        status, error = "completed", None
        try:
            for split in ("release", "test"):
                samples = getattr(suite, split)
                if not samples:
                    continue
                reports[split] = {}
                for label, version in [("baseline", base), ("selected", selected)]:
                    if label == "selected" and selected.version_id == base.version_id:
                        reports[split][label] = reports[split]["baseline"]
                        context.emit(
                            "validation.reused",
                            split=split,
                            reason="selected version is the baseline",
                        )
                        continue
                    report = await validation.evaluate(
                        version, samples, suite.metric, suite_id=suite.suite_id, split=split
                    )
                    store.report(scope, report)
                    reports[split][label] = report
                    context.emit(
                        "validation.completed",
                        split=split,
                        label=label,
                        report_id=report["report_id"],
                        score=report["score"],
                        count=report["count"],
                    )
            gate = config.gate.assess(
                reports["release"]["baseline"], reports["release"]["selected"]
            )
        except BudgetExceeded:
            status = "canceled" if cancel and cancel.is_set() else "budget_exhausted"
            error = "validation did not complete within the configured budget"
            gate = {"passed": False, "reasons": [error], "automatic_release": False}
        usage = combine_usage(search_usage, validation_meter.snapshot())
        if on_usage:
            on_usage(usage)
        return {
            "status": status,
            "error": error,
            "method": method_result,
            "base_version": base.version_id,
            "selected_version": selected.version_id,
            "suite_id": suite.suite_id,
            "split_ids": {
                split: suite.split_id(split) for split in ("search", "selection", "release", "test")
            },
            "candidates": list(context.candidates.values()),
            "search_reports": [report["report_id"] for report in context.reports],
            "reports": {
                split: {
                    label: {key: value for key, value in report.items() if key != "samples"}
                    for label, report in group.items()
                }
                for split, group in reports.items()
            },
            "gate": gate,
            "usage": usage,
            "release_changed": False,
        }
    finally:
        watcher.cancel()
        await asyncio.gather(watcher, return_exceptions=True)
