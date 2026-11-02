import asyncio
import json

from evosprig.core.protocols import ModelResponse, Tool, ToolCall, ToolRegistry
from evosprig.core.runtime import Runtime
from evosprig.core.version import compile_agent
from evosprig.plugins.mock import MockProvider
from evosprig.plugins.sqlite_journal import SQLiteJournal
from evosprig.sdk import Builder


async def test_parallel_read_calls_overlap_preserve_order_and_receipts(tmp_path):
    entered = []
    ready = asyncio.Event()

    async def lookup(value):
        entered.append(value)
        if len(entered) == 2:
            ready.set()
        await asyncio.wait_for(ready.wait(), 2)
        await asyncio.sleep(0.01 if value == 1 else 0)
        return {"value": value}

    registry = ToolRegistry()
    registry.register(Tool("lookup", "Lookup", {}, {}, lookup))
    b = Builder("parallel-tools", {}, {}, spec_version="0.3").model("main", "main")
    b.tool("lookup", "lookup").node(
        "agent", "agent", model="main", tools=["lookup"], parallel_tool_calls=True, output_schema={}
    )
    b.output(text={"ref": "nodes.agent.output.text"}).execution(max_parallel_tools=2)
    model = MockProvider(
        [
            ModelResponse(
                tool_calls=(
                    ToolCall("a", "lookup", {"value": 1}),
                    ToolCall("b", "lookup", {"value": 2}),
                )
            ),
            ModelResponse(text="Done"),
        ]
    )
    journal = SQLiteJournal(tmp_path / "runs.sqlite")
    result = await Runtime({"main": model}, registry, journal=journal).run(
        compile_agent(b.build_spec()), {}
    )
    assert result.status == "succeeded", result.error
    receipts = [json.loads(m["content"]) for m in model.requests[1].messages if m["role"] == "tool"]
    assert receipts == [{"value": 1}, {"value": 2}]
    assert len(journal.operations(result.run_id)) == 2


async def test_retrieved_tools_never_expand_allowlist():
    registry = ToolRegistry()
    for name, desc in [
        ("weather", "Weather forecast temperature"),
        ("finance", "Finance accounting balance"),
    ]:
        registry.register(Tool(name, desc, {}, {}, lambda: {}))
    b = Builder("discovery", {}, {}, spec_version="0.3").model("main", "main")
    for name in ("weather", "finance"):
        b.tool(name, name)
    b.node(
        "agent",
        "agent",
        model="main",
        tools=["weather", "finance"],
        tool_selection="relevant",
        tool_limit=1,
        inputs={"task": {"ref": "input.task"}},
        output_schema={},
    )
    b.output(text={"ref": "nodes.agent.output.text"})
    model = MockProvider([ModelResponse(tool_calls=(ToolCall("wrong", "finance", {}),))])
    result = await Runtime({"main": model}, registry).run(
        compile_agent(b.build_spec()), {"task": "weather forecast"}
    )
    assert [t["function"]["name"] for t in model.requests[0].tools] == ["weather"]
    assert result.status == "failed"


def test_duplicate_tool_aliases_rejected_before_provider_request():
    import pytest

    from evosprig.core.spec import Node

    with pytest.raises(ValueError, match="tool aliases must be unique"):
        Node(
            type="agent", model="main", tools=["recall", "recall"], output_schema={"type": "object"}
        )
