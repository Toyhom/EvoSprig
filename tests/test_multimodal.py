import json

import httpx
import pytest

from evosprig.core.multimodal import input_reservation, user_content
from evosprig.core.protocols import ExecutionError, Tool, ToolRegistry
from evosprig.core.runtime import Runtime
from evosprig.core.version import compile_agent
from evosprig.plugins.openai_compatible import Connection, OpenAICompatibleProvider
from evosprig.sdk import Builder

IMAGE = "data:image/png;base64,aW1hZ2U="


async def test_vision_node_sends_images_as_content_parts(monkeypatch):
    monkeypatch.setenv("VISION_TEST_KEY", "test")
    def handle(request):
        body = json.loads(request.content)
        content = body["messages"][1]["content"]
        assert content[1] == {"type": "image_url", "image_url": {"url": IMAGE}}
        assert IMAGE not in content[0]["text"]
        assert body["max_completion_tokens"] == 128
        assert "max_tokens" not in body and "temperature" not in body and "top_p" not in body
        return httpx.Response(200, json={"choices": [{"message": {"content": "A frame"}}],
                                        "usage": {"prompt_tokens": 200, "completion_tokens": 4}})
    provider = OpenAICompatibleProvider(Connection(
        base_url="https://example.com/v1", model="kimi-k3.1-pro", api_key_env="VISION_TEST_KEY",
        capabilities=["text", "vision"], token_limit_field="max_completion_tokens",
        send_sampling_parameters=False, options={"reasoning_effort": "low"}
    ), transport=httpx.MockTransport(handle))
    spec = (Builder("vision", {}, {}).model("main", "main", ["text", "vision"])
            .node("review", "model", model="main", inputs={"frame": {"ref": "input.frame"}},
                  image_inputs=["frame"], output_schema={})
            .output(review={"ref": "nodes.review.output"})
            .execution(max_output_tokens=128, max_total_tokens=8192).build_spec())
    result = await Runtime({"main": provider}).run(compile_agent(spec), {"frame": IMAGE})
    assert result.status == "succeeded"
    assert result.output["review"]["text"] == "A frame"


def test_images_do_not_consume_base64_length_in_token_reservations():
    short = [{"role": "user", "content": user_content({"image": IMAGE}, ["image"])}]
    long_image = "data:image/png;base64," + "YWJj" * 100000
    long = [{"role": "user", "content": user_content({"image": long_image}, ["image"])}]
    assert input_reservation(short, []) == input_reservation(long, [])
    assert input_reservation(short, [], 8192) - input_reservation(short, []) == 4096


@pytest.mark.parametrize("uri", ["file:///etc/passwd", "http://localhost/private", "data:text/plain;base64,YQ==", "data:image/png;base64,???"])
def test_images_cannot_implicitly_read_files_or_local_services(uri):
    with pytest.raises(ExecutionError):
        user_content({"image": uri}, ["image"])


async def test_complete_assistant_message_survives_tool_round(monkeypatch):
    monkeypatch.setenv("VISION_TEST_KEY", "test")
    original = {"role": "assistant", "content": None, "reasoning_content": "opaque-provider-state",
                "tool_calls": [{"id": "one", "type": "function", "function": {"name": "lookup", "arguments": "{}"}}]}
    calls = []
    def handle(request):
        body = json.loads(request.content)
        calls.append(body)
        if len(calls) == 1:
            message = original
        else:
            assert body["messages"][2] == original
            assert body["messages"][3]["tool_call_id"] == "one"
            message = {"content": "Done"}
        return httpx.Response(200, json={"choices": [{"message": message}],
                                        "usage": {"prompt_tokens": 20, "completion_tokens": 8}})
    provider = OpenAICompatibleProvider(Connection(
        base_url="https://example.com/v1", model="kimi-k3.1-pro", api_key_env="VISION_TEST_KEY"
    ), transport=httpx.MockTransport(handle))
    tools = ToolRegistry()
    tools.register(Tool("lookup", "Look up a fact", {}, {}, lambda: {"value": 1}))
    spec = (Builder("roundtrip", {}, {}).model("main", "main", ["text", "tool_calling"])
            .tool("lookup", "lookup").node("work", "agent", model="main", tools=["lookup"], output_schema={})
            .output(answer={"ref": "nodes.work.output"}).build_spec())
    result = await Runtime({"main": provider}, tools).run(compile_agent(spec), {})
    assert result.status == "succeeded"
    assert "opaque-provider-state" not in json.dumps(result.output)


def test_vision_capability_is_required():
    with pytest.raises(ValueError, match="vision-capable"):
        (Builder("bad", {}, {}).model("main", "main")
         .node("work", "model", model="main", inputs={"frame": {"value": IMAGE}},
               image_inputs=["frame"], output_schema={}).build_spec())
