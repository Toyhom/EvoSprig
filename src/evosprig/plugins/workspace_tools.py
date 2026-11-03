"""Shared, revisioned documents and durable wake-ups for agent teams."""

from __future__ import annotations

import json
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path

from evosprig.core.protocols import ExternalStatus, ExternalTool, Tool, ToolRejectedError
from evosprig.core.spec import canonical_json

WORKSPACE_TOOL_NAMES = frozenset(
    {"workspace.list", "workspace.read", "workspace.write", "workspace.history", "workspace.wait"}
)
TEXT = {"type": "string"}
NAME = {
    "type": "string",
    "minLength": 1,
    "maxLength": 240,
    "pattern": r"^[A-Za-z0-9][A-Za-z0-9_./ -]*$",
}


def obj(**props):
    return {
        "type": "object",
        "properties": props,
        "required": list(props),
        "additionalProperties": False,
    }


class WorkspaceStore:
    """Each scope shares documents across runs; revisions and receipts commit together."""

    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS workspace_documents (
                    scope TEXT, name TEXT, revision INTEGER, body TEXT,
                    PRIMARY KEY(scope, name));
                CREATE TABLE IF NOT EXISTS workspace_revisions (
                    scope TEXT, name TEXT, revision INTEGER, body TEXT,
                    PRIMARY KEY(scope, name, revision));
                CREATE TABLE IF NOT EXISTS workspace_receipts (
                    scope TEXT, operation TEXT, intent TEXT, output TEXT,
                    PRIMARY KEY(scope, operation));
                CREATE TABLE IF NOT EXISTS workspace_wakes (
                    scope TEXT, id TEXT, due REAL, message TEXT, canceled INTEGER DEFAULT 0,
                    PRIMARY KEY(scope, id));
                CREATE TABLE IF NOT EXISTS workspace_wake_intents (
                    scope TEXT, id TEXT, intent TEXT, PRIMARY KEY(scope, id));
            """)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=15)
        try:
            with db:
                yield db
        finally:
            db.close()

    @staticmethod
    def valid_name(name):
        import re

        if (
            not isinstance(name, str)
            or not re.fullmatch(NAME["pattern"], name)
            or len(name) > 240
            or any(p in {"", ".", ".."} for p in name.split("/"))
        ):
            raise ValueError("use a relative document name with ordinary path components")

    def read(self, scope, name, revision=None):
        self.valid_name(name)
        with self.connect() as db:
            if revision is None:
                row = db.execute(
                    "SELECT body FROM workspace_documents WHERE scope=? AND name=?",
                    (scope.key, name),
                ).fetchone()
            else:
                row = db.execute(
                    "SELECT body FROM workspace_revisions WHERE scope=? AND name=? AND revision=?",
                    (scope.key, name, revision),
                ).fetchone()
        if row is None:
            return {
                "name": name,
                "revision": 0,
                "content": "",
                "media_type": "text/markdown",
                "updated_at": None,
            }
        return json.loads(row[0])

    def list(self, scope, prefix=""):
        with self.connect() as db:
            rows = db.execute(
                "SELECT name, revision FROM workspace_documents WHERE scope=? ORDER BY name",
                (scope.key,),
            ).fetchall()
        return {
            "documents": [{"name": n, "revision": r} for n, r in rows if n.startswith(prefix)][:200]
        }

    def history(self, scope, name):
        self.valid_name(name)
        with self.connect() as db:
            rows = db.execute(
                "SELECT body FROM workspace_revisions WHERE scope=? AND name=? ORDER BY revision DESC LIMIT 50",
                (scope.key, name),
            ).fetchall()
        return {
            "revisions": [
                {k: v for k, v in json.loads(row[0]).items() if k != "content"} for row in rows
            ]
        }

    def write(
        self,
        scope,
        name,
        content,
        expected_revision,
        *,
        idempotency_key,
        media_type="text/markdown",
    ):
        self.valid_name(name)
        if not isinstance(content, str) or len(content.encode()) > 1_000_000:
            raise ValueError("document content must be UTF-8 text up to 1 MB")
        if type(expected_revision) is not int or expected_revision < 0:
            raise ValueError("expected_revision must be a nonnegative integer")
        if media_type not in {
            "text/markdown",
            "text/plain",
            "text/html",
            "text/csv",
            "application/json",
        }:
            raise ValueError("unsupported document media type")
        intent = canonical_json([name, content, expected_revision, media_type])
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            receipt = db.execute(
                "SELECT intent, output FROM workspace_receipts WHERE scope=? AND operation=?",
                (scope.key, idempotency_key),
            ).fetchone()
            if receipt:
                if receipt[0] != intent:
                    raise ValueError("operation ID already belongs to a different document edit")
                return json.loads(receipt[1])
            current = db.execute(
                "SELECT revision FROM workspace_documents WHERE scope=? AND name=?",
                (scope.key, name),
            ).fetchone()
            revision = current[0] if current else 0
            if revision != expected_revision:
                raise ToolRejectedError(
                    "revision_conflict",
                    f"{name} is at revision {revision}. Read it, merge your change, and submit with that revision.",
                )
            output = {
                "name": name,
                "revision": revision + 1,
                "content": content,
                "media_type": media_type,
                "updated_at": time.time(),
            }
            body = canonical_json(output)
            db.execute(
                "INSERT OR REPLACE INTO workspace_documents VALUES (?,?,?,?)",
                (scope.key, name, revision + 1, body),
            )
            db.execute(
                "INSERT INTO workspace_revisions VALUES (?,?,?,?)",
                (scope.key, name, revision + 1, body),
            )
            db.execute(
                "INSERT INTO workspace_receipts VALUES (?,?,?,?)",
                (scope.key, idempotency_key, intent, body),
            )
        return output

    def wait(self, scope, seconds, message, *, idempotency_key):
        if (
            type(seconds) not in {int, float}
            or not 0 <= seconds <= 604800
            or not isinstance(message, str)
            or len(message) > 4000
        ):
            raise ValueError("wake-up must be within seven days with a bounded message")
        intent = canonical_json([float(seconds), message])
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            old = db.execute(
                "SELECT intent FROM workspace_wake_intents WHERE scope=? AND id=?",
                (scope.key, idempotency_key),
            ).fetchone()
            if old and old[0] != intent:
                raise ValueError("operation ID already belongs to a different wake-up")
            legacy = db.execute(
                "SELECT message FROM workspace_wakes WHERE scope=? AND id=?",
                (scope.key, idempotency_key),
            ).fetchone()
            if not old and legacy:
                # An older installation cannot reconstruct the original delay.
                raise ValueError("legacy wake-up already exists; poll its saved job ID")
            db.execute(
                "INSERT OR IGNORE INTO workspace_wake_intents VALUES(?,?,?)",
                (scope.key, idempotency_key, intent),
            )
            db.execute(
                "INSERT OR IGNORE INTO workspace_wakes(scope,id,due,message) VALUES(?,?,?,?)",
                (scope.key, idempotency_key, time.time() + seconds, message),
            )
        return idempotency_key

    def poll(self, scope, job_id):
        with self.connect() as db:
            row = db.execute(
                "SELECT due,message,canceled FROM workspace_wakes WHERE scope=? AND id=?",
                (scope.key, job_id),
            ).fetchone()
        if row is None:
            raise ValueError("wake-up not found")
        if row[2]:
            return ExternalStatus("canceled")
        return (
            ExternalStatus("pending")
            if time.time() < row[0]
            else ExternalStatus("succeeded", {"message": row[1], "due_at": row[0]})
        )

    def cancel(self, scope, job_id):
        with self.connect() as db:
            db.execute(
                "UPDATE workspace_wakes SET canceled=1 WHERE scope=? AND id=?", (scope.key, job_id)
            )


def register_workspace_tools(registry, store, scope):
    def write_document(name, content, expected_revision, idempotency_key):
        try:
            saved = store.write(
                scope, name, content, expected_revision, idempotency_key=idempotency_key
            )
        except ValueError as exc:
            raise ToolRejectedError("invalid_document", str(exc)) from None
        return {key: value for key, value in saved.items() if key != "content"}

    for name, description, schema, function in [
        (
            "list",
            "List shared project documents by folder prefix.",
            obj(prefix=TEXT),
            lambda prefix: store.list(scope, prefix),
        ),
        (
            "read",
            "Read a shared document and its revision. A missing document has revision 0.",
            obj(name=NAME),
            lambda name: store.read(scope, name),
        ),
        (
            "history",
            "List the revisions of a shared document.",
            obj(name=NAME),
            lambda name: store.history(scope, name),
        ),
    ]:
        registry.register(
            Tool("workspace." + name, description, schema, {"type": "object"}, function)
        )
    registry.register(
        Tool(
            "workspace.write",
            "Save a shared document. Read its current revision first; use 0 to create. On a revision conflict, read again and merge.",
            obj(
                name=NAME,
                content={"type": "string", "maxLength": 1000000},
                expected_revision={"type": "integer", "minimum": 0},
            ),
            {"type": "object"},
            write_document,
            side_effect="write",
            idempotent=True,
        )
    )
    registry.register(
        ExternalTool(
            "workspace.wait",
            "Schedule a durable wake-up; resume the workflow after the delay.",
            obj(
                seconds={"type": "number", "minimum": 0, "maximum": 604800},
                message={"type": "string", "maxLength": 4000},
            ),
            {"type": "object"},
            lambda seconds, message, idempotency_key: store.wait(
                scope, seconds, message, idempotency_key=idempotency_key
            ),
            lambda job_id: store.poll(scope, job_id),
            lambda job_id: store.cancel(scope, job_id),
            job_timeout_seconds=604860,
        )
    )
    return registry
