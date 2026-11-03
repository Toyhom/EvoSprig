"""Durable peer mailboxes, idempotent delivery and resumable waits."""

import json
import time

from evosprig.core.protocols import ExternalStatus, ExternalTool, Tool, ToolRejectedError
from evosprig.core.spec import IDENTIFIER, canonical_json, digest
from evosprig.core.tool_context import caller

from .workspace_tools import WorkspaceStore, obj

MESSAGE_TOOL_NAMES = frozenset(
    {"messages.send", "messages.receive", "messages.ack", "messages.wait"}
)


class MessageStore(WorkspaceStore):
    def __init__(self, path):
        super().__init__(path)
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS peer_messages (
                    seq INTEGER PRIMARY KEY AUTOINCREMENT,
                    scope TEXT NOT NULL, run_id TEXT NOT NULL, id TEXT NOT NULL,
                    sender TEXT NOT NULL, recipient TEXT NOT NULL, body TEXT NOT NULL,
                    acknowledged INTEGER NOT NULL DEFAULT 0,
                    UNIQUE(scope,run_id,id));
                CREATE INDEX IF NOT EXISTS peer_inbox ON peer_messages(scope,run_id,recipient,seq);
                CREATE TABLE IF NOT EXISTS peer_waits (
                    scope TEXT, id TEXT, run_id TEXT, recipient TEXT,
                    intent TEXT, deadline REAL, canceled INTEGER DEFAULT 0,
                    PRIMARY KEY(scope,id));
            """)

    @staticmethod
    def identity(value):
        if not isinstance(value, str) or not IDENTIFIER.fullmatch(value):
            raise ValueError("mailbox must be an identifier")

    def send(self, scope, run_id, sender, recipient, content, *, reply_to=None, idempotency_key):
        self.identity(sender)
        self.identity(recipient)
        if not isinstance(content, str) or not content.strip() or len(content) > 12000:
            raise ValueError("message content must contain 1–12000 characters")
        intent = {
            "sender": sender,
            "recipient": recipient,
            "content": content,
            "reply_to": reply_to,
        }
        identifier = digest([scope.key, run_id, idempotency_key])
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT seq,body FROM peer_messages WHERE scope=? AND run_id=? AND id=?",
                (scope.key, run_id, identifier),
            ).fetchone()
            if row:
                if json.loads(row[1]) != intent:
                    raise ValueError("message operation already has a different intent")
                return {"id": identifier, "sequence": row[0], "recipient": recipient}
            if reply_to is not None:
                original = db.execute(
                    "SELECT sender,recipient FROM peer_messages WHERE scope=? AND run_id=? AND id=?",
                    (scope.key, run_id, reply_to),
                ).fetchone()
                if not original or original != (recipient, sender):
                    raise ValueError("reply must address the sender of a received message")
            cursor = db.execute(
                "INSERT INTO peer_messages(scope,run_id,id,sender,recipient,body) VALUES(?,?,?,?,?,?)",
                (scope.key, run_id, identifier, sender, recipient, canonical_json(intent)),
            )
            return {"id": identifier, "sequence": cursor.lastrowid, "recipient": recipient}

    def receive(self, scope, run_id, recipient, *, after=0, limit=20):
        self.identity(recipient)
        if type(after) is not int or after < 0 or type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("invalid inbox cursor or limit")
        with self.connect() as db:
            rows = db.execute(
                "SELECT seq,id,body FROM peer_messages WHERE scope=? AND run_id=? AND recipient=? AND seq>? AND acknowledged=0 ORDER BY seq LIMIT ?",
                (scope.key, run_id, recipient, after, limit),
            ).fetchall()
        messages = [
            {**json.loads(body), "id": identifier, "sequence": seq}
            for seq, identifier, body in rows
        ]
        return {"messages": messages, "cursor": rows[-1][0] if rows else after}

    def ack(self, scope, run_id, recipient, identifiers):
        if not isinstance(identifiers, list) or len(identifiers) > 100:
            raise ValueError("ack accepts at most 100 message IDs")
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            for identifier in identifiers:
                found = db.execute(
                    "SELECT recipient FROM peer_messages WHERE scope=? AND run_id=? AND id=?",
                    (scope.key, run_id, identifier),
                ).fetchone()
                if not found or found[0] != recipient:
                    raise ValueError("message does not belong to this inbox")
            for identifier in identifiers:
                db.execute(
                    "UPDATE peer_messages SET acknowledged=1 WHERE scope=? AND run_id=? AND id=?",
                    (scope.key, run_id, identifier),
                )
        return {"acknowledged": identifiers}

    def wait(self, scope, run_id, recipient, after, timeout_seconds, *, idempotency_key):
        self.identity(recipient)
        if not 0 < timeout_seconds <= 3600 or type(after) is not int or after < 0:
            raise ValueError("invalid wait policy")
        intent = canonical_json(
            {
                "run_id": run_id,
                "recipient": recipient,
                "after": after,
                "timeout_seconds": timeout_seconds,
            }
        )
        identifier = digest([scope.key, run_id, recipient, idempotency_key])
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT intent FROM peer_waits WHERE scope=? AND id=?", (scope.key, identifier)
            ).fetchone()
            if row and row[0] != intent:
                raise ValueError("wait operation already has a different intent")
            db.execute(
                "INSERT OR IGNORE INTO peer_waits(scope,id,run_id,recipient,intent,deadline) VALUES(?,?,?,?,?,?)",
                (scope.key, identifier, run_id, recipient, intent, time.time() + timeout_seconds),
            )
        return identifier

    def poll_wait(self, scope, run_id, recipient, identifier):
        with self.connect() as db:
            row = db.execute(
                "SELECT intent,deadline,canceled FROM peer_waits WHERE scope=? AND run_id=? AND recipient=? AND id=?",
                (scope.key, run_id, recipient, identifier),
            ).fetchone()
        if not row:
            raise ValueError("wait is outside this inbox")
        if row[2]:
            return ExternalStatus("canceled")
        result = self.receive(scope, run_id, recipient, after=json.loads(row[0])["after"])
        expired = time.time() >= row[1]
        if result["messages"] or expired:
            return ExternalStatus(
                "succeeded", {**result, "timed_out": expired and not result["messages"]}
            )
        return ExternalStatus("pending")

    def cancel_wait(self, scope, run_id, recipient, identifier):
        with self.connect() as db:
            db.execute(
                "UPDATE peer_waits SET canceled=1 WHERE scope=? AND run_id=? AND recipient=? AND id=?",
                (scope.key, run_id, recipient, identifier),
            )


def register_message_tools(registry, store, scope):
    def validated(function, *args, **kwargs):
        # Store validation happens before writes or inside a rolled-back
        # transaction. Let an agent correct its call without reconciliation.
        try:
            return function(*args, **kwargs)
        except ValueError as exc:
            raise ToolRejectedError("invalid_message", str(exc)) from None

    def send(recipient, content, idempotency_key, reply_to=None):
        identity = validated(caller)
        return validated(store.send,
            scope,
            identity.run_id,
            identity.mailbox,
            recipient,
            content,
            reply_to=reply_to,
            idempotency_key=idempotency_key,
        )

    def receive(after=0, limit=20):
        identity = validated(caller)
        return validated(store.receive, scope, identity.run_id, identity.mailbox, after=after, limit=limit)

    def ack(ids, idempotency_key):
        identity = validated(caller)
        return validated(store.ack, scope, identity.run_id, identity.mailbox, ids)

    def wait(after=0, timeout_seconds=60, *, idempotency_key):
        identity = validated(caller)
        return validated(store.wait,
            scope,
            identity.run_id,
            identity.mailbox,
            after,
            timeout_seconds,
            idempotency_key=idempotency_key,
        )

    def poll(identifier):
        identity = caller()
        return store.poll_wait(scope, identity.run_id, identity.mailbox, identifier)

    def cancel(identifier):
        identity = caller()
        store.cancel_wait(scope, identity.run_id, identity.mailbox, identifier)
        return ExternalStatus("canceled")

    send_schema = obj(
        recipient={"type": "string", "pattern": IDENTIFIER.pattern},
        content={"type": "string", "minLength": 1, "maxLength": 12000},
    )
    send_schema["properties"]["reply_to"] = {"type": ["string", "null"]}
    registry.register(
        Tool(
            "messages.send",
            "Send a non-blocking message, delivered when the peer next runs. Sender identity is supplied by the runtime.",
            send_schema,
            {"type": "object"},
            send,
            side_effect="write",
            idempotent=True,
        )
    )
    receive_schema = {
        "type": "object",
        "properties": {
            "after": {"type": "integer", "minimum": 0},
            "limit": {"type": "integer", "minimum": 1, "maximum": 100},
        },
        "additionalProperties": False,
    }
    registry.register(
        Tool(
            "messages.receive",
            "Read messages addressed to this agent. Use sequence cursors to read later arrivals.",
            receive_schema,
            {"type": "object"},
            receive,
        )
    )
    registry.register(
        Tool(
            "messages.ack",
            "Mark received messages as handled. Pass IDs from this agent's inbox or injected peer messages.",
            obj(ids={"type": "array", "items": {"type": "string"}, "maxItems": 100}),
            {"type": "object"},
            ack,
            side_effect="write",
            idempotent=True,
        )
    )
    registry.register(
        ExternalTool(
            "messages.wait",
            "Wait durably for a peer message. Releases the worker until a message arrives or the timeout expires.",
            {
                "type": "object",
                "properties": {
                    "after": {"type": "integer", "minimum": 0},
                    "timeout_seconds": {"type": "number", "exclusiveMinimum": 0, "maximum": 3600},
                },
                "additionalProperties": False,
            },
            {"type": "object"},
            wait,
            poll,
            cancel,
            job_timeout_seconds=3660,
        )
    )
    return registry
