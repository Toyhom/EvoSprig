from evosprig.core.protocols import ModelResponse, ProviderError, Tool, ToolCall, ToolRegistry
from evosprig.core.runtime import Runtime
from evosprig.core.version import compile_agent
from evosprig.plugins.mock import MockProvider
from evosprig.sdk import Builder


def build(*, retries=2):
    b = Builder("output-repair", {}, {}, spec_version="0.3").model("main", "main")
    b.node(
        "answer",
        "model",
        model="main",
        response_format="json",
        output_errors="feedback",
        max_output_retries=retries,
        output_schema={
            "type": "object",
            "properties": {"answer": {"type": "integer"}},
            "required": ["answer"],
        },
    )
    b.output(answer={"ref": "nodes.answer.output.answer"})
    return compile_agent(b.build_spec())


async def test_invalid_json_and_schema_repair_are_bounded():
    model = MockProvider(
        [
            ModelResponse(text="not json"),
            ModelResponse(text='{"answer":"wrong type"}'),
            ModelResponse(text='{"answer":42}'),
        ]
    )
    result = await Runtime({"main": model}).run(build(), {})
    assert result.status == "succeeded" and result.output == {"answer": 42}
    assert len([e for e in result.events if e["type"] == "model.feedback"]) == 2
    assert "Invalid JSON" in model.requests[1].messages[-1]["content"]
    failed = await Runtime({"main": MockProvider([ModelResponse(text="bad")] * 3)}).run(
        build(retries=1), {}
    )
    assert failed.status == "failed" and failed.usage["model_calls"] == 2


async def test_truncation_retry_retains_unknown_usage_and_does_not_retry_transport():
    class Truncated(MockProvider):
        async def complete(self, request):
            self.requests.append(request)
            if len(self.requests) == 1:
                raise ProviderError("output_limit", "Truncated")
            return ModelResponse(text='{"answer":42}')

    result = await Runtime({"main": Truncated()}).run(build(), {})
    assert result.status == "succeeded" and result.usage["unreported_model_calls"] == 1
    assert result.usage["reserved_tokens"] > 0

    class Broken(MockProvider):
        async def complete(self, request):
            raise ProviderError("transport", "Unavailable")

    failed = await Runtime({"main": Broken()}).run(build(), {})
    assert failed.status == "failed" and failed.usage["model_calls"] == 1


async def test_tool_round_limit_requests_final_answer_without_exposing_tools():
    b = (
        Builder("bounded-tools", {}, {}, spec_version="0.3")
        .model("main", "main")
        .tool("read", "read")
    )
    b.node(
        "agent", "agent", model="main", tools=["read"], max_tool_rounds=1, output_schema={}
    ).output(text={"ref": "nodes.agent.output.text"})
    registry = ToolRegistry()
    registry.register(Tool("read", "Read", {}, {}, lambda: {}))
    model = MockProvider(
        [ModelResponse(tool_calls=(ToolCall("a", "read", {}),)), ModelResponse(text="Finished")]
    )
    result = await Runtime({"main": model}, registry).run(compile_agent(b.build_spec()), {})
    assert result.status == "succeeded"
    assert (
        model.requests[1].tools == []
        and "limit is reached" in model.requests[1].messages[-1]["content"]
    )
