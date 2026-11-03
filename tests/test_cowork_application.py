"""Native team execution, human edits and a delayed continuation across restarts."""

import json
from pathlib import Path

from evosprig.config import make_tools
from evosprig.core.journal import Scope
from evosprig.core.protocols import ModelResponse, ToolCall
from evosprig.core.runtime import Runtime
from evosprig.core.spec import load_spec
from evosprig.core.version import compile_agent
from evosprig.plugins.mock import MockProvider
from evosprig.plugins.sqlite_journal import SQLiteJournal
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
        if "Read each completed team document" in prompt:
            return ModelResponse(text=json.dumps({"content": "Draft brief"}))
        if request.messages[-1]["role"] != "tool":
            return ModelResponse(
                tool_calls=(ToolCall("read", "read", {"name": "deliverables/brief.md"}),)
            )
        return ModelResponse(text="Next: " + json.loads(request.messages[-1]["content"])["content"])


async def test_native_cowork_resumes_and_reads_human_edits(tmp_path, monkeypatch):
    root = Path(__file__).resolve().parents[1] / "examples/cowork"
    spec = load_spec(root / "agent.yaml")
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
