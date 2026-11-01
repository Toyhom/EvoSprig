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
