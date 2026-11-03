"""Native team execution, human edits and a delayed continuation across restarts."""

import json
from pathlib import Path

import pytest

from evosprig.config import make_tools
from evosprig.core.journal import Scope
from evosprig.core.memory import MemoryScope
from evosprig.core.protocols import ModelResponse, ToolCall
from evosprig.core.runtime import Runtime
from evosprig.core.spec import load_spec
from evosprig.core.version import compile_agent
from evosprig.plugins.mock import MockProvider
from evosprig.plugins.sqlite_journal import SQLiteJournal
from evosprig.plugins.sqlite_memory import SQLiteMemory
from evosprig.plugins.workspace_tools import WorkspaceStore


class OfficeModel(MockProvider):
    async def complete(self, request):
        self.requests.append(request)
        prompt = request.messages[0]["content"]
        inputs = json.loads(request.messages[1]["content"])
        if "You lead a small office team" in prompt:
            return ModelResponse(
                text=json.dumps(
                    {
                        "title": "Pilot",
                        "tasks": [
                            {"role": "Analyst", "task": "Budget", "document": "team/budget.md"},
                            {"role": "Writer", "task": "Email", "document": "team/email.md"},
                        ],
                    }
                )
            )
        if "Complete your assigned work" in prompt:
            return ModelResponse(
                text=json.dumps({"content": "Draft for " + inputs["assignment"]["role"]})
            )
        if "Save the supplied draft" in prompt:
            if request.messages[-1]["role"] != "tool":
                return ModelResponse(
                    tool_calls=(ToolCall("read", "read", {"name": inputs["name"]}),)
                )
            result = json.loads(request.messages[-1]["content"])
            if request.messages[-1]["tool_call_id"] == "read":
                return ModelResponse(
                    tool_calls=(
                        ToolCall(
                            "write",
                            "write",
                            {
                                "name": inputs["name"],
                                "content": inputs["draft"],
                                "expected_revision": result["revision"],
                            },
                        ),
                    )
                )
            return ModelResponse(
                text=json.dumps(
                    {
                        "name": result["name"],
                        "revision": result["revision"],
                        "summary": "Saved team work",
                    }
                )
            )
        if "Extract a reusable lesson" in prompt:
            return ModelResponse(
                text=json.dumps({"memory": "Keep the agreed launch date in every document."})
            )
        if "Read each completed team document" in prompt:
            return ModelResponse(
                text=json.dumps({"content": "Draft brief", "accepted": True, "tasks": []})
            )
        if request.messages[-1]["role"] != "tool":
            return ModelResponse(
                tool_calls=(ToolCall("read", "read", {"name": "deliverables/brief.md"}),)
            )
        return ModelResponse(text="Next: " + json.loads(request.messages[-1]["content"])["content"])


@pytest.mark.parametrize("file", ["agent.yaml", "rsi-agent.yaml"])
async def test_native_cowork_resumes_and_reads_human_edits(tmp_path, monkeypatch, file):
    root = Path(__file__).resolve().parents[1] / "examples/cowork"
    spec = load_spec(root / file)
    version = compile_agent(spec, root)
    scope = Scope(spec.id)
    model = OfficeModel()
    journal = SQLiteJournal(tmp_path / "runs.sqlite")

    def runtime():
        return Runtime(
            {"main": model},
            make_tools(tmp_path, scope),
            journal=SQLiteJournal(journal.path),
            allow_writes=True,
        )

    run = await runtime().run(version, {"request": "Create a launch pack", "follow_up_seconds": 60})
    assert run.status == "waiting_input", run.error
    assert len(WorkspaceStore(tmp_path / "documents.sqlite").list(scope)["documents"]) == 2
    journal.respond(run.run_id, run.waiting[0]["path"], {"content": "User-approved launch plan"})
    run = await runtime().resume(run.run_id)
    assert run.status == "waiting_external", run.error
    if file == "rsi-agent.yaml":
        lessons = SQLiteMemory(tmp_path / "memory.sqlite").search(
            MemoryScope(scope), "agreed launch date"
        )
        assert any("Keep the agreed launch date" in item["content"] for item in lessons)
    store = WorkspaceStore(tmp_path / "documents.sqlite")
    item = store.read(scope, "deliverables/brief.md")
    store.write(
        scope,
        item["name"],
        "New launch date: Monday",
        item["revision"],
        idempotency_key="human-edit",
    )
    import time

    now = time.time() + 61
    monkeypatch.setattr("evosprig.plugins.workspace_tools.time.time", lambda: now)
    run = await runtime().resume(run.run_id)
    assert run.status == "succeeded", run.error
    assert run.output["follow_up"] == "Next: New launch date: Monday"
    assert store.history(scope, item["name"])["revisions"][0]["revision"] == 2
    before = len(model.requests)
    assert (await runtime().resume(run.run_id)).status == "succeeded"
    assert len(model.requests) == before


async def test_main_redelegates_only_rejected_work(tmp_path):
    class ReviewingModel(OfficeModel):
        waves = 0

        async def complete(self, request):
            if "Read each completed team document" in request.messages[0]["content"]:
                self.waves += 1
                if self.waves == 1:
                    return ModelResponse(
                        text=json.dumps(
                            {
                                "content": "Budget needs correction",
                                "accepted": False,
                                "tasks": [
                                    {
                                        "role": "Analyst",
                                        "task": "Fix the total",
                                        "document": "team/budget.md",
                                    }
                                ],
                            }
                        )
                    )
            return await super().complete(request)

    root = Path(__file__).resolve().parents[1] / "examples/cowork"
    spec = load_spec(root / "agent.yaml")
    model = ReviewingModel()
    scope = Scope(spec.id)
    result = await Runtime(
        {"main": model},
        make_tools(tmp_path, scope),
        allow_writes=True,
        journal=SQLiteJournal(tmp_path / "runs.sqlite"),
    ).run(compile_agent(spec, root), {"request": "Prepare a budget and email"})
    assert result.status == "waiting_input", result.error
    assert model.waves == 2
    store = WorkspaceStore(tmp_path / "documents.sqlite")
    assert store.read(scope, "team/budget.md")["revision"] == 2
    assert store.read(scope, "team/email.md")["revision"] == 1
    assert result.waiting[0]["input"]["team"]["accepted"] is True
