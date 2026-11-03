import json

import pytest

from evosprig.core.protocols import ModelResponse, ToolRegistry
from evosprig.core.runtime import Runtime
from evosprig.core.version import compile_snapshot
from evosprig.plugins.mock import MockProvider
from evosprig.sdk import Builder


def candidate(code, retries=1):
    spec = (Builder("checked", {"type": "object"}, {"type": "object"}, spec_version="0.3")
            .model("main", "main").resource("check", "check.py", role="code")
            .node("answer", "model", model="main", inputs={"allowed": {"ref": "input.allowed"}},
                  response_format="json", output_schema={"type": "object"}, output_validator="check",
                  output_errors="feedback", max_output_retries=retries)
            .output(answer={"ref": "nodes.answer.output"}).build_spec())
    return compile_snapshot(spec, {"check": code})


class Answers(MockProvider):
    async def complete(self, request):
        self.requests.append(request)
        return ModelResponse(text=json.dumps({"id": "missing" if len(self.requests) == 1 else "known"}))


CHECK = '''def run(inputs):
    valid = inputs["output"]["id"] in inputs["input"]["allowed"]
    return {"valid": valid, "feedback": "Choose a declared ID"}
'''


async def test_semantic_feedback_repairs_schema_valid_output():
    from evosprig.core.debug import plan_debug

    model = Answers()
    original = candidate(CHECK)
    assert original.spec.used_resources() == {"check"}
    fragment = plan_debug(original.spec, ["answer"])
    assert "check" in fragment.spec.resources
    result = await Runtime({"main": model}, ToolRegistry()).run(
        compile_snapshot(fragment.spec, original.resources), {"project": {"allowed": ["known"]}, "upstream": {}})
    assert result.status == "succeeded", result.error
    assert result.output == {"answer": {"id": "known"}}
    assert len(model.requests) == 2
    assert "Choose a declared ID" in model.requests[1].messages[-1]["content"]
    assert len([event for event in result.events if event["type"] == "model.feedback"]) == 1


async def test_semantic_validation_budget_prevents_downstream_success():
    model = Answers()
    result = await Runtime({"main": model}, ToolRegistry()).run(candidate(CHECK, retries=0), {"allowed": ["known"]})
    assert result.status == "failed"
    assert result.error["code"] == "validation_error"
    assert any(event["type"] == "model.validation" and "Choose a declared ID" in str(event) for event in result.events)
    assert len(model.requests) == 1


@pytest.mark.parametrize("code", [
    'def run(inputs):\n    return {"valid": "true", "feedback": ""}',
    'def run(inputs):\n    return True',
])
async def test_invalid_validator_contract_is_an_application_error(code):
    model = Answers()
    result = await Runtime({"main": model}, ToolRegistry()).run(candidate(code), {"allowed": ["known"]})
    assert result.status == "failed"
    assert result.error["code"] == "execution_error"
    assert len(model.requests) == 1


def test_json_program_schema_feedback_and_external_reference_rejection():
    from evosprig.core.json_program import execute
    from evosprig.core.protocols import ToolFeedbackError

    code = 'def run(inputs):\n    return schema_errors(inputs["schema"], inputs["value"])'
    assert execute(code, {"schema": {"type": "integer", "minimum": 12}, "value": 14}) == []
    assert "minimum" in str(execute(code, {"schema": {"type": "integer", "minimum": 12}, "value": 4}))
    with pytest.raises(ToolFeedbackError, match="local fragments"):
        execute(code, {"schema": {"$ref": "https://example.com/schema"}, "value": {}})
