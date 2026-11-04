import json

from evosprig.core.context_window import tool_observation


def test_bounded_unicode_observation_keeps_start_and_end():
    value = {"rows": ["开头"+"x\\\""*10000+"结尾"]}
    preview = tool_observation(value, 1024)
    assert len(preview) <= 1024
    parsed = json.loads(preview)
    assert parsed["truncated"] and "开头" in parsed["preview"] and "结尾" in parsed["preview"]
    assert len(value["rows"][0]) > 10000
    assert json.loads(tool_observation({"answer": 42}, 512)) == {"answer": 42}


async def test_runtime_bounds_model_observation_and_keeps_full_tool_result():
    from evosprig.core.protocols import ModelResponse, Tool, ToolCall, ToolRegistry
    from evosprig.core.runtime import Runtime
    from evosprig.core.version import compile_agent
    from evosprig.plugins.mock import MockProvider
    from evosprig.sdk import Builder

    value = {"rows": ["start" + "x" * 10000 + "end"]}
    tools = ToolRegistry()
    tools.register(Tool("large.result", "Read table", {"type": "object"}, {}, lambda: value))
    model = MockProvider([ModelResponse(tool_calls=(ToolCall("read-1", "read", {}),)),
                          ModelResponse(text="done")])
    spec = (Builder("bounded-context", {"type": "object"}, {"type": "object"}, spec_version="0.3")
            .model("main", "main").tool("read", "large.result")
            .node("agent", "agent", model="main", tools=["read"],
                  harness={"max_tool_result_chars": 512}, output_schema={"type": "object"})
            .output(answer={"ref": "nodes.agent.output"}).build_spec())
    runtime = Runtime({"main": model}, tools)
    result = await runtime.run(compile_agent(spec), {})
    assert result.status == "succeeded"
    message = model.requests[1].messages[-1]
    assert message["tool_call_id"] == "read-1" and len(message["content"]) <= 512
    assert json.loads(message["content"])["truncated"]
    full = list(runtime.journal._operations.values())
    assert any(item["output"] == value for item in full)
