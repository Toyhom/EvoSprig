from evosprig.core.protocols import ModelResponse, ProviderError, Tool, ToolCall, ToolRegistry
from evosprig.core.runtime import Runtime
from evosprig.core.version import compile_agent
from evosprig.plugins.mock import MockProvider
from evosprig.sdk import Builder


async def test_schema_repair_reports_multiple_fields_with_bounded_feedback():
    import json

    fields = {f"field_{index}": {"type": "integer"} for index in range(12)}
    b = Builder("repair-fields", {}, {}, spec_version="0.3").model("main", "main")
    b.node("answer", "model", model="main", response_format="json", output_errors="feedback",
           max_output_retries=1, output_schema={"type": "object", "properties": fields, "required": list(fields)})
    b.output(answer={"ref": "nodes.answer.output"})
    model = MockProvider([ModelResponse(text=json.dumps({key: "private-invalid-value" for key in fields})),
                          ModelResponse(text=json.dumps({key: index for index, key in enumerate(fields)}))])
    result = await Runtime({"main": model}).run(compile_agent(b.build_spec()), {})
    assert result.status == "succeeded" and result.usage["model_calls"] == 2
    message = model.requests[1].messages[-1]["content"]
    assert all(f"['{name}']" in message for name in sorted(fields)[:8])
    assert all(f"['{name}']" not in message for name in sorted(fields)[8:])
    assert message.count("Output does not satisfy") == 8
    assert "private-invalid-value" not in message


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


async def test_node_output_limit_overrides_default_but_respects_total_budget():
    b = Builder("node-limits", {}, {}, spec_version="0.3").model("main", "main")
    b.node("short", "model", model="main", output_schema={})
    b.node("long", "model", model="main", max_output_tokens=2048, output_schema={})
    b.edge("short", "long").output(text={"ref": "nodes.long.output.text"})
    b.execution(max_output_tokens=256, max_total_tokens=8192)
    model = MockProvider([ModelResponse(text="a"), ModelResponse(text="b")])
    result = await Runtime({"main": model}).run(compile_agent(b.build_spec()), {})
    assert result.status == "succeeded"
    assert [r.max_output_tokens for r in model.requests] == [256, 2048]
    old_hash = b.build_spec().spec_hash
    b.data["graph"]["nodes"]["short"]["max_output_tokens"] = None
    assert b.build_spec().spec_hash == old_hash


async def test_truncated_response_with_usage_settles_run_and_study_budgets():
    from evosprig.core.protocols import Usage
    from evosprig.evaluation.budget import BudgetedProvider, BudgetMeter, ExperimentBudget
    from evosprig.plugins.openai_compatible import OpenAICompatibleProvider

    class Truncated(MockProvider):
        async def complete(self, request):
            self.requests.append(request)
            if len(self.requests) == 1:
                return OpenAICompatibleProvider._parse(
                    {
                        "choices": [{"finish_reason": "length", "message": {"content": "partial"}}],
                        "usage": {"prompt_tokens": 40, "completion_tokens": 20},
                    }
                )
            return ModelResponse(text='{"answer":42}', usage=Usage(45, 5))

    meter = BudgetMeter(ExperimentBudget())
    result = await Runtime({"main": BudgetedProvider(Truncated(), meter)}).run(build(), {})
    assert result.status == "succeeded"
    for usage in [result.usage, meter.snapshot()]:
        assert usage["reserved_tokens"] == 0
        assert usage["unreported_model_calls"] == 0
        assert usage["input_tokens"] == 85
        assert usage["output_tokens"] == 25
    assert any(e["type"] == "model.rejected" for e in result.events)
