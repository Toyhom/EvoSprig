"""SQLite run journal: atomic snapshots/events, leases and fenced operation records."""

from __future__ import annotations

import json
import sqlite3
import time
from contextlib import contextmanager
from dataclasses import asdict
from pathlib import Path

from evosprig.core.journal import (
    TERMINAL,
    Lease,
    LeaseConflict,
    check_lease,
    make_event,
    new_run,
    validate_response,
)
from evosprig.core.spec import canonical_json

CONTROL_FIELDS = (
    "run_id", "scope", "status", "owner", "generation", "lease_until",
    "cancel_requested", "created_at", "updated_at", "ready_at",
)


def control_record(record):
    return {**{key: record[key] for key in CONTROL_FIELDS},
            "version": {"version_id": record["version"]["version_id"]},
            "title": production_title(record["checkpoint"], record["input"])}


def production_title(checkpoint, inputs):
    output = checkpoint.get("output") or {}
    def title(value):
        return value.get("title") if isinstance(value, dict) else None
    if not isinstance(output, dict):
        output = {}
    upstream = inputs.get("upstream")
    return (title(output.get("plan")) or title(output.get("script_editor"))
            or title(upstream.get("script_editor") if isinstance(upstream, dict) else None)
            or str(inputs.get("source_text", ""))[:80])


class SQLiteJournal:
    durable = True

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._transaction() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS runtime_runs (id TEXT PRIMARY KEY, body TEXT NOT NULL)"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS runtime_events (run_id TEXT, sequence INTEGER, body TEXT NOT NULL, PRIMARY KEY(run_id, sequence))"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS runtime_operations (run_id TEXT, id TEXT, body TEXT NOT NULL, PRIMARY KEY(run_id, id))"
            )
            db.execute("CREATE TABLE IF NOT EXISTS runtime_run_control (id TEXT PRIMARY KEY, body TEXT NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS runtime_checkpoints (id TEXT PRIMARY KEY, body TEXT NOT NULL)")
            # One atomic migration, including old in-flight leases and checkpoints.
            pending = [row[0] for row in db.execute(
                "SELECT id FROM runtime_runs WHERE id NOT IN (SELECT id FROM runtime_run_control)"
            )]
            for run_id in pending:
                body = db.execute("SELECT body FROM runtime_runs WHERE id=?", (run_id,)).fetchone()[0]
                record = json.loads(body)
                db.execute("INSERT INTO runtime_run_control VALUES (?, ?)", (run_id, canonical_json(control_record(record))))
                db.execute("INSERT INTO runtime_checkpoints VALUES (?, ?)", (run_id, canonical_json(record.pop("checkpoint"))))
                db.execute("UPDATE runtime_runs SET body=? WHERE id=?", (canonical_json(record), run_id))

    @contextmanager
    def _transaction(self, write=True):
        db = sqlite3.connect(self.path, timeout=10)
        try:
            if write:
                db.execute("BEGIN IMMEDIATE")
            yield db
            if write:
                db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    def _control(db, run_id, scope=None):
        row = db.execute("SELECT body FROM runtime_run_control WHERE id=?", (run_id,)).fetchone()
        if row is None:
            raise KeyError("run not found")
        record = json.loads(row[0])
        if scope is not None and record["scope"] != asdict(scope):
            raise KeyError("run not found in scope")
        return record

    @staticmethod
    def _read(db, run_id, scope=None):
        row = db.execute(
            "SELECT r.body, c.body, p.body FROM runtime_runs r "
            "JOIN runtime_run_control c ON c.id=r.id JOIN runtime_checkpoints p ON p.id=r.id WHERE r.id=?",
            (run_id,),
        ).fetchone()
        if row is None:
            raise KeyError("run not found")
        record, control, checkpoint = (json.loads(body) for body in row)
        record.update({key: control[key] for key in CONTROL_FIELDS})
        record["checkpoint"] = checkpoint
        if scope is not None and record["scope"] != asdict(scope):
            raise KeyError("run not found in scope")
        return record

    @staticmethod
    def _write_control(db, record):
        db.execute("UPDATE runtime_run_control SET body=? WHERE id=?",
                   (canonical_json(record), record["run_id"]))

    def control(self, run_id, scope=None):
        """Read scheduling/cancellation state without deserializing a checkpoint."""
        with self._transaction(False) as db:
            return self._control(db, run_id, scope)

    def create(self, run_id, version, inputs, scope, metadata):
        candidate = new_run(run_id, version, inputs, scope, metadata)
        with self._transaction() as db:
            changed = db.execute(
                "INSERT OR IGNORE INTO runtime_runs VALUES (?, ?)",
                (run_id, canonical_json({key: value for key, value in candidate.items() if key != "checkpoint"})),
            ).rowcount
            if changed:
                db.execute("INSERT INTO runtime_run_control VALUES (?, ?)", (run_id, canonical_json(control_record(candidate))))
                db.execute("INSERT INTO runtime_checkpoints VALUES (?, ?)", (run_id, canonical_json(candidate["checkpoint"])))
            record = self._read(db, run_id, scope)
            if not changed and any(
                record[key] != candidate[key] for key in ("version", "input", "scope", "metadata")
            ):
                raise ValueError("run ID already belongs to a different execution")
            return record

    def get(self, run_id, scope=None):
        with self._transaction(False) as db:
            return self._read(db, run_id, scope)

    def claim(self, run_id, owner, lease_seconds=30.0):
        if lease_seconds <= 0:
            raise ValueError("lease must be positive")
        with self._transaction() as db:
            record = self._control(db, run_id)
            if record["status"] in TERMINAL or (
                record["status"] == "waiting_input" and not record["cancel_requested"]
            ):
                raise LeaseConflict("run cannot be claimed in its current state")
            if record["owner"] is not None and record["lease_until"] > time.time():
                raise LeaseConflict("another worker holds the run lease")
            record.update(
                owner=owner,
                generation=record["generation"] + 1,
                lease_until=time.time() + lease_seconds,
                status="running",
            )
            self._write_control(db, record)
            return Lease(run_id, owner, record["generation"])

    def heartbeat(self, lease, lease_seconds=30.0):
        if lease_seconds <= 0:
            raise ValueError("lease must be positive")
        with self._transaction() as db:
            record = self._control(db, lease.run_id)
            check_lease(record, lease)
            record["lease_until"] = time.time() + lease_seconds
            self._write_control(db, record)

    def save(self, lease, checkpoint, status, events, *, release=False, delay=0):
        # Serialize before acquiring the writer lock, so heartbeats can proceed.
        checkpoint_body = canonical_json(checkpoint)
        with self._transaction() as db:
            record = self._control(db, lease.run_id)
            check_lease(record, lease)
            record.update(
                status=status,
                updated_at=time.time(),
                ready_at=time.time() + delay,
            )
            sequence = db.execute(
                "SELECT COALESCE(MAX(sequence),0) FROM runtime_events WHERE run_id=?",
                (lease.run_id,),
            ).fetchone()[0]
            added = [make_event(record, sequence + i + 1, event) for i, event in enumerate(events)]
            db.executemany(
                "INSERT INTO runtime_events VALUES (?, ?, ?)",
                [(lease.run_id, event["sequence"], canonical_json(event)) for event in added],
            )
            db.execute("UPDATE runtime_checkpoints SET body=? WHERE id=?", (checkpoint_body, lease.run_id))
            record["title"] = production_title(checkpoint, {}) or record.get("title", "")
            # Fence again after database I/O; an expired worker cannot commit.
            check_lease(record, lease)
            if release:
                record.update(owner=None, lease_until=0.0)
            self._write_control(db, record)
            return added

    def events(self, run_id, after=0):
        with self._transaction(False) as db:
            return [
                json.loads(row[0])
                for row in db.execute(
                    "SELECT body FROM runtime_events WHERE run_id=? AND sequence>? ORDER BY sequence",
                    (run_id, after),
                )
            ]

    def operations(self, run_id, scope=None):
        self.control(run_id, scope)
        with self._transaction(False) as db:
            return [
                json.loads(row[0])
                for row in db.execute(
                    "SELECT body FROM runtime_operations WHERE run_id=? ORDER BY rowid", (run_id,)
                )
            ]

    def operation(self, lease, operation_id, intent=None, update=None):
        with self._transaction() as db:
            check_lease(self._control(db, lease.run_id), lease)
            row = db.execute(
                "SELECT body FROM runtime_operations WHERE run_id=? AND id=?",
                (lease.run_id, operation_id),
            ).fetchone()
            operation = json.loads(row[0]) if row else None
            if operation is None and intent is not None:
                operation = {"id": operation_id, "status": "intent", "intent": intent}
                db.execute(
                    "INSERT INTO runtime_operations VALUES (?, ?, ?)",
                    (lease.run_id, operation_id, canonical_json(operation)),
                )
            if update is not None:
                if operation is None:
                    raise KeyError("operation intent is missing")
                operation.update(update)
                db.execute(
                    "UPDATE runtime_operations SET body=? WHERE run_id=? AND id=?",
                    (canonical_json(operation), lease.run_id, operation_id),
                )
            return operation

    def cancel(self, run_id, scope=None):
        with self._transaction() as db:
            record = self._control(db, run_id, scope)
            if record["status"] not in TERMINAL:
                record["cancel_requested"] = True
                self._write_control(db, record)

    def respond(self, run_id, path, response, scope=None):
        with self._transaction() as db:
            record = self._read(db, run_id, scope)
            validate_response(record, path, response)
            record["checkpoint"]["responses"][path] = response
            control = self._control(db, run_id, scope)
            control.update(status="queued", ready_at=time.time())
            db.execute("UPDATE runtime_checkpoints SET body=? WHERE id=?",
                       (canonical_json(record["checkpoint"]), run_id))
            self._write_control(db, control)

    def due(self, limit=100):
        with self._transaction(False) as db:
            now = time.time()
            result = []
            for row in db.execute("SELECT body FROM runtime_run_control ORDER BY rowid"):
                record = json.loads(row[0])
                if (
                    (
                        record["status"] in {"queued", "running", "waiting_external"}
                        or (record["status"] == "waiting_input" and record["cancel_requested"])
                    )
                    and record["lease_until"] <= now
                    and record["ready_at"] <= now
                ):
                    result.append(record["run_id"])
                    if len(result) >= limit:
                        break
            return result

    def list(self, scope=None, limit=100):
        with self._transaction(False) as db:
            records = []
            for run_id, body in db.execute("SELECT id, body FROM runtime_run_control ORDER BY rowid DESC"):
                if scope is None or json.loads(body)["scope"] == asdict(scope):
                    records.append(self._read(db, run_id, scope))
                    if len(records) >= limit:
                        break
            return records

    def summaries(self, scope, limit=100):
        """List a project's productions without loading snapshots or event histories."""
        with self._transaction(False) as db:
            return [dict(zip(("run_id", "status", "created_at", "title"), row)) for row in db.execute(
                "SELECT id, json_extract(body, '$.status'), json_extract(body, '$.created_at'), "
                "json_extract(body, '$.title') FROM runtime_run_control "
                "WHERE json_extract(body, '$.scope.project')=? "
                "AND json_extract(body, '$.scope.user')=? AND json_extract(body, '$.scope.tenant')=? "
                "ORDER BY rowid DESC LIMIT ?", (scope.project, scope.user, scope.tenant, limit))]
