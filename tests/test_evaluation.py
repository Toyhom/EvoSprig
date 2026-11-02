import asyncio

import pytest

from evosprig.core.protocols import BudgetExceeded, ModelRequest, ModelResponse, Usage
from evosprig.core.version import compile_snapshot
from evosprig.evaluation.budget import BudgetedProvider, BudgetMeter, ExperimentBudget
from evosprig.evaluation.runner import Evaluator
from evosprig.evaluation.suite import EvalSuite
from evosprig.plugins.mock import MockProvider
from evosprig.sdk import Builder


def suite():
    return EvalSuite.model_validate(
        {
            "id": "test-suite",
            "search": [{"id": "s1", "input": {"question": "train"}, "expected": "train-answer"}],
            "selection": [
                {"id": "s2", "input": {"question": "select"}, "expected": "selection-answer"}
            ],
            "release": [
                {"id": "s3", "input": {"question": "release-secret"}, "expected": "release-answer"}
            ],
            "test": [
                {"id": "s4", "input": {"question": "sealed-secret"}, "expected": "test-answer"}
            ],
        }
    )


def version():
    spec = (
        Builder("eval-agent", {"type": "object"}, {"type": "object"})
        .model("main", "main")
        .resource("prompt", "prompts/main.md")
        .node(
            "answer",
            "model",
            model="main",
            instructions={"resource": "prompt"},
            inputs={"question": {"ref": "input.question"}},
            output_schema={"type": "object"},
        )
        .output(answer={"ref": "nodes.answer.output.text"})
        .build_spec()
    )
    return compile_snapshot(spec, {"prompt": "Answer accurately."})


def test_splits_disjoint_and_optimizer_view_has_no_release_or_test_data():
    data = suite()
    view = data.optimization_view()
    assert set(view) == {"suite_id", "search", "selection"}
    assert "secret" not in str(view)
    duplicate = data.model_dump()
    duplicate["test"][0]["input"] = duplicate["search"][0]["input"]
    with pytest.raises(ValueError, match="disjoint"):
        EvalSuite.model_validate(duplicate)
    assert len({data.split_id(split) for split in ["search", "selection", "release", "test"]}) == 4


async def test_budget_is_shared_and_reserves_unknown_usage():
    class Slow(MockProvider):
        async def complete(self, request):
            await asyncio.sleep(0.02)
            return ModelResponse(text="done", usage=Usage(10, 5))

    meter = BudgetMeter(ExperimentBudget(max_model_calls=1))
    provider = BudgetedProvider(Slow(), meter)
    request = ModelRequest([{"role": "user", "content": "hi"}])
    results = await asyncio.gather(
        provider.complete(request), provider.complete(request), return_exceptions=True
    )
    assert sum(isinstance(item, BudgetExceeded) for item in results) == 1
    assert meter.snapshot()["model_calls"] == 1
    assert meter.snapshot()["input_tokens"] == 10
    assert meter.snapshot()["reserved_tokens"] == 0

    class Broken(MockProvider):
        async def complete(self, request):
            raise OSError("no receipt")

    meter2 = BudgetMeter(ExperimentBudget(max_total_tokens=1024))
    with pytest.raises(OSError):
        await BudgetedProvider(Broken(), meter2).complete(request)
    assert meter2.snapshot()["unreported_model_calls"] == 1
    assert meter2.snapshot()["reserved_tokens"] > 0
    with pytest.raises(BudgetExceeded):
        await BudgetedProvider(Slow(), meter2).complete(request)


async def test_sample_reports_and_isolation(tmp_path):
    data = suite()
    model = MockProvider(
        [
            ModelResponse(text="train-answer", usage=Usage(12, 3)),
            ModelResponse(text="wrong", usage=Usage(12, 3)),
        ]
    )
    evaluator = Evaluator(tmp_path, {"main": model}, BudgetMeter(ExperimentBudget()))
    first = await evaluator.evaluate(
        version(), data.search, data.metric, suite_id=data.suite_id, split="search"
    )
    second = await evaluator.evaluate(
        version(), data.search, data.metric, suite_id=data.suite_id, split="search"
    )
    assert first["score"] == 1
    assert second["score"] == 0
    assert first["input_tokens"] == 12
    assert first["samples"][0]["scope"] != second["samples"][0]["scope"]
    assert first["samples"][0]["run"]["events"]
    assert first["samples"][0]["expected"] == "train-answer"


def test_tool_call_metric_uses_successful_receipts():
    data = suite()
    metric = data.metric.model_copy(update={"kind": "tool_called"})
    sample = data.search[0].model_copy(update={"expected": "search"})
    assert (
        metric.score(
            sample,
            {
                "status": "succeeded",
                "events": [{"type": "tool.result", "data": {"tool": "search"}}],
            },
        )[0]
        == 1
    )
    assert (
        metric.score(
            sample,
            {
                "status": "succeeded",
                "events": [{"type": "tool.request", "data": {"tool": "search"}}],
            },
        )[0]
        == 0
    )
