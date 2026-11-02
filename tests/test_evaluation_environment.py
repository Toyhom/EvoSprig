import pytest

from evosprig.core.protocols import ModelResponse, ToolCall
from evosprig.core.version import compile_agent
from evosprig.evaluation.budget import BudgetMeter, ExperimentBudget
from evosprig.evaluation.environment import EnvironmentConfig, LocalEnvironment
from evosprig.evaluation.runner import Evaluator
from evosprig.evaluation.suite import Metric, Sample
from evosprig.plugins.mock import MockProvider
from evosprig.sdk import Builder


async def test_memory_environment_is_fresh_and_cleanup_runs_on_failure(tmp_path):
    b = (
        Builder("personal", {}, {}, spec_version="0.3")
        .model("main", "main")
        .tool("remember", "memory.remember")
    )
    b.node("assistant", "agent", model="main", tools=["remember"], output_schema={}).output(
        text={"ref": "nodes.assistant.output.text"}
    ).execution(allow_side_effects=True)
    version = compile_agent(b.build_spec())
    model = MockProvider(
        [
            ModelResponse(
                tool_calls=(
                    ToolCall(
                        "save",
                        "remember",
                        {"content": "peanut allergy", "source": "user", "importance": 1},
                    ),
                )
            ),
            ModelResponse(text="Remembered"),
        ]
    )
    config = EnvironmentConfig(memory_writes=True)
    env = LocalEnvironment(tmp_path, config)
    cleaned = []

    async def cleanup(scope):
        cleaned.append(scope)

    env.cleanup = cleanup
    evaluator = Evaluator(
        tmp_path, {"main": model}, BudgetMeter(ExperimentBudget()), environment=env
    )
    sample = Sample(id="a", input={}, expected="Remembered")
    report = await evaluator.evaluate(
        version, [sample], Metric(output_path="text"), suite_id="suite", split="search"
    )
    first = report["samples"][0]
    assert first["score"] == 1 and len(first["observations"]["environment"]["memories"]) == 1
    second = await evaluator.evaluate(
        version, [sample], Metric(output_path="text"), suite_id="suite", split="search"
    )
    assert second["samples"][0]["observations"]["environment"]["memories"] == []
    assert len(cleaned) == 2
    env.allow_writes = False
    with pytest.raises(ValueError, match="isolated"):
        await evaluator.evaluate(
            version, [sample], Metric(output_path="text"), suite_id="suite", split="search"
        )
    assert len(cleaned) == 3


async def test_human_approval_uses_native_resume_and_cancels_unanswered_waits(tmp_path):
    b = Builder("approval", {}, {}, spec_version="0.3")
    b.node(
        "review",
        "human",
        inputs={"draft": {"ref": "input.draft"}},
        output_schema={"type": "object"},
    ).output(text={"ref": "nodes.review.output.text"})
    v = compile_agent(b.build_spec())
    evaluator = Evaluator(tmp_path, {}, BudgetMeter(ExperimentBudget()))
    sample = Sample(
        id="yes",
        input={"draft": "A real draft"},
        expected="A real draft",
        responses={"graph/review": {"text": {"from_input": "draft"}}},
    )
    result = await evaluator.evaluate(
        v, [sample], Metric(output_path="text"), suite_id="suite", split="release"
    )
    assert result["score"] == 1
    unapproved = sample.model_copy(update={"responses": {}})
    result = await evaluator.evaluate(
        v, [unapproved], Metric(output_path="text"), suite_id="suite", split="release"
    )
    assert result["samples"][0]["run"]["status"] == "canceled"


async def test_experiment_budget_is_not_scored_as_an_application_failure(tmp_path):
    from evosprig.core.protocols import BudgetExceeded

    b = Builder("budget-case", {}, {}, spec_version="0.3").model("main", "main")
    b.node("first", "model", model="main", output_schema={}).node(
        "second", "model", model="main", output_schema={}
    )
    b.edge("first", "second").output(text={"ref": "nodes.second.output.text"})
    evaluator = Evaluator(
        tmp_path, {"main": MockProvider()}, BudgetMeter(ExperimentBudget(max_model_calls=1))
    )
    with pytest.raises(BudgetExceeded, match="before assessment"):
        await evaluator.evaluate(
            compile_agent(b.build_spec()),
            [Sample(id="a", input={}, expected="done")],
            Metric(output_path="text"),
            suite_id="s",
            split="search",
        )


async def test_parallel_samples_are_bounded_isolated_and_ordered(tmp_path):
    import asyncio

    class Slow(MockProvider):
        active = peak = 0

        async def complete(self, request):
            self.active += 1
            self.peak = max(self.active, self.peak)
            try:
                await asyncio.sleep(0.05)
                return ModelResponse(text="done")
            finally:
                self.active -= 1

    b = Builder("parallel-eval", {}, {}, spec_version="0.3").model("main", "main")
    b.node("answer", "model", model="main", output_schema={}).output(
        text={"ref": "nodes.answer.output.text"}
    )
    model = Slow()
    evaluator = Evaluator(
        tmp_path,
        {"main": model},
        BudgetMeter(ExperimentBudget()),
        environment_config=EnvironmentConfig(max_concurrent_samples=2),
    )
    report = await evaluator.evaluate(
        compile_agent(b.build_spec()),
        [Sample(id=str(i), input={"n": i}, expected="done") for i in range(5)],
        Metric(output_path="text"),
        suite_id="s",
        split="release",
    )
    assert model.peak == 2
    assert [s["sample_id"] for s in report["samples"]] == [str(i) for i in range(5)]
    assert len({s["scope"]["user"] for s in report["samples"]}) == 5
