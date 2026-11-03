"""Immutable version/candidate archive and compare-and-swap release history."""

from __future__ import annotations

import difflib
import json
import sqlite3
import time
import uuid
from contextlib import contextmanager
from dataclasses import asdict
from pathlib import Path

from evosprig.core.spec import canonical_json
from evosprig.core.version import AgentVersion, compile_snapshot
from evosprig.plugins.sqlite_projects import RevisionConflict

DATA_CONTRACT = {"memory": "sqlite-memory-v1", "runtime": "journal-v1"}


class VersionStore:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS versions (scope TEXT, id TEXT, body TEXT NOT NULL, PRIMARY KEY(scope,id))"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS candidates (scope TEXT, id TEXT, body TEXT NOT NULL, PRIMARY KEY(scope,id))"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS releases (scope TEXT PRIMARY KEY, revision INTEGER NOT NULL, version_id TEXT NOT NULL, body TEXT NOT NULL)"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS release_history (scope TEXT, revision INTEGER, body TEXT NOT NULL, PRIMARY KEY(scope,revision))"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS evaluation_reports (scope TEXT, id TEXT, body TEXT NOT NULL, PRIMARY KEY(scope,id))"
            )

    @contextmanager
    def connect(self, write=True):
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

    def put(self, scope, version):
        if version.spec.id != scope.project:
            raise ValueError("version scope does not match project")
        verified = compile_snapshot(version.spec, version.resources)
        if version != verified:
            raise ValueError("version does not match its content and runtime lock")
        with self.connect() as db:
            db.execute(
                "INSERT OR IGNORE INTO versions VALUES (?, ?, ?)",
                (scope.key, version.version_id, canonical_json(asdict(version))),
            )
        return version.version_id

    @staticmethod
    def _version(db, scope, version_id):
        row = db.execute(
            "SELECT body FROM versions WHERE scope=? AND id=?", (scope.key, version_id)
        ).fetchone()
        if not row:
            raise KeyError("version not found in scope")
        return AgentVersion(**json.loads(row[0]))

    def get(self, scope, version_id):
        with self.connect(False) as db:
            return self._version(db, scope, version_id)

    def versions(self, scope):
        with self.connect(False) as db:
            return [
                AgentVersion(**json.loads(row[0]))
                for row in db.execute(
                    "SELECT body FROM versions WHERE scope=? ORDER BY id", (scope.key,)
                )
            ]

    def candidate(self, scope, base, changes, *, allowed, method, job_id):
        if not changes or set(changes) - set(allowed) or set(allowed) - set(base.resources):
            raise ValueError("candidate attempted to edit undeclared or protected resources")
        version = compile_snapshot(base.spec, {**base.resources, **changes})
        return self.snapshot_candidate(scope, base, version, method=method, job_id=job_id)

    def snapshot_candidate(self, scope, base, version, *, method, job_id):
        """Archive a validated SDK snapshot, including graph and code changes."""
        self.put(scope, base)
        self.put(scope, version)
        identifier = uuid.uuid4().hex
        record = {
            "id": identifier,
            "base_version": base.version_id,
            "version_id": version.version_id,
            "job_id": job_id,
            "method": method,
            "created_at": time.time(),
            "changes": sorted(self.diff(base, version)),
            "diff": self.diff(base, version),
            "data_contract": DATA_CONTRACT,
        }
        with self.connect() as db:
            db.execute(
                "INSERT INTO candidates VALUES (?, ?, ?)",
                (scope.key, identifier, canonical_json(record)),
            )
        return record

    @staticmethod
    def diff(base, candidate):
        changes = {
            name: "".join(
                difflib.unified_diff(
                    [line + "\n" for line in base.resources.get(name, "").splitlines()],
                    [line + "\n" for line in text.splitlines()],
                    fromfile="base/" + name,
                    tofile="candidate/" + name,
                )
            )
            for name, text in candidate.resources.items()
            if text != base.resources.get(name)
        }
        if base.spec_json != candidate.spec_json:
            changes["agent.json"] = "".join(difflib.unified_diff(
                (json.dumps(json.loads(base.spec_json), indent=2) + "\n").splitlines(True),
                (json.dumps(json.loads(candidate.spec_json), indent=2) + "\n").splitlines(True),
                fromfile="base/agent.json", tofile="candidate/agent.json",
            ))
        return changes

    def candidates(self, scope):
        with self.connect(False) as db:
            return [
                json.loads(row[0])
                for row in db.execute(
                    "SELECT body FROM candidates WHERE scope=? ORDER BY rowid", (scope.key,)
                )
            ]

    def get_candidate(self, scope, identifier):
        with self.connect(False) as db:
            row = db.execute(
                "SELECT body FROM candidates WHERE scope=? AND id=?", (scope.key, identifier)
            ).fetchone()
        if not row:
            raise KeyError("candidate not found in scope")
        return json.loads(row[0])

    def report(self, scope, report):
        self.get(scope, report["version_id"])
        with self.connect() as db:
            data = canonical_json(report)
            existing = db.execute(
                "SELECT body FROM evaluation_reports WHERE scope=? AND id=?",
                (scope.key, report["report_id"]),
            ).fetchone()
            if existing and existing[0] != data:
                raise ValueError("evaluation reports are immutable")
            db.execute(
                "INSERT OR IGNORE INTO evaluation_reports VALUES (?, ?, ?)",
                (scope.key, report["report_id"], data),
            )
        return report["report_id"]

    def get_report(self, scope, identifier):
        with self.connect(False) as db:
            row = db.execute(
                "SELECT body FROM evaluation_reports WHERE scope=? AND id=?",
                (scope.key, identifier),
            ).fetchone()
        if not row:
            raise KeyError("evaluation report not found in scope")
        return json.loads(row[0])

    def release(self, scope):
        with self.connect(False) as db:
            row = db.execute("SELECT body FROM releases WHERE scope=?", (scope.key,)).fetchone()
        return (
            json.loads(row[0])
            if row
            else {"revision": 0, "version_id": None, "data_contract": DATA_CONTRACT}
        )

    def history(self, scope):
        with self.connect(False) as db:
            return [
                json.loads(row[0])
                for row in db.execute(
                    "SELECT body FROM release_history WHERE scope=? ORDER BY revision", (scope.key,)
                )
            ]

    def publish(
        self,
        scope,
        version_id,
        *,
        expected_revision,
        expected_base=None,
        reason="manual",
        evidence=None,
        rollback=False,
    ):
        with self.connect() as db:
            self._version(db, scope, version_id)
            row = db.execute(
                "SELECT revision,version_id,body FROM releases WHERE scope=?", (scope.key,)
            ).fetchone()
            revision = row[0] if row else 0
            if revision != expected_revision or (
                expected_base is not None and row is not None and row[1] != expected_base
            ):
                raise RevisionConflict("release changed; re-evaluate against the current release")
            if row and json.loads(row[2])["data_contract"] != DATA_CONTRACT:
                raise ValueError("release requires an explicit data migration")
            if rollback:
                previous = [
                    json.loads(item[0])
                    for item in db.execute(
                        "SELECT body FROM release_history WHERE scope=?", (scope.key,)
                    )
                ]
                if not any(
                    item["version_id"] == version_id and item["data_contract"] == DATA_CONTRACT
                    for item in previous
                ):
                    raise ValueError(
                        "rollback target must be a compatible previously released version"
                    )
            record = {
                "revision": revision + 1,
                "version_id": version_id,
                "previous_version": row[1] if row else None,
                "reason": reason,
                "evidence": evidence,
                "created_at": time.time(),
                "data_contract": DATA_CONTRACT,
            }
            body = canonical_json(record)
            db.execute(
                "INSERT INTO releases VALUES (?, ?, ?, ?) ON CONFLICT(scope) DO UPDATE SET revision=excluded.revision,version_id=excluded.version_id,body=excluded.body",
                (scope.key, revision + 1, version_id, body),
            )
            db.execute(
                "INSERT INTO release_history VALUES (?, ?, ?)", (scope.key, revision + 1, body)
            )
        return record
