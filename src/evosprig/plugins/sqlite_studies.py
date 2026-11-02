"""Scoped immutable suites and durable optimization jobs with fenced ownership."""

import json
import time
import uuid

from evosprig.core.journal import LeaseConflict, LeaseLost
from evosprig.core.spec import canonical_json
from evosprig.evaluation.suite import EvalSuite
from evosprig.plugins.sqlite_versions import VersionStore


class StudyStore(VersionStore):
    def __init__(self, path):
        super().__init__(path)
        with self.connect() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS suites (scope TEXT, id TEXT, body TEXT NOT NULL, PRIMARY KEY(scope,id))"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS studies (scope TEXT, id TEXT, body TEXT NOT NULL, PRIMARY KEY(scope,id))"
            )

    def put_suite(self, scope, suite):
        with self.connect() as db:
            db.execute(
                "INSERT OR IGNORE INTO suites VALUES (?, ?, ?)",
                (scope.key, suite.suite_id, canonical_json(suite.model_dump())),
            )
        return suite.suite_id

    def get_suite(self, scope, identifier):
        with self.connect(False) as db:
            row = db.execute(
                "SELECT body FROM suites WHERE scope=? AND id=?", (scope.key, identifier)
            ).fetchone()
        if not row:
            raise KeyError("suite not found in scope")
        return EvalSuite.model_validate_json(row[0])

    def suites(self, scope):
        with self.connect(False) as db:
            return [
                {"suite_id": row[0], "suite": json.loads(row[1])}
                for row in db.execute(
                    "SELECT id,body FROM suites WHERE scope=? ORDER BY rowid", (scope.key,)
                )
            ]

    def create_study(self, scope, version_id, suite_id, config, bindings):
        self.get(scope, version_id)
        self.get_suite(scope, suite_id)
        identifier = uuid.uuid4().hex
        record = {
            "id": identifier,
            "scope": json.loads(scope.key),
            "base_version": version_id,
            "suite_id": suite_id,
            "config": config,
            "bindings": bindings,
            "status": "queued",
            "created_at": time.time(),
            "owner": None,
            "generation": 0,
            "lease_until": 0.0,
            "events": [],
            "usage": {},
            "result": None,
            "error": None,
            "cancel_requested": False,
        }
        with self.connect() as db:
            db.execute(
                "INSERT INTO studies VALUES (?, ?, ?)",
                (scope.key, identifier, canonical_json(record)),
            )
        return record

    @staticmethod
    def _study(db, scope, identifier):
        row = db.execute(
            "SELECT body FROM studies WHERE scope=? AND id=?", (scope.key, identifier)
        ).fetchone()
        if not row:
            raise KeyError("study not found in scope")
        return json.loads(row[0])

    def study(self, scope, identifier):
        with self.connect(False) as db:
            return self._study(db, scope, identifier)

    def studies(self, scope):
        with self.connect(False) as db:
            return [
                json.loads(row[0])
                for row in db.execute(
                    "SELECT body FROM studies WHERE scope=? ORDER BY rowid DESC", (scope.key,)
                )
            ]

    def claim_study(self, scope, identifier, owner):
        with self.connect() as db:
            record = self._study(db, scope, identifier)
            if record["status"] != "queued":
                raise LeaseConflict("study is not queued")
            record.update(
                status="running",
                owner=owner,
                generation=record["generation"] + 1,
                lease_until=time.time() + 30,
            )
            db.execute(
                "UPDATE studies SET body=? WHERE scope=? AND id=?",
                (canonical_json(record), scope.key, identifier),
            )
        return record["generation"]

    def update_study(self, scope, identifier, owner, generation, *, event=None, **changes):
        if set(changes) - {"status", "result", "error", "usage"}:
            raise ValueError("invalid study changes")
        with self.connect() as db:
            record = self._study(db, scope, identifier)
            if (
                record["owner"] != owner
                or record["generation"] != generation
                or record["lease_until"] <= time.time()
            ):
                raise LeaseLost("study lease expired or was superseded")
            record.update(changes, lease_until=time.time() + 30)
            if event:
                record["events"].append(
                    {"sequence": len(record["events"]) + 1, "time": time.time(), **event}
                )
            if record["status"] != "running":
                record.update(owner=None, lease_until=0.0)
            db.execute(
                "UPDATE studies SET body=? WHERE scope=? AND id=?",
                (canonical_json(record), scope.key, identifier),
            )
        return record

    def cancel_study(self, scope, identifier):
        with self.connect() as db:
            record = self._study(db, scope, identifier)
            record["cancel_requested"] = True
            if record["status"] == "queued":
                record["status"] = "canceled"
            db.execute(
                "UPDATE studies SET body=? WHERE scope=? AND id=?",
                (canonical_json(record), scope.key, identifier),
            )
        return record

    def pending_studies(self):
        with self.connect() as db:
            records = []
            for scope, identifier, body in db.execute("SELECT scope,id,body FROM studies"):
                record = json.loads(body)
                if record["status"] == "running" and record["lease_until"] < time.time():
                    # An opaque optimizer may have spent tokens before interruption.
                    # Preserve evidence and reservations; never silently restart its search.
                    record.update(
                        status="interrupted",
                        owner=None,
                        lease_until=0.0,
                        error="worker lost; start a new study from an archived candidate",
                    )
                    db.execute(
                        "UPDATE studies SET body=? WHERE scope=? AND id=?",
                        (canonical_json(record), scope, identifier),
                    )
                if record["status"] == "queued":
                    records.append(record)
        return records
