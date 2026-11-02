"""Run each sample with a fresh identity and keep sample-level execution evidence."""

from __future__ import annotations

import asyncio
import statistics
import uuid
from dataclasses import asdict
from pathlib import Path

from evosprig.config import make_tools
from evosprig.core.journal import Scope
from evosprig.core.protocols import BudgetExceeded
from evosprig.core.runtime import Runtime
from evosprig.core.spec import digest
from evosprig.plugins.sqlite_journal import SQLiteJournal

from .budget import BudgetedProvider
from .environment import EnvironmentConfig, LocalEnvironment, approval_response
from .scoring import ScoringEngine


class Evaluator:
    def __init__(
        self,
        workspace,
        models,
        meter,
        *,
        tool_bindings=None,
        tool_factory=None,
        tenant="local",
        judge_models=None,
        scorers=None,
        environment=None,
        environment_config=None,
    ):
        self.workspace = Path(workspace)
        self.models = {name: BudgetedProvider(provider, meter) for name, provider in models.items()}
        self.meter, self.tenant = meter, tenant
        self.tool_bindings = tool_bindings or {}
        self.tool_factory = tool_factory
        self.environment_config = environment_config or EnvironmentConfig()
        self.environment = environment or LocalEnvironment(self.workspace, self.environment_config)
        self.scoring = ScoringEngine(judge_models or models, meter, scorers=scorers)
        # This journal is not consumed by ordinary API workers.
        self.journal = SQLiteJournal(self.workspace / "evaluation-runs.sqlite")

    async def sample(self, version, sample, metric, *, suite_id, split):
        self.meter.consume("evaluations")
        run_id = uuid.uuid4().hex
        scope = Scope(version.spec.id, "evaluation-" + run_id, self.tenant)
        tools = (
            self.tool_factory(scope)
            if self.tool_factory
            else make_tools(self.workspace, scope, bindings=self.tool_bindings)
        )
        remaining = max(
            0.01, self.meter.limits.max_seconds - self.meter.snapshot()["elapsed_seconds"]
        )
        try:
            async with asyncio.timeout(remaining):
                tools = await self.environment.prepare(scope, sample, tools)
                for binding in version.spec.tools.values():
                    tool = tools.resolve(binding.plugin, binding.version)
                    if (tool.side_effect != "read_only" and not self.environment.allow_writes) or (
                        hasattr(self.environment, "permits") and not self.environment.permits(tool)
                    ):
                        raise ValueError(
                            "evaluation writes require an explicitly isolated environment"
                        )
                runtime = Runtime(
                    self.models,
                    tools,
                    journal=self.journal,
                    allow_writes=self.environment.allow_writes,
                )
                result = await runtime.run(version, sample.input, run_id=run_id, scope=scope)
                for _ in range(self.environment_config.max_resumes):
                    if result.status not in {"waiting_input", "waiting_external"}:
                        break
                    if result.status == "waiting_input":
                        unresolved = False
                        for wait in result.waiting:
                            if wait["kind"] == "human" and wait["path"] in sample.responses:
                                response = approval_response(
                                    sample.responses[wait["path"]], wait["input"]
                                )
                                self.journal.respond(run_id, wait["path"], response)
                            elif wait["kind"] in {"human", "operation_unknown"}:
                                unresolved = True
                        if unresolved:
                            break
                    else:
                        await asyncio.sleep(self.environment_config.poll_seconds)
                    self.meter.check()
                    result = await runtime.resume(run_id, scope=scope)
                if result.status in {"waiting_input", "waiting_external"}:
                    result = await runtime.cancel_run(run_id, scope=scope)
                if result.error and result.error.get("code") == "experiment_budget_exhausted":
                    raise BudgetExceeded(
                        "experiment budget ended before assessment", scope="experiment"
                    )
                record = result.to_dict()
                state = self.journal.get(run_id, scope)["checkpoint"]
                observations = {
                    "nodes": {
                        path: node["output"]
                        for path, node in state["nodes"].items()
                        if "output" in node
                    },
                    "tools": [
                        {
                            "tool": op["intent"]["alias"],
                            "arguments": op["intent"]["arguments"],
                            "status": op["status"],
                            "output": op.get("output"),
                        }
                        for op in self.journal.operations(run_id, scope)
                    ],
                    "environment": await self.environment.observe(scope, sample, result),
                }
                assessment = await self.scoring.assess(metric, sample, record, observations)
                score, feedback = assessment["score"], assessment["feedback"]
        except TimeoutError:
            raise BudgetExceeded("experiment time budget exhausted", scope="experiment") from None
        finally:
            await self.environment.cleanup(scope)
        return {
            "sample_id": sample.id,
            "suite_id": suite_id,
            "split": split,
            "version_id": version.version_id,
            "input": sample.input,
            "expected": sample.expected,
            "score": score,
            "feedback": feedback,
            "assessment": assessment,
            "observations": observations,
            "tags": sample.tags,
            "scope": asdict(scope),
            "run": record,
        }

    async def evaluate(self, version, samples, metric, *, suite_id, split):
        semaphore = asyncio.Semaphore(self.environment_config.max_concurrent_samples)

        async def bounded(sample):
            async with semaphore:
                return await self.sample(version, sample, metric, suite_id=suite_id, split=split)

        # Preserve sample order and cancel siblings on a failed assessment.
        tasks = [asyncio.create_task(bounded(sample)) for sample in samples]
        try:
            results = await asyncio.gather(*tasks)
        except BaseException:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            raise
        return aggregate(version.version_id, suite_id, split, results)


def aggregate(version_id, suite_id, split, samples):
    def receipts(assessment):
        yield from assessment.get("judge_receipts", [])
        for child in assessment.get("components", []):
            yield from receipts(child)

    judge_usage = [
        item["usage"] for sample in samples for item in receipts(sample.get("assessment", {}))
    ]
    scores = [sample["score"] for sample in samples]
    tags = {tag for sample in samples for tag in sample["tags"]}
    return {
        "report_id": digest(
            {
                "version": version_id,
                "suite": suite_id,
                "split": split,
                "runs": [sample["run"]["run_id"] for sample in samples],
            }
        ),
        "version_id": version_id,
        "suite_id": suite_id,
        "split": split,
        "count": len(samples),
        "score": statistics.mean(scores) if scores else None,
        "tags": {
            tag: statistics.mean(sample["score"] for sample in samples if tag in sample["tags"])
            for tag in sorted(tags)
        },
        "input_tokens": sum(sample["run"]["usage"]["input_tokens"] for sample in samples),
        "output_tokens": sum(sample["run"]["usage"]["output_tokens"] for sample in samples),
        "judge_usage": {
            "model_calls": len(judge_usage),
            "input_tokens": sum(item["input_tokens"] for item in judge_usage),
            "output_tokens": sum(item["output_tokens"] for item in judge_usage),
        },
        "samples": samples,
    }
