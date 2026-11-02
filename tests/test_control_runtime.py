import asyncio
import json

import pytest
from jsonschema import ValidationError

from evosprig.core.protocols import ModelResponse, Usage
from evosprig.core.runtime import Runtime
from evosprig.core.spec import AgentSpec
from evosprig.core.version import compile_agent
from evosprig.plugins.builtin_tools import builtin_registry
from evosprig.plugins.mock import MockProvider
from evosprig.plugins.sqlite_journal import SQLiteJournal
from evosprig.sdk import Builder
from evosprig.server.canvas import from_canvas, to_canvas


def obj(**properties):
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }


def conditional_spec():
    builder = Builder(
        "choice",
        obj(flag={"type": "boolean"}),
        obj(left={"type": ["string", "null"]}, right={"type": ["string", "null"]}),
        spec_version="0.2",
    )
    builder.node(
        "choose",
        "condition",
        condition={"left": {"ref": "input.flag"}, "op": "truthy"},
        output_schema=obj(value={"type": "boolean"}),
    )
    for name in ("yes", "no"):
        builder.node(
            name,
            "transform",
            inputs={"answer": {"value": name}},
            output_schema=obj(answer={"type": "string"}),
        )
        builder.edge("choose", name, when=name == "yes").edge(name, "merge")
    builder.node(
        "merge",
        "join",
        join="selected",
        inputs={
            "left": {"ref": "nodes.yes.output.answer", "optional": True},
            "right": {"ref": "nodes.no.output.answer", "optional": True},
        },
        output_schema=builder.data["output_schema"],
    )
    return builder.output(
        left={"ref": "nodes.merge.output.left"}, right={"ref": "nodes.merge.output.right"}
    ).build_spec()


@pytest.mark.parametrize("flag", [True, False])
async def test_condition_selected_join_and_canvas_roundtrip(flag):
    spec = conditional_spec()
    restored, _ = from_canvas(spec, to_canvas(spec))
    assert restored.spec_hash == spec.spec_hash
    result = await Runtime({}).run(compile_agent(restored), {"flag": flag})
    assert result.status == "succeeded", result.error
    assert result.output == {"left": "yes" if flag else None, "right": None if flag else "no"}
    assert sum(event["type"] == "node.skipped" for event in result.events) == 1


async def test_bounded_loop_stops_when_predicate_matches():
    schema = obj(value={"type": "number"})
    body = {
        "entry": "add",
        "nodes": {
            "add": {
                "type": "tool",
                "tool": "add",
                "inputs": {"a": {"ref": "input.value"}, "b": {"value": 1}},
                "output_schema": schema,
            }
        },
        "edges": [],
        "output": {"value": {"ref": "nodes.add.output.value"}},
    }
    spec = (
        Builder("looping", schema, schema, spec_version="0.2")
        .tool("add", "builtin.add")
        .node(
            "loop",
            "loop",
            inputs={"value": {"ref": "input.value"}},
            body=body,
            max_iterations=8,
            until={"left": {"ref": "input.value"}, "op": "ge", "right": {"value": 3}},
            output_schema=schema,
        )
        .output(value={"ref": "nodes.loop.output.value"})
        .build_spec()
    )
    runtime = Runtime({}, builtin_registry())
    result = await runtime.run(compile_agent(spec), {"value": 0})
    assert result.status == "succeeded", result.error
    assert result.output == {"value": 3}
    assert sum(event["type"] == "tool.result" for event in result.events) == 3


async def test_parallel_branches_run_concurrently_and_share_budget():
    reached = asyncio.Event()
    active = 0

    class BarrierModel(MockProvider):
        async def complete(self, request):
            nonlocal active
            active += 1
            if active == 2:
                reached.set()
            await asyncio.wait_for(reached.wait(), 2)
            return ModelResponse(text="ok", usage=Usage(10, 2), model=self.model_id)

    text = obj(text={"type": "string"})
    branch = {
        "entry": "model",
        "nodes": {"model": {"type": "model", "model": "main", "output_schema": text}},
        "edges": [],
        "output": {"text": {"ref": "nodes.model.output.text"}},
    }
    spec = (
        Builder("parallel", {"type": "object"}, obj(left=text, right=text), spec_version="0.2")
        .model("main", "main")
        .node(
            "experts",
            "parallel",
            branches={"left": branch, "right": branch},
            output_schema=obj(left=text, right=text),
        )
        .output(
            left={"ref": "nodes.experts.output.left"}, right={"ref": "nodes.experts.output.right"}
        )
        .execution(max_parallel_nodes=2, max_model_calls=2)
        .build_spec()
    )
    result = await Runtime({"main": BarrierModel()}).run(compile_agent(spec), {})
    assert result.status == "succeeded", result.error
    assert active == 2
    assert result.usage["input_tokens"] == 20 and result.usage["reserved_tokens"] == 0
    # Only one request may pass the shared reservation gate when the call limit is one.
    spec.execution.max_model_calls = 1
    model = MockProvider()
    result = await Runtime({"main": model}).run(compile_agent(spec), {})
    assert result.error["code"] == "budget_exhausted"
    assert len(model.requests) == 1


async def test_human_checkpoint_validates_input_and_preserves_prior_nodes(tmp_path):
    text = obj(text={"type": "string"})
    spec = (
        Builder("approval", {"type": "object"}, text, spec_version="0.2")
        .model("main", "main")
        .node("draft", "model", model="main", output_schema=text)
        .node(
            "approval",
            "human",
            inputs={"draft": {"ref": "nodes.draft.output.text"}},
            output_schema=text,
        )
        .edge("draft", "approval")
        .output(text={"ref": "nodes.approval.output.text"})
        .build_spec()
    )
    store = SQLiteJournal(tmp_path / "runs.sqlite")
    model = MockProvider()
    runtime = Runtime({"main": model}, journal=store)
    first = await runtime.run(compile_agent(spec), {}, run_id="approval-run")
    assert first.status == "waiting_input"
    assert len(model.requests) == 1
    with pytest.raises(ValidationError):
        store.respond(first.run_id, "graph/approval", {"text": 4})
    assert store.get(first.run_id)["status"] == "waiting_input"
    store.respond(first.run_id, "graph/approval", {"text": "approved"})
    second = await Runtime({"main": model}, journal=SQLiteJournal(store.path)).resume(first.run_id)
    assert second.status == "succeeded", second.error
    assert second.output == {"text": "approved"} and len(model.requests) == 1
    assert [event["sequence"] for event in second.events] == list(range(1, len(second.events) + 1))


async def test_legacy_canonical_hash_stays_unchanged(spec):
    assert spec.spec_hash == "b4491f8fdb9431554fea0074efdd8168c4055ade55cb39d3de67603e29fe5471"


def test_control_nodes_require_explicit_protocol_upgrade():
    raw = json.loads(conditional_spec().canonical())
    raw["spec_version"] = "0.1"
    with pytest.raises(ValueError, match="0.2"):
        AgentSpec.model_validate(raw)
