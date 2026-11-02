"""Run each sample with a fresh identity and keep sample-level execution evidence."""

from __future__ import annotations

import asyncio
import statistics
import uuid
from dataclasses import asdict
from pathlib import Path

from evosprig.config import make_tools
from evosprig.core.journal import Scope
from evosprig.core.runtime import Runtime
from evosprig.core.spec import digest
from evosprig.plugins.sqlite_journal import SQLiteJournal

from .budget import BudgetedProvider


class Evaluator:
    def __init__(
        self, workspace, models, meter, *, tool_bindings=None, tool_factory=None, tenant="local"
    ):
        self.workspace = Path(workspace)
        self.models = {name: BudgetedProvider(provider, meter) for name, provider in models.items()}
        self.meter, self.tenant = meter, tenant
        self.tool_bindings = tool_bindings or {}
        self.tool_factory = tool_factory
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
        # Only audited read-only tools are eligible for the Alpha evaluation harness.
        for binding in version.spec.tools.values():
            if tools.resolve(binding.plugin, binding.version).side_effect != "read_only":
                raise ValueError(
                    "evaluation requires read-only tools or a separate sandbox adapter"
                )
        runtime = Runtime(self.models, tools, journal=self.journal)
        remaining = max(
            0.01, self.meter.limits.max_seconds - self.meter.snapshot()["elapsed_seconds"]
        )
        async with asyncio.timeout(remaining):
            result = await runtime.run(version, sample.input, run_id=run_id, scope=scope)
        record = result.to_dict()
        score, feedback = metric.score(sample, record)
        return {
            "sample_id": sample.id,
            "suite_id": suite_id,
            "split": split,
            "version_id": version.version_id,
            "input": sample.input,
            "expected": sample.expected,
            "score": score,
            "feedback": feedback,
            "tags": sample.tags,
            "scope": asdict(scope),
            "run": record,
        }

    async def evaluate(self, version, samples, metric, *, suite_id, split):
        results = []
        for sample in samples:
            results.append(
                await self.sample(version, sample, metric, suite_id=suite_id, split=split)
            )
        return aggregate(version.version_id, suite_id, split, results)


def aggregate(version_id, suite_id, split, samples):
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
        "samples": samples,
    }
