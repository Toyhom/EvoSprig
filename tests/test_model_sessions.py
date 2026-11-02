import asyncio

import httpx
import pytest

from evosprig.core.protocols import ModelRequest
from evosprig.core.runtime import Runtime
from evosprig.core.version import compile_agent
from evosprig.plugins.openai_compatible import Connection, OpenAICompatibleProvider
from evosprig.sdk import Builder


class CountingProvider(OpenAICompatibleProvider):
    def __init__(self, monkeypatch, handler):
        monkeypatch.setenv("POOL_TEST_KEY", "test")
        super().__init__(
            Connection(base_url="https://example.com", model="test", api_key_env="POOL_TEST_KEY"),
            transport=httpx.MockTransport(handler),
        )
        self.clients = []

    def _client(self):
        client = super()._client()
        self.clients.append(client)
        return client


def response(_):
    return httpx.Response(200, json={
        "choices": [{"message": {"content": "ok"}}],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1},
    })


async def test_runtime_reuses_a_connection_pool_and_export_keeps_the_lifecycle(monkeypatch):
    provider = CountingProvider(monkeypatch, response)
    spec = (Builder("pooled", {}, {}).model("main", "main")
            .node("first", "model", model="main", output_schema={})
            .node("second", "model", model="main", output_schema={})
            .edge("first", "second").build_spec())
    result = await Runtime({"main": provider}).run(compile_agent(spec), {})
    assert result.status == "succeeded"
    assert len(provider.clients) == 1
    assert provider.clients[0].is_closed
    assert provider._shared_client is None
    # The same configured provider can be used in a later run after closure.
    await Runtime({"main": provider}).run(compile_agent(spec), {})
    assert len(provider.clients) == 2
    assert all(client.is_closed for client in provider.clients)


async def test_canceling_one_session_preserves_another_sessions_pool(monkeypatch):
    entered, release = asyncio.Event(), asyncio.Event()
    provider = CountingProvider(monkeypatch, response)

    async def canceled():
        async with provider.session():
            entered.set()
            await release.wait()

    async with provider.session() as client:
        task = asyncio.create_task(canceled())
        await entered.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert not client.is_closed
        assert (await provider.complete(ModelRequest([]))).text == "ok"
        assert len(provider.clients) == 1
    assert client.is_closed
    assert provider._sessions == 0


def test_connection_limits_are_configurable_and_consistent():
    with pytest.raises(ValueError, match="keepalive"):
        Connection(base_url="https://example.com", model="test", api_key_env="KEY",
                   max_connections=2, max_keepalive_connections=3)
