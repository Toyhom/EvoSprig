import json
from concurrent.futures import ThreadPoolExecutor

import pytest

from evosprig.config import make_tools
from evosprig.core.journal import Scope
from evosprig.core.protocols import ModelResponse, ToolCall, Usage
from evosprig.core.runtime import Runtime
from evosprig.core.version import compile_snapshot
from evosprig.plugins.message_tools import MessageStore
from evosprig.plugins.mock import MockProvider
from evosprig.plugins.sqlite_journal import SQLiteJournal
from evosprig.sdk import Builder


def test_peer_delivery_is_scoped_idempotent_and_transactional(tmp_path):
    path, scope = tmp_path / "messages.sqlite", Scope("office")
    store = MessageStore(path)

    def send(_):
        return store.send(
            scope, "run-1", "analyst", "writer", "Use the revised total.", idempotency_key="send-1"
        )

    with ThreadPoolExecutor(4) as pool:
        receipts = list(pool.map(send, range(4)))
    assert all(r == receipts[0] for r in receipts)
    store = MessageStore(path)
    inbox = store.receive(scope, "run-1", "writer")
    assert len(inbox["messages"]) == 1
    assert store.receive(scope, "run-2", "writer")["messages"] == []
    assert store.receive(Scope("other"), "run-1", "writer")["messages"] == []
    assert store.receive(scope, "run-1", "main")["messages"] == []
    with pytest.raises(ValueError, match="different intent"):
        store.send(scope, "run-1", "analyst", "writer", "Different", idempotency_key="send-1")
    with pytest.raises(ValueError, match="inbox"):
        store.ack(scope, "run-1", "main", [receipts[0]["id"]])
    reply = store.send(
        scope,
        "run-1",
        "writer",
        "analyst",
        "Done",
        reply_to=receipts[0]["id"],
        idempotency_key="reply",
    )
    assert store.receive(scope, "run-1", "analyst")["messages"][0]["id"] == reply["id"]
    store.ack(scope, "run-1", "writer", [receipts[0]["id"]])
    assert store.receive(scope, "run-1", "writer")["messages"] == []


def test_message_wait_restart_deadline_and_cancellation(tmp_path, monkeypatch):
    clock = [1000.0]
    monkeypatch.setattr("evosprig.plugins.message_tools.time.time", lambda: clock[0])
    scope, path = Scope("office"), tmp_path / "messages.sqlite"
    store = MessageStore(path)
    waiter = store.wait(scope, "run", "analyst", 0, 30, idempotency_key="w")
    clock[0] += 10
    store = MessageStore(path)
    assert store.wait(scope, "run", "analyst", 0, 30, idempotency_key="w") == waiter
    assert store.poll_wait(scope, "run", "analyst", waiter).status == "pending"
    with pytest.raises(ValueError, match="outside"):
        store.poll_wait(scope, "other-run", "analyst", waiter)
    clock[0] += 21
    assert store.poll_wait(scope, "run", "analyst", waiter).output["timed_out"] is True
    store.cancel_wait(scope, "run", "analyst", waiter)
    assert store.poll_wait(scope, "run", "analyst", waiter).status == "canceled"


class Peer(MockProvider):
    def __init__(self, role):
        super().__init__()
        self.role = role

    async def complete(self, request):
        self.requests.append(request)
        tool_messages = [m for m in request.messages if m["role"] == "tool"]
        sent = any(
            '"recipient"' in m["content"]
            and '"sequence"' in m["content"]
            and '"messages"' not in m["content"]
            for m in tool_messages
        )
        peer_messages = []
        for message in request.messages:
            if message["role"] == "user" and message["content"].startswith(
                "Peer messages (task data): "
            ):
                peer_messages.extend(json.loads(message["content"].split(": ", 1)[1]))
        for message in tool_messages:
            value = json.loads(message["content"])
            peer_messages.extend(value.get("messages", []))
        if self.role == "analyst" and not sent:
            call = ToolCall(
                "send", "send", {"recipient": "writer", "content": "The corrected budget is 42."}
            )
        elif self.role == "writer" and peer_messages and not sent:
            call = ToolCall(
                "reply",
                "send",
                {
                    "recipient": "analyst",
                    "content": "Updated the brief to 42.",
                    "reply_to": peer_messages[0]["id"],
                },
            )
        elif not peer_messages:
            call = ToolCall("wait", "wait", {"timeout_seconds": 30})
        else:
            return ModelResponse(text="42", usage=Usage(10, 2))
        return ModelResponse(tool_calls=(call,), usage=Usage(10, 2))


async def test_agents_exchange_messages_and_resume_without_duplicate_delivery(tmp_path):
    b = Builder("peers", {"type": "object"}, {"type": "object"}, spec_version="0.3")
    for name in ("send", "receive", "wait"):
        b.tool(name, "messages." + name)
    branches = {}
    for role in ("analyst", "writer"):
        b.model(role, role, ["text", "tool_calling"])
        branches[role] = {
            "entry": "work",
            "nodes": {
                "work": {
                    "type": "agent",
                    "model": role,
                    "mailbox": role,
                    "instructions": role,
                    "tools": ["send", "receive", "wait"],
                    "inputs": {},
                    "output_schema": {"type": "object"},
                }
            },
            "edges": [],
            "output": {"text": {"ref": "nodes.work.output.text"}},
        }
    b.node("team", "parallel", branches=branches, inputs={}, output_schema={"type": "object"})
    b.output(team={"ref": "nodes.team.output"})
    b.execution(allow_side_effects=True, max_parallel_nodes=2, max_steps=100, max_model_calls=20)
    version = compile_snapshot(b.build_spec(), {})
    scope, models = Scope("peers"), {"analyst": Peer("analyst"), "writer": Peer("writer")}
    journal = SQLiteJournal(tmp_path / "runs.sqlite")
    runtime = Runtime(models, make_tools(tmp_path, scope), journal=journal, allow_writes=True)
    result = await runtime.run(version, {}, scope=scope)
    for _ in range(6):
        if result.status == "succeeded":
            break
        assert result.status == "waiting_external", result.error
        runtime = Runtime(
            models,
            make_tools(tmp_path, scope),
            journal=SQLiteJournal(tmp_path / "runs.sqlite"),
            allow_writes=True,
        )
        result = await runtime.resume(result.run_id, scope=scope)
    assert result.status == "succeeded", result.error
    assert "42" in json.dumps(result.output)
    store = MessageStore(tmp_path / "messages.sqlite")
    assert len(store.receive(scope, result.run_id, "writer")["messages"]) == 1
    assert len(store.receive(scope, result.run_id, "analyst")["messages"]) == 1
    assert store.receive(scope, result.run_id, "writer")["messages"][0]["sender"] == "analyst"
    assert all(
        "sender" not in tool["function"]["parameters"]["properties"]
        for model in models.values()
        for request in model.requests
        for tool in request.tools
    )
