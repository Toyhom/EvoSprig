"""Durable media jobs with payload-bound idempotency and explicit recovery."""

import hashlib
import json
import sqlite3
import time
import uuid
from contextlib import contextmanager
from pathlib import Path


class JobStore:
    def __init__(self, path):
        self.path = str(path)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, operation TEXT, key TEXT UNIQUE, fingerprint TEXT, payload TEXT, status TEXT, output TEXT, error TEXT, created REAL, updated REAL)")

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=30)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def submit(self, operation, key, payload):
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        fingerprint = hashlib.sha256((operation + encoded).encode()).hexdigest()
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            previous = db.execute("SELECT * FROM jobs WHERE key=?", (key,)).fetchone()
            if previous:
                if previous["fingerprint"] != fingerprint:
                    raise ValueError("idempotency key already belongs to a different request")
                return previous["id"]
            identifier = uuid.uuid4().hex
            now = time.time()
            db.execute("INSERT INTO jobs VALUES (?, ?, ?, ?, ?, 'pending', NULL, NULL, ?, ?)",
                       (identifier, operation, key, fingerprint, encoded, now, now))
            return identifier

    def get(self, identifier, operation=None):
        with self.connect() as db:
            row = db.execute("SELECT * FROM jobs WHERE id=?", (identifier,)).fetchone()
        if not row or operation is not None and row["operation"] != operation:
            raise KeyError(identifier)
        return dict(row)

    def claim(self, operations=None):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            allowed = tuple(sorted(operations)) if operations is not None else None
            if allowed == ():
                return None
            clause = " AND operation IN (" + ",".join("?" for _ in allowed) + ")" if allowed else ""
            row = db.execute("SELECT * FROM jobs WHERE status='pending'" + clause + " ORDER BY created LIMIT 1",
                             allowed or ()).fetchone()
            if not row:
                return None
            db.execute("UPDATE jobs SET status='running', updated=? WHERE id=?", (time.time(), row["id"]))
            return dict(row)

    def finish(self, identifier, output=None, error=None):
        with self.connect() as db:
            db.execute("UPDATE jobs SET status=?, output=?, error=?, updated=? WHERE id=? AND status='running'",
                       ("failed" if error else "succeeded", json.dumps(output), error, time.time(), identifier))

    def cancel(self, identifier):
        self.get(identifier)
        with self.connect() as db:
            db.execute("UPDATE jobs SET status='canceled', updated=? WHERE id=? AND status IN ('pending','running')", (time.time(), identifier))

    def retry(self, identifier):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT status FROM jobs WHERE id=?", (identifier,)).fetchone()
            if not row:
                raise KeyError(identifier)
            if row["status"] != "failed":
                raise ValueError("only failed jobs can be retried")
            db.execute("UPDATE jobs SET status='pending', error=NULL, output=NULL, updated=? WHERE id=?", (time.time(), identifier))

    def recover(self):
        # Interrupted GPU work is never billed or rendered again implicitly.
        with self.connect() as db:
            db.execute("UPDATE jobs SET status='failed', error='Worker interrupted; retry this job or submit a new take', updated=? WHERE status='running'", (time.time(),))

    def counts(self):
        with self.connect() as db:
            return {row["status"]: row["count"] for row in db.execute(
                "SELECT status, COUNT(*) AS count FROM jobs GROUP BY status")}

    def run_once(self, backend, operations=None):
        row = self.claim(operations)
        if row is None:
            return False
        try:
            output = backend.execute(row["operation"], json.loads(row["payload"]), row["id"],
                                     lambda: self.get(row["id"])["status"] == "canceled")
            self.finish(row["id"], output)
        except Exception as exc:
            self.finish(row["id"], error=f"{type(exc).__name__}: {str(exc)[:500]}")
        return True
