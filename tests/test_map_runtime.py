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

    for path in [root / "examples/hello/agent.yaml", root / "examples/customer-support/agent.yaml"]:
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
