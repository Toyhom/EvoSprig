from types import SimpleNamespace

import pytest

from evosprig.core.journal import Scope
from evosprig.core.protocols import ModelResponse, Tool, ToolCall, ToolRegistry
from evosprig.core.version import compile_snapshot
from evosprig.evaluation.budget import BudgetMeter, ExperimentBudget
from evosprig.evaluation.industry import IndustryConfig, IndustryEnvironment, industry_score
from evosprig.evaluation.runner import Evaluator
from evosprig.evaluation.suite import Metric, Sample
from evosprig.industry_cli import INSTRUCTIONS, industry_agent
from evosprig.plugins.mock import MockProvider


class Session:
    instances = []

    def __init__(self, case_id):
        self.case, self.industry = case_id, "government"
        self.env, self.value, self.closed = self, 0, False
        self.instances.append(self)

    def observation(self):
        return {"case_id": self.case, "request": "Approve one item"}

    def search(self, query, limit):
        return [{"function": {"name": "approve", "parameters": {"type": "object"}}}]

    def call(self, name, arguments, idempotency_key=None):
        assert idempotency_key and name == "approve"
        self.value += 1
        return {"ok": True, "value": self.value}

    def final_state(self):
        return {"value": self.value}

    def close(self):
        self.closed = True


def backend():
    def evaluate(predictions, industry, ids):
        assert len(predictions) == 1 and predictions[0]["case_id"] == ids[0]
        return {"summary": {"task_success_rate": float(len(predictions[0]["calls"]) == 1)}}

    return Session, SimpleNamespace(sop=lambda industry, case: "Read, approve, verify."), evaluate


async def test_industry_agent_uses_isolated_tools_and_replay_scores(tmp_path):
    env = IndustryEnvironment(backend=backend())
    model = MockProvider(
        [
            ModelResponse(tool_calls=(ToolCall("find", "search", {"query": "approve"}),)),
            ModelResponse(
                tool_calls=(ToolCall("do", "invoke", {"name": "approve", "arguments": {}}),)
            ),
            ModelResponse(text="Completed"),
        ]
    )
    evaluator = Evaluator(
        tmp_path,
        {"main-model": model},
        BudgetMeter(ExperimentBudget()),
        environment=env,
        scorers={"industry": industry_score},
    )
    version = compile_snapshot(industry_agent(), {"procedure": INSTRUCTIONS})
    metric = Metric(kind="external", scorer="industry", target="environment", output_path="")
    sample = Sample(id="one", input={"case_id": "case-1"})
    report = await evaluator.evaluate(version, [sample], metric, suite_id="s", split="search")
    assert report["score"] == 1
    observed = report["samples"][0]["observations"]["environment"]
    assert len(observed["calls"]) == 1
    assert Session.instances[-1].closed and not env.sessions
    # A claimed success without an actual business action cannot pass replay.
    model2 = MockProvider([ModelResponse(text="Completed successfully")])
    evaluator.models["main-model"] = model2
    second = await evaluator.evaluate(version, [sample], metric, suite_id="s", split="release")
    assert second["score"] == 0
    assert Session.instances[-1].value == 0 and Session.instances[-1].closed


async def test_industry_scope_discovery_and_budget():
    env = IndustryEnvironment(
        IndustryConfig(allowed_cases=["allowed"], max_calls=1), backend=backend()
    )
    scope = Scope("app")
    with pytest.raises(ValueError, match="allowlist"):
        await env.prepare(scope, Sample(id="bad", input={"case_id": "other"}), ToolRegistry())
    tools = await env.prepare(scope, Sample(id="ok", input={"case_id": "allowed"}), ToolRegistry())
    invoke = tools.resolve("industry.invoke")
    assert not (await invoke.invoke({"name": "approve", "arguments": {}}, operation_id="first"))[
        "ok"
    ]
    await tools.resolve("industry.search").invoke({"query": "approve"})
    assert (await invoke.invoke({"name": "approve", "arguments": {}}, operation_id="second"))["ok"]
    assert not (await invoke.invoke({"name": "approve", "arguments": {}}, operation_id="third"))[
        "ok"
    ]
    unrelated = Tool(
        "external.write", "Write outside sandbox", {}, {}, lambda: {}, side_effect="write"
    )
    assert not env.permits(unrelated)
    await env.cleanup(scope)


async def test_synthesis_templates_build_native_workflow_and_wait_for_review(tmp_path):
    import yaml

    from evosprig.core.runtime import Runtime
    from evosprig.core.spec import load_spec
    from evosprig.core.version import compile_agent
    from evosprig.industry_cli import synthesis_project

    templates = tmp_path / "templates/government/prompts"
    templates.mkdir(parents=True)
    files = [
        "Context_Generation",
        "Schema_Generation",
        "SOP_Generation",
        "API_Graph_Generation",
        "Dataset_Generation",
        "SOP_API_Generation",
        "SOP_API_Function_Code",
    ]
    for i, name in enumerate(files):
        content = (
            {"system_prompt": "Draft the environment", "user_prompt": "Use the brief"}
            if i == 0
            else {"prompts": {"text_1": "Use prior outputs", "text_2": "Return an editable draft"}}
        )
        (templates / (name + ".yaml")).write_text(yaml.safe_dump(content))
    out = tmp_path / "builder"
    synthesis_project(out, template_root=tmp_path / "templates", scene="government")
    version = compile_agent(load_spec(out / "agent.yaml"), out)
    model = MockProvider([ModelResponse(text=f"Draft {i}") for i in range(7)])
    runtime = Runtime({"main-model": model})
    run = await runtime.run(version, {"brief": "Permit approvals"})
    assert run.status == "waiting_input" and len(model.requests) == 7
    runtime.journal.respond(run.run_id, "graph/review_environment", {"approved": True})
    final = await runtime.resume(run.run_id)
    assert final.status == "succeeded" and final.output["implementation"] == "Draft 6"
