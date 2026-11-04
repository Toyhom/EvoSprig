import json

import pytest

from evosprig.core.protocols import ModelResponse, Tool, ToolCall, ToolFeedbackError, ToolRegistry
from evosprig.core.runtime import Runtime
from evosprig.core.version import compile_agent
from evosprig.plugins.mock import MockProvider
from evosprig.plugins.sqlite_journal import SQLiteJournal
from evosprig.sdk import Builder


def agent(tool, *, feedback=True):
    spec = (
        Builder("feedback", {}, {"type": "object"}, spec_version="0.3")
        .model("main", "main", ["text", "tool_calling"])
        .tool("action", tool.name)
        .node(
            "agent",
            "agent",
            model="main",
            tools=["action"],
            tool_errors="feedback" if feedback else "raise",
            output_schema={"type": "object"},
        )
        .output(text={"ref": "nodes.agent.output.text"})
        .execution(allow_side_effects=True)
        .build_spec()
    )
    registry = ToolRegistry()
    registry.register(tool)
    return compile_agent(spec), registry


@pytest.mark.parametrize("feedback", [False, True])
async def test_invalid_arguments_are_corrected_only_when_enabled(feedback):
    effects = []

    def invoke(amount):
        effects.append(amount)
        return {"amount": amount}

    tool = Tool(
        "example.read",
        "Read",
        {"type": "object", "properties": {"amount": {"type": "integer"}}, "required": ["amount"]},
        {"type": "object"},
        invoke,
    )
    version, registry = agent(tool, feedback=feedback)
    model = MockProvider(
        [
            ModelResponse(tool_calls=(ToolCall("bad", "action", {"amount": "invalid"}),)),
            ModelResponse(tool_calls=(ToolCall("fixed", "action", {"amount": 3}),)),
            ModelResponse(text="Done"),
        ]
    )
    result = await Runtime({"main": model}, registry).run(version, {})
    if feedback:
        assert result.status == "succeeded"
        assert effects == [3]
        assert (
            json.loads(model.requests[1].messages[-1]["content"])["error"]["code"]
            == "invalid_arguments"
        )
    else:
        assert result.status == "failed" and effects == []
        assert len(model.requests) == 1
        assert "ValidationError" in result.error["message"]


async def test_write_failure_still_requires_reconciliation(tmp_path):
    writes = []

    def write():
        writes.append("possibly committed")
        raise ToolFeedbackError("unsafe_retry", "Do not automatically retry this write")

    version, registry = agent(Tool("example.write", "Write", {}, {}, write, side_effect="write"))
    model = MockProvider(
        [
            ModelResponse(tool_calls=(ToolCall("write", "action", {}),)),
            ModelResponse(text="Confirmed"),
        ]
    )
    journal = SQLiteJournal(tmp_path / "runs.sqlite")
    runtime = Runtime({"main": model}, registry, journal=journal, allow_writes=True)
    result = await runtime.run(version, {})
    assert result.status == "waiting_input"
    assert result.waiting[0]["kind"] == "operation_unknown"
    assert len(model.requests) == len(writes) == 1
    journal.respond(result.run_id, result.waiting[0]["path"], {"receipt": "verified"})
    result = await runtime.resume(result.run_id)
    assert result.status == "succeeded" and len(writes) == 1
    assert not any(event["type"] == "tool.feedback" for event in result.events)


@pytest.mark.parametrize("declared", [False, True])
async def test_deterministic_nodes_show_declared_feedback_and_hide_unexpected_errors(declared):
    def invoke():
        if declared:
            raise ToolFeedbackError("invalid_option", "Choose a sampler listed in the render profile.")
        raise RuntimeError("private service credentials")

    registry = ToolRegistry()
    registry.register(Tool("example.options", "Options", {}, {}, invoke))
    spec = (Builder("direct-feedback", {}, {}, spec_version="0.3")
            .tool("options", "example.options")
            .node("options", "tool", tool="options", output_schema={})
            .build_spec())
    result = await Runtime({}, registry).run(compile_agent(spec), {})
    assert result.status == "failed"
    assert result.error["node_id"] == "graph/options"
    if declared:
        assert result.error["code"] == "invalid_option"
        assert result.error["message"] == "Choose a sampler listed in the render profile."
    else:
        assert "private service credentials" not in json.dumps(result.error)


@pytest.mark.parametrize("external", [False, True])
async def test_write_rejected_before_commit_can_be_corrected(tmp_path, external):
    from evosprig.core.protocols import ExternalStatus, ExternalTool, ToolRejectedError

    writes = []

    def write(revision):
        if revision != 2:
            raise ToolRejectedError("revision_conflict", "Read revision 2 before retrying")
        writes.append(revision)
        return {"revision": 3}

    action = Tool(
            "example.cas",
            "Write",
            {
                "type": "object",
                "properties": {"revision": {"type": "integer"}},
                "required": ["revision"],
            },
            {"type": "object"},
            write,
            side_effect="write",
        )
    if external:
        async def submit(revision, *, idempotency_key):
            write(revision)
            return "accepted"

        async def poll(job_id):
            assert job_id == "accepted"
            return ExternalStatus("succeeded", {"revision": 3})

        action = ExternalTool(action.name, action.description, action.input_schema, action.output_schema, submit, poll)
    version, registry = agent(action)
    model = MockProvider(
        [
            ModelResponse(tool_calls=(ToolCall("stale", "action", {"revision": 1}),)),
            ModelResponse(tool_calls=(ToolCall("merged", "action", {"revision": 2}),)),
            ModelResponse(text="Saved"),
        ]
    )
    journal = SQLiteJournal(tmp_path / "runs.sqlite")
    result = await Runtime({"main": model}, registry, journal=journal, allow_writes=True).run(
        version, {}
    )
    assert result.status == "succeeded"
    assert writes == [2]
    assert any(op["status"] == "rejected" for op in journal.operations(result.run_id))
