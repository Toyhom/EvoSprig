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


def test_history_projection_preserves_pairing_recent_round_and_original_messages():
    import copy

    from evosprig.core.context_window import project_tool_history
    from evosprig.core.spec import ToolHistoryPolicy

    messages = [{"role": "system", "content": "Keep the instructions."}]
    for i in range(3):
        calls = [{"id": f"{i}-{j}", "function": {"name": "read", "arguments": "{}"}}
                 for j in range(2)]
        messages.append({"role": "assistant", "tool_calls": calls, "content": ""})
        messages.extend({"role": "tool", "tool_call_id": call["id"], "content": "doc" * 3000}
                        for call in calls)
    original = copy.deepcopy(messages)
    projected, stats = project_tool_history(messages, ToolHistoryPolicy(max_chars=24000, keep_recent_rounds=1))
    assert stats['after_chars'] <= 24000 and stats['pruned_results'] > 0
    assert messages == original
    assert projected[-3:] == original[-3:]
    assert projected[0] == original[0]
    assert [m.get('tool_call_id') for m in projected] == [m.get('tool_call_id') for m in original]
    _, protected = project_tool_history(messages, ToolHistoryPolicy(max_chars=512, keep_recent_rounds=3))
    assert not protected['cap_satisfied'] and protected['pruned_results'] == 0


async def test_runtime_prunes_history_only_in_model_requests():
    from evosprig.core.protocols import ModelResponse, Tool, ToolCall, ToolRegistry
    from evosprig.core.runtime import Runtime
    from evosprig.core.version import compile_agent
    from evosprig.plugins.mock import MockProvider
    from evosprig.sdk import Builder

    value = {'rows': 'start' + 'a' * 8000 + 'end'}
    tools = ToolRegistry()
    tools.register(Tool('large.read', 'read', {'type': 'object'}, {}, lambda: value))
    model = MockProvider([ModelResponse(tool_calls=(ToolCall(str(i), 'read', {}),)) for i in range(2)]
                         + [ModelResponse(text='finished')])
    spec = (Builder('history', {}, {}, spec_version='0.3').model('main', 'main').tool('read', 'large.read')
            .node('answer', 'agent', model='main', tools=['read'], output_schema={},
                  harness={'tool_history': {'max_chars': 10000, 'keep_recent_rounds': 1}})
            .output(answer={'ref': 'nodes.answer.output.text'}).execution(max_total_tokens=80000).build_spec())
    runtime = Runtime({'main': model}, tools)
    result = await runtime.run(compile_agent(spec), {})
    assert result.status == 'succeeded'
    observations = [m for m in model.requests[-1].messages if m['role'] == 'tool']
    assert json.loads(observations[0]['content'])['truncated']
    assert json.loads(observations[-1]['content']) == value
    assert all(item['output'] == value for item in runtime.journal._operations.values())
