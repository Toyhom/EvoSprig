import httpx
import pytest

from evosprig.core.protocols import ExecutionError
from evosprig.plugins.http_tools import HTTPToolConfig, http_tool


def config(**kwargs):
    return HTTPToolConfig(
        name="http.lookup",
        description="Lookup a fact",
        endpoint="https://tools.example/lookup",
        input_schema={
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
            "additionalProperties": False,
        },
        output_schema={
            "type": "object",
            "properties": {"answer": {"type": "string"}},
            "required": ["answer"],
            "additionalProperties": False,
        },
        **kwargs,
    )


async def test_http_get_and_schema(monkeypatch):
    monkeypatch.setenv("LOOKUP_TOKEN", "test-credential")

    def handler(request):
        assert request.headers["authorization"] == "Bearer test-credential"
        assert request.url.params["query"] == "two words"
        return httpx.Response(200, json={"answer": "found"})

    tool = http_tool(config(auth_env="LOOKUP_TOKEN"), transport=httpx.MockTransport(handler))
    assert await tool.invoke({"query": "two words"}) == {"answer": "found"}


async def test_http_write_uses_runtime_operation_key():
    def handler(request):
        assert request.headers["idempotency-key"] == "run/node/op"
        assert request.content == b'{"query":"create"}'
        return httpx.Response(200, json={"answer": "saved"})

    tool = http_tool(
        config(method="POST", side_effect="write", idempotent=True),
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(ExecutionError):
        await tool.invoke({"query": "create"})
    assert await tool.invoke({"query": "create"}, operation_id="run/node/op") == {"answer": "saved"}


@pytest.mark.parametrize("status", [301, 401, 429, 500])
async def test_http_failure_never_echoes_upstream_secrets(status):
    tool = http_tool(
        config(),
        transport=httpx.MockTransport(
            lambda request: httpx.Response(status, text="private secret")
        ),
    )
    with pytest.raises(ExecutionError) as caught:
        await tool.invoke({"query": "fact"})
    assert "private" not in str(caught.value)


async def test_response_size_and_configuration():
    tool = http_tool(
        config(max_response_bytes=8),
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json={"answer": "long response"})
        ),
    )
    with pytest.raises(ExecutionError, match="byte limit"):
        await tool.invoke({"query": "fact"})
    for endpoint in [
        "https://user:secret@example.org",
        "https://example.org?api_key=abc",
        "http://outside.example",
    ]:
        with pytest.raises(ValueError):
            HTTPToolConfig.model_validate({**config().model_dump(), "endpoint": endpoint})


async def test_tool_binding_is_frozen_for_resume(tmp_path):
    from evosprig.config import make_tools
    from evosprig.core.journal import Scope
    from evosprig.core.runtime import Runtime
    from evosprig.core.version import compile_agent
    from evosprig.plugins.sqlite_journal import SQLiteJournal
    from evosprig.sdk import Builder

    spec = (
        Builder("test", {"type": "object"}, {"type": "object"}, spec_version="0.2")
        .node("wait", "human", output_schema={"type": "object"})
        .output()
        .build_spec()
    )
    connection = config().model_dump()
    store = SQLiteJournal(tmp_path / "runs.sqlite")
    tools = make_tools(tmp_path, Scope("test"), bindings={"http.lookup": connection})
    first = await Runtime({}, tools, journal=store).run(compile_agent(spec), {}, run_id="frozen")
    assert first.status == "waiting_input"
    store.respond("frozen", "graph/wait", {})
    changed = make_tools(
        tmp_path,
        Scope("test"),
        bindings={"http.lookup": {**connection, "endpoint": "https://different.example/lookup"}},
    )
    with pytest.raises(ExecutionError, match="original tool bindings"):
        await Runtime({}, changed, journal=store).resume("frozen")
    original = make_tools(
        tmp_path, Scope("test"), bindings=store.get("frozen")["metadata"]["tools"]
    )
    assert (await Runtime({}, original, journal=store).resume("frozen")).status == "succeeded"


def test_openapi_import_is_explicit_about_unsupported_contracts():
    from evosprig.plugins.http_tools import from_openapi

    document = {
        "openapi": "3.1.0",
        "paths": {
            "/facts": {
                "get": {
                    "operationId": "lookup",
                    "parameters": [
                        {
                            "in": "query",
                            "name": "query",
                            "required": True,
                            "schema": {"type": "string"},
                        }
                    ],
                    "responses": {
                        "200": {"content": {"application/json": {"schema": {"type": "object"}}}}
                    },
                }
            }
        },
    }
    imported = from_openapi(document, "lookup", base_url="https://service.example")
    assert imported.name == "http.lookup"
    assert imported.endpoint == "https://service.example/facts"
    assert imported.input_schema["required"] == ["query"]
    document["paths"]["/facts"]["get"]["parameters"][0]["in"] = "header"
    with pytest.raises(ValueError, match="only query"):
        from_openapi(document, "lookup", base_url="https://service.example")


@pytest.mark.parametrize("status", [400, 422])
async def test_only_read_only_argument_rejections_produce_safe_feedback(status):
    from evosprig.core.protocols import ToolFeedbackError

    transport = httpx.MockTransport(lambda request: httpx.Response(status, text="private payload"))
    with pytest.raises(ToolFeedbackError, match="rejected the arguments") as caught:
        await http_tool(config(), transport=transport).invoke({"query": "bad"})
    assert "private" not in str(caught.value)
    with pytest.raises(ExecutionError) as write_error:
        await http_tool(config(method="POST", side_effect="write"), transport=transport).invoke(
            {"query": "bad"}, operation_id="write"
        )
    assert not isinstance(write_error.value, ToolFeedbackError)
