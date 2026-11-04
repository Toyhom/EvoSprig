import json

import httpx
import pytest

from evosprig.core.protocols import ModelRequest, ProviderError
from evosprig.plugins.openai_compatible import Connection, OpenAICompatibleProvider


@pytest.fixture
def connection(monkeypatch):
    monkeypatch.setenv("TEST_MODEL_KEY", "test-value")
    return Connection(
        base_url="https://model.example/v1", model="test-model", api_key_env="TEST_MODEL_KEY"
    )


async def test_chat_contract_and_secret_reference(connection):
    async def handle(request):
        assert request.url == "https://model.example/v1/chat/completions"
        assert request.headers["authorization"] == "Bearer test-value"
        body = json.loads(request.content)
        assert body["max_tokens"] == 32
        assert "api_key" not in body
        return httpx.Response(
            200,
            json={
                "model": "test-model-1",
                "choices": [{"message": {"content": "ok"}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 2},
            },
        )

    model = OpenAICompatibleProvider(connection, transport=httpx.MockTransport(handle))
    response = await model.complete(
        ModelRequest([{"role": "user", "content": "hi"}], max_output_tokens=32)
    )
    assert response.text == "ok"
    assert response.model == "test-model-1"
    assert response.usage.total_tokens == 12
    assert "test-value" not in connection.model_dump_json()


async def test_json_and_tool_call_contract(connection):
    def handle(request):
        body = json.loads(request.content)
        assert body["response_format"] == {"type": "json_object"}
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "abc",
                                    "function": {"name": "add", "arguments": '{"a":1,"b":2}'},
                                }
                            ],
                        }
                    }
                ],
                "usage": {"prompt_tokens": 5, "completion_tokens": 4},
            },
        )

    result = await OpenAICompatibleProvider(
        connection, transport=httpx.MockTransport(handle)
    ).complete(ModelRequest([], json_output=True))
    assert result.tool_calls[0].id == "abc"
    assert result.tool_calls[0].arguments == {"a": 1, "b": 2}


async def test_long_local_generations_use_the_configured_timeout(connection):
    config = Connection(**{**connection.model_dump(), "timeout_seconds": 1200})

    def handle(request):
        assert request.extensions["timeout"]["read"] == 1200
        return httpx.Response(200, json={"choices": [{"message": {"content": "done"}}],
                                        "usage": {"prompt_tokens": 1, "completion_tokens": 1}})

    response = await OpenAICompatibleProvider(config, transport=httpx.MockTransport(handle)).complete(ModelRequest([]))
    assert response.text == "done"
    with pytest.raises(ValueError):
        Connection(**{**connection.model_dump(), "timeout_seconds": 0})


@pytest.mark.parametrize(
    "status,code",
    [
        (401, "authentication"),
        (403, "authentication"),
        (429, "rate_limit"),
        (500, "upstream"),
        (302, "upstream"),
    ],
)
async def test_errors_are_sanitized_and_never_retried(connection, status, code):
    requests = []

    def handle(request):
        requests.append(request)
        return httpx.Response(
            status,
            text="private provider body test-value",
            headers={"Location": "https://untrusted.example"},
        )

    with pytest.raises(ProviderError) as caught:
        await OpenAICompatibleProvider(connection, transport=httpx.MockTransport(handle)).complete(
            ModelRequest([])
        )
    assert caught.value.code == code
    assert "test-value" not in str(caught.value)
    assert len(requests) == 1


async def test_stream_filters_private_fields_and_tracks_usage(connection):
    body = 'data: {"choices":[{"delta":{"reasoning_content":"private", "content":"Hi"}}]}\n\n'
    body += 'data: {"choices":[],"usage":{"prompt_tokens":2,"completion_tokens":1,"total_tokens":3}}\n\n'
    body += "data: [DONE]\n\n"
    model = OpenAICompatibleProvider(
        connection, transport=httpx.MockTransport(lambda _: httpx.Response(200, text=body))
    )
    chunks = [chunk async for chunk in model.stream(ModelRequest([]))]
    assert chunks[0] == {"type": "text", "text": "Hi"}
    assert chunks[-1]["usage"]["total_tokens"] == 3
    assert "private" not in json.dumps(chunks)


async def test_missing_key_stops_before_network(connection, monkeypatch):
    monkeypatch.delenv("TEST_MODEL_KEY")

    def forbidden(request):
        pytest.fail("network should not be reached")

    with pytest.raises(ProviderError, match="environment"):
        await OpenAICompatibleProvider(
            connection, transport=httpx.MockTransport(forbidden)
        ).complete(ModelRequest([]))


@pytest.mark.parametrize(
    "url",
    ["https://secret:pass@example.com", "http://example.com", "https://example.com?api_key=secret"],
)
def test_endpoint_validation(url):
    with pytest.raises(ValueError):
        Connection(base_url=url, model="test", api_key_env="KEY")


def test_vllm_template_option_is_explicit_and_validated():
    config = Connection(
        base_url="http://localhost:8000/v1",
        model="qwen3",
        api_key_env="LOCAL_KEY",
        options={"chat_template_kwargs": {"enable_thinking": False}},
    )
    payload = OpenAICompatibleProvider(config)._payload(ModelRequest([]))
    assert payload["chat_template_kwargs"] == {"enable_thinking": False}
    with pytest.raises(ValueError):
        Connection(
            base_url=config.base_url,
            model=config.model,
            api_key_env="LOCAL_KEY",
            options={"chat_template_kwargs": {"enable_thinking": "false"}},
        )


async def test_tool_loop_can_defer_json_mode_until_tools_are_exhausted(connection):
    from evosprig.core.protocols import Tool, ToolRegistry
    from evosprig.core.runtime import Runtime
    from evosprig.core.version import compile_agent
    from evosprig.sdk import Builder

    calls = []
    def handle(request):
        body = json.loads(request.content)
        calls.append(body)
        if body.get("tools"):
            # Qwen/vLLM emits tool-call markup that a JSON grammar would forbid.
            assert "response_format" not in body
            message = {"content": None, "tool_calls": [{"id": "lookup1", "type": "function",
                       "function": {"name": "lookup", "arguments": "{}"}}]}
        else:
            assert body["response_format"] == {"type": "json_object"}
            observation = next(message for message in body["messages"] if message["role"] == "tool")
            assert json.loads(observation["content"]) == {"value": "from tool"}
            message = {"content": '{"value":"from tool"}'}
        return httpx.Response(200, json={"choices": [{"message": message}],
                                         "usage": {"prompt_tokens": 50, "completion_tokens": 10}})

    config = connection.model_copy(update={"json_mode": "without_tools"})
    provider = OpenAICompatibleProvider(config, transport=httpx.MockTransport(handle))
    tools = ToolRegistry()
    tools.register(Tool("lookup", "Read a value", {"type": "object"}, {"type": "object"}, lambda: {"value": "from tool"}))
    builder = (Builder("json-tools", {"type": "object"}, {"type": "object"}, spec_version="0.3")
               .model("main", "main").tool("lookup", "lookup")
               .node("answer", "agent", model="main", tools=["lookup"], response_format="json",
                     max_tool_rounds=1, output_schema={"type": "object", "required": ["value"]})
               .output(result={"ref": "nodes.answer.output"}))
    result = await Runtime({"main": provider}, tools).run(compile_agent(builder.build_spec()), {})
    assert result.status == "succeeded", result.error
    assert result.output == {"result": {"value": "from tool"}}
    assert len(calls) == 2
    assert len([event for event in result.events if event["type"] == "tool.result"]) == 1


def test_provider_json_modes_preserve_existing_default(connection):
    request = ModelRequest([], tools=[{"type": "function"}], json_output=True)
    assert OpenAICompatibleProvider(connection)._payload(request)["response_format"] == {"type": "json_object"}
    for mode in ["without_tools", "off"]:
        provider = OpenAICompatibleProvider(connection.model_copy(update={"json_mode": mode}))
        assert "response_format" not in provider._payload(request)
    provider = OpenAICompatibleProvider(connection.model_copy(update={"json_mode": "off"}))
    assert "response_format" not in provider._payload(ModelRequest([], json_output=True))


async def test_saved_connection_defaults_resume_without_allowing_behavior_changes(connection, tmp_path):
    from evosprig.core.protocols import ExecutionError
    from evosprig.core.runtime import Runtime
    from evosprig.core.version import compile_agent
    from evosprig.plugins.sqlite_journal import SQLiteJournal
    from evosprig.sdk import Builder

    async def handle(request):
        assert json.loads(request.content)["response_format"] == {"type": "json_object"}
        return httpx.Response(200, json={"choices": [{"message": {"role": "assistant", "content": '{"answer":"resumed"}'},
                                                     "finish_reason": "stop"}],
                                        "usage": {"prompt_tokens": 5, "completion_tokens": 5}})

    def provider(config):
        return OpenAICompatibleProvider(config, transport=httpx.MockTransport(handle))

    spec = (Builder("old-connection", {"type": "object"}, {"type": "object"})
            .model("main", "main").node("answer", "model", model="main", response_format="json",
                                        inputs={}, output_schema={"type": "object"})
            .output(answer={"ref": "nodes.answer.output"}).build_spec())
    journal = SQLiteJournal(tmp_path / "runs.sqlite")
    runtime = Runtime({"main": provider(connection)}, journal=journal)
    run_id = runtime.create_run(compile_agent(spec), {})
    with journal._transaction() as db:
        record = journal._read(db, run_id)
        del record["metadata"]["models"]["main"]["connection"]["json_mode"]
        journal._write(db, record)
    changed = Runtime({"main": provider(connection.model_copy(update={"json_mode": "off"}))}, journal=journal)
    with pytest.raises(ExecutionError, match="original model bindings"):
        await changed.resume(run_id)
    result = await runtime.resume(run_id)
    assert result.status == "succeeded", result.error
    assert result.output == {"answer": {"answer": "resumed"}}
    assert "json_mode" not in journal.get(run_id)["metadata"]["models"]["main"]["connection"]
