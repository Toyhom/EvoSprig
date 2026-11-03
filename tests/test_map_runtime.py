import asyncio
import json

import pytest
from jsonschema import Draft202012Validator

from evosprig.core.runtime import Runtime
from evosprig.core.spec import AgentSpec
from evosprig.core.version import compile_agent
from evosprig.plugins.builtin_tools import builtin_registry
from evosprig.plugins.sqlite_journal import SQLiteJournal
from evosprig.sdk import Builder
from evosprig.server.canvas import from_canvas, to_canvas


def mapping(*, human=False, cap=8):
    body = {
        "entry": "work",
        "nodes": {
            "work": {
                "type": "human" if human else "tool",
                **({} if human else {"tool": "add"}),
                "inputs": {"a": {"ref": "input.item"}, "b": {"value": 1}},
                "output_schema": {
                    "type": "object",
                    "properties": {"value": {"type": "number"}},
                    "required": ["value"],
                },
            }
        },
        "edges": [],
        "output": {"value": {"ref": "nodes.work.output.value"}},
    }
    return (
        Builder(
            "mapped",
            {"type": "object", "properties": {"values": {"type": "array"}}},
            {"type": "object"},
        )
        .tool("add", "builtin.add")
        .map(
            "batch",
            items={"ref": "input.values"},
            body=body,
            output_schema={"type": "object"},
            max_items=cap,
        )
        .output(results={"ref": "nodes.batch.output.items"})
        .execution(max_parallel_nodes=3)
        .build_spec()
    )


@pytest.mark.parametrize("values", [[], [4, 2, 7]])
async def test_map_order_empty_input_and_roundtrip(values):
    spec = mapping()
    restored, _ = from_canvas(spec, to_canvas(spec))
    assert spec.spec_hash == restored.spec_hash
    result = await Runtime({}, builtin_registry()).run(compile_agent(spec), {"values": values})
    assert result.status == "succeeded"
    assert result.output == {"results": [{"value": value + 1} for value in values]}


async def test_map_item_approvals_recover_without_repeating_completed_items(tmp_path):
    spec = mapping(human=True)
    journal = SQLiteJournal(tmp_path / "runs.sqlite")
    runtime = Runtime({}, builtin_registry(), journal=journal)
    first = await runtime.run(compile_agent(spec), {"values": [10, 20, 30]})
    assert first.status == "waiting_input"
    paths = sorted(w["path"] for w in first.waiting)
    journal.respond(first.run_id, paths[1], {"value": 21})
    second = await Runtime({}, builtin_registry(), journal=SQLiteJournal(journal.path)).resume(
        first.run_id
    )
    assert len(second.waiting) == 2
    for wait in second.waiting:
        journal.respond(first.run_id, wait["path"], {"value": wait["input"]["a"] + 1})
    result = await runtime.resume(first.run_id)
    assert result.status == "succeeded"
    assert result.output["results"] == [{"value": 11}, {"value": 21}, {"value": 31}]
    completed = [e["node_id"] for e in result.events if e["type"] == "node.completed"]
    assert completed.count(paths[1]) == 1


async def test_map_item_cap_and_shared_step_budget():
    too_many = await Runtime({}, builtin_registry()).run(
        compile_agent(mapping(cap=2)), {"values": [1, 2, 3]}
    )
    assert too_many.status == "failed"
    assert not any(e["type"] == "tool.request" for e in too_many.events)
    spec = mapping()
    spec.execution.max_steps = 3
    limited = await Runtime({}, builtin_registry()).run(compile_agent(spec), {"values": [1, 2, 3]})
    assert limited.error["code"] == "budget_exhausted"


async def test_long_workflow_uses_its_configured_budget():
    from evosprig.core.debug import plan_debug

    raw = mapping(cap=256).model_dump()
    body = raw["graph"]["nodes"]["batch"]["body"]
    body["nodes"]["finish"] = {"type": "tool", "tool": "add", "inputs": {
        "a": {"ref": "nodes.work.output.value"}, "b": {"value": 1}}, "output_schema": {"type": "object"}}
    body["edges"] = [{"source": "work", "target": "finish"}]
    body["output"] = {"value": {"ref": "nodes.finish.output.value"}}
    raw["execution"].update(max_steps=1100, timeout_seconds=120)
    spec = AgentSpec.model_validate(raw)
    assert plan_debug(spec, ["batch"]).spec.execution.max_steps == 1101
    result = await Runtime({}, builtin_registry()).run(compile_agent(spec), {"values": list(range(256))})
    assert result.status == "succeeded", result.error
    assert result.usage["steps"] > 1000
    assert result.output["results"][-1] == {"value": 257}


async def test_carry_map_resumes_in_order_with_previous_output(tmp_path):
    raw = mapping(human=True).model_dump()
    batch = raw["graph"]["nodes"]["batch"]
    batch["carry"] = {"value": {"value": 0}}
    batch["body"]["nodes"]["work"]["inputs"]["b"] = {"ref": "input.previous.value"}
    spec = AgentSpec.model_validate(raw)
    journal = SQLiteJournal(tmp_path / "carry.sqlite")
    first = await Runtime({}, builtin_registry(), journal=journal).run(compile_agent(spec), {"values": [3, 7]})
    assert len(first.waiting) == 1
    assert first.waiting[0]["input"] == {"a": 3, "b": 0}
    journal.respond(first.run_id, first.waiting[0]["path"], {"value": 3})
    second = await Runtime({}, builtin_registry(), journal=SQLiteJournal(journal.path)).resume(first.run_id)
    assert len(second.waiting) == 1
    assert second.waiting[0]["input"] == {"a": 7, "b": 3}
    journal.respond(first.run_id, second.waiting[0]["path"], {"value": 10})
    final = await Runtime({}, builtin_registry(), journal=SQLiteJournal(journal.path)).resume(first.run_id)
    assert final.status == "succeeded"
    assert final.output["results"] == [{"value": 3}, {"value": 10}]
    completed = [e["node_id"] for e in final.events if e["type"] == "node.completed"]
    assert completed.count("graph/batch/item-0/work") == 1


async def test_empty_carry_map_returns_initial_state():
    raw = mapping().model_dump()
    raw["graph"]["nodes"]["batch"]["carry"] = {"value": {"value": 9}}
    raw["graph"]["output"] = {"last": {"ref": "nodes.batch.output.carry"}}
    result = await Runtime({}, builtin_registry()).run(compile_agent(AgentSpec.model_validate(raw)), {"values": []})
    assert result.output == {"last": {"value": 9}}


def test_map_requires_new_spec_and_preserves_legacy_canonical_hashes():
    spec = mapping()
    raw = spec.model_dump()
    raw["spec_version"] = "0.2"
    with pytest.raises(ValueError, match="0.3"):
        AgentSpec.model_validate(raw)
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    old = json.loads((root / "spec/agent-spec-0.2.schema.json").read_text())
    from evosprig.core.spec import load_spec

    for path in [root / "examples/hello/agent.yaml", root / "tests/fixtures/support-v02.yaml"]:
        legacy = load_spec(path)
        Draft202012Validator(old).validate(json.loads(legacy.canonical()))
        assert '"max_items"' not in legacy.canonical()


async def test_map_limits_concurrent_leaf_work():
    from evosprig.core.protocols import Tool, ToolRegistry

    active = 0
    maximum = 0

    async def add(a, b):
        nonlocal active, maximum
        active += 1
        maximum = max(maximum, active)
        await asyncio.sleep(0.01)
        active -= 1
        return {"value": a + b}

    registry = ToolRegistry()
    registry.register(Tool("builtin.add", "add", {"type": "object"}, {"type": "object"}, add))
    spec = mapping()
    spec.execution.max_parallel_nodes = 2
    spec.execution.max_parallel_tools = 2
    result = await Runtime({}, registry).run(compile_agent(spec), {"values": list(range(6))})
    assert result.status == "succeeded"
    assert maximum == 2
