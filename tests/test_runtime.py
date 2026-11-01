import asyncio

import pytest

from evosprig.core.protocols import ModelResponse, ToolCall, Usage
from evosprig.core.runtime import Runtime
from evosprig.core.version import compile_agent
from evosprig.plugins.builtin_tools import builtin_registry
from evosprig.plugins.mock import MockProvider
from evosprig.sdk import Builder
from evosprig.server.canvas import from_canvas, to_canvas


def agent_spec(max_calls=3):
    schema = {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}
    return (
        Builder("calculator", {"type": "object"}, schema)
        .model("main", "main")
        .tool("add", "builtin.add")
        .node(
            "agent",
            "agent",
            model="main",
            tools=["add"],
            inputs={"task": {"value": "Add 2 and 3"}},
            output_schema=schema,
        )
        .output(text={"ref": "nodes.agent.output.text"})
        .execution(max_model_calls=max_calls)
        .build_spec()
    )


async def test_mock_execution_and_canvas_parity(spec, example_root):
    runtime = Runtime({"main-model": MockProvider()}, builtin_registry())
    first = await runtime.run(compile_agent(spec, example_root), {"question": "hello world"})
    restored, _ = from_canvas(spec, to_canvas(spec))
    second = await runtime.run(compile_agent(restored, example_root), {"question": "hello world"})
    assert first.status == "succeeded"
    assert first.output == second.output
    assert '"word_count":2' in first.output["answer"]
    assert [event["sequence"] for event in first.events] == list(range(1, len(first.events) + 1))
    assert first.usage["model_calls"] == 1
    assert first.usage["cost"] is None


async def test_agent_tool_loop_preserves_call_ids():
    model = MockProvider(
        [
            ModelResponse(
                tool_calls=(ToolCall("call-7", "add", {"a": 2, "b": 3}),), usage=Usage(4, 4)
            ),
            ModelResponse(text="5", usage=Usage(8, 2)),
        ]
    )
    result = await Runtime({"main": model}, builtin_registry()).run(compile_agent(agent_spec()), {})
    assert result.status == "succeeded"
    assert result.output == {"text": "5"}
    assert model.requests[1].messages[-1]["tool_call_id"] == "call-7"
    assert model.requests[1].messages[-1]["content"] == '{"value":5}'
    assert result.usage["input_tokens"] == 12


async def test_call_budget_stops_loop():
    model = MockProvider([ModelResponse(tool_calls=(ToolCall("c", "add", {"a": 2, "b": 3}),))])
    result = await Runtime({"main": model}, builtin_registry()).run(
        compile_agent(agent_spec(1)), {}
    )
    assert result.error["code"] == "budget_exhausted"
    assert len(model.requests) == 1


@pytest.mark.parametrize(
    "call", [ToolCall("c", "unregistered", {}), ToolCall("c", "add", {"a": "invalid", "b": 3})]
)
async def test_untrusted_tool_calls_fail(call):
    model = MockProvider([ModelResponse(tool_calls=(call,))])
    result = await Runtime({"main": model}, builtin_registry()).run(compile_agent(agent_spec()), {})
    assert result.status == "failed"
    assert not any(event["type"] == "tool.result" for event in result.events)


async def test_token_reservation_prevents_request(spec, example_root):
    spec.execution.max_total_tokens = 1
    model = MockProvider()
    result = await Runtime({"main-model": model}, builtin_registry()).run(
        compile_agent(spec, example_root), {"question": "hi"}
    )
    assert result.error["code"] == "budget_exhausted"
    assert not model.requests


async def test_cancellation_before_model(spec, example_root):
    cancel = asyncio.Event()
    cancel.set()
    model = MockProvider()
    result = await Runtime({"main-model": model}, builtin_registry()).run(
        compile_agent(spec, example_root), {"question": "hi"}, cancel=cancel
    )
    assert result.status == "canceled"
    assert not model.requests


async def test_timeout_and_inflight_cancellation(spec, example_root):
    class SlowModel(MockProvider):
        async def complete(self, request):
            await asyncio.sleep(5)

    spec.execution.timeout_seconds = 0.03
    runtime = Runtime({"main-model": SlowModel()}, builtin_registry())
    version = compile_agent(spec, example_root)
    result = await runtime.run(version, {"question": "hi"})
    assert result.error["code"] == "timeout"
    assert result.usage["unreported_model_calls"] == 1
    spec.execution.timeout_seconds = 10.0
    task = asyncio.create_task(runtime.run(compile_agent(spec, example_root), {"question": "hi"}))
    await asyncio.sleep(0.02)
    task.cancel()
    assert (await task).status == "canceled"


async def test_input_and_output_validation(spec, example_root):
    model = MockProvider()
    runtime = Runtime({"main-model": model}, builtin_registry())
    invalid = await runtime.run(compile_agent(spec, example_root), {"question": 5})
    assert invalid.status == "failed"
    assert not model.requests
    spec.graph.nodes["assistant"].response_format = "json"
    invalid = await runtime.run(compile_agent(spec, example_root), {"question": "hi"})
    assert invalid.status == "failed"
