"""Scoped SQLite memory with an independent, monotonic deletion ledger.

Restore memory.sqlite alone or import records through restore(); retain the current
ledger. Restoring an old ledger would lose deletion history, so it is not a supported
restore procedure. Neither exports nor the ledger contain authentication credentials.
"""

from __future__ import annotations

import json
import math
import re
import sqlite3
import time
import uuid
from contextlib import contextmanager
from dataclasses import asdict
from pathlib import Path

from evosprig.core.memory import MemoryConflict, MemoryRecord, MemoryScope
from evosprig.core.spec import canonical_json, digest


def terms(text):
    words = re.findall(r"[a-z0-9_]+|[\u3400-\u9fff]", text.casefold())
    return set(words)


class SQLiteMemory:
    capabilities = frozenset(
        {"write", "search", "get", "update", "delete", "export", "namespace_delete", "restore"}
    )

    def __init__(self, path: str | Path, *, ledger_path: str | Path | None = None):
        self.path = Path(path)
        self.ledger_path = Path(ledger_path or self.path.with_suffix(".deletions.sqlite"))
        if self.path.resolve() == self.ledger_path.resolve():
            raise ValueError("the deletion ledger must be independent of the memory database")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        with self._transaction() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS memories (scope TEXT, id TEXT, fingerprint TEXT, body TEXT NOT NULL, PRIMARY KEY(scope,id))"
            )
            db.execute(
                "CREATE INDEX IF NOT EXISTS memories_fingerprint ON memories(scope,fingerprint)"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS ledger.tombstones (scope TEXT, id TEXT, deleted_at REAL NOT NULL, PRIMARY KEY(scope,id))"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS ledger.namespaces (scope TEXT PRIMARY KEY, deleted_at REAL NOT NULL)"
            )

    @contextmanager
    def _transaction(self, write=True):
        db = sqlite3.connect(self.path, timeout=10)
        try:
            db.execute("ATTACH DATABASE ? AS ledger", (str(self.ledger_path),))
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
    def _visible(db, scope, record):
        if canonical_json(record["scope"]) != scope.key:
            return False
        if db.execute(
            "SELECT 1 FROM ledger.tombstones WHERE scope=? AND id=?", (scope.key, record["id"])
        ).fetchone():
            return False
        row = db.execute(
            "SELECT deleted_at FROM ledger.namespaces WHERE scope=?", (scope.key,)
        ).fetchone()
        return row is None or record["created_at"] > row[0]

    @staticmethod
    def _active(record):
        now = time.time()
        return (record["valid_from"] is None or record["valid_from"] <= now) and (
            record["valid_until"] is None or record["valid_until"] > now
        )

    def _read(self, db, scope, record_id, *, active=True):
        row = db.execute(
            "SELECT body FROM memories WHERE scope=? AND id=?", (scope.key, record_id)
        ).fetchone()
        if row:
            record = json.loads(row[0])
            if self._visible(db, scope, record) and (not active or self._active(record)):
                return record
        raise KeyError("memory not found in scope")

    @staticmethod
    def _fingerprint(record):
        return digest(
            {
                key: record[key]
                for key in (
                    "content",
                    "source",
                    "content_type",
                    "metadata",
                    "confidence",
                    "valid_from",
                    "valid_until",
                )
            }
        )

    def write(
        self,
        scope: MemoryScope,
        content,
        *,
        source,
        content_type="fact",
        metadata=None,
        confidence=1.0,
        valid_from=None,
        valid_until=None,
        idempotency_key=None,
    ):
        now = time.time()
        record = MemoryRecord(
            id=digest([scope.key, idempotency_key]) if idempotency_key else uuid.uuid4().hex,
            scope=asdict(scope),
            content=content.strip(),
            source=source,
            content_type=content_type,
            metadata=metadata or {},
            confidence=confidence,
            created_at=now,
            updated_at=now,
            valid_from=valid_from,
            valid_until=valid_until,
        ).model_dump()
        fingerprint = self._fingerprint(record)
        with self._transaction() as db:
            if not self._visible(db, scope, record):
                raise MemoryConflict("deleted operation cannot recreate memory")
            existing = db.execute(
                "SELECT body FROM memories WHERE scope=? AND id=?", (scope.key, record["id"])
            ).fetchone()
            if existing:
                old = json.loads(existing[0])
                if self._fingerprint(old) != fingerprint:
                    raise MemoryConflict("idempotency key belongs to different memory content")
                return old
            if idempotency_key is None:
                for row in db.execute(
                    "SELECT body FROM memories WHERE scope=? AND fingerprint=?",
                    (scope.key, fingerprint),
                ):
                    old = json.loads(row[0])
                    if self._visible(db, scope, old):
                        return old
            db.execute(
                "INSERT INTO memories VALUES (?, ?, ?, ?)",
                (scope.key, record["id"], fingerprint, canonical_json(record)),
            )
        return record

    def get(self, scope, record_id):
        with self._transaction(False) as db:
            return self._read(db, scope, record_id)

    def export(self, scope):
        with self._transaction(False) as db:
            records = [
                json.loads(row[0])
                for row in db.execute(
                    "SELECT body FROM memories WHERE scope=? ORDER BY id", (scope.key,)
                )
            ]
            return [record for record in records if self._visible(db, scope, record)]

    def search(self, scope, query, *, limit=5):
        if not isinstance(query, str) or len(query) > 4096 or not 1 <= limit <= 100:
            raise ValueError("invalid search bounds")
        query_terms = terms(query)
        hits = []
        for record in self.export(scope):
            if not self._active(record):
                continue
            document_terms = terms(record["content"])
            overlap = len(query_terms & document_terms)
            if query_terms and not overlap:
                continue
            score = overlap / math.sqrt(max(1, len(document_terms)))
            hits.append({**record, "score": score})
        return sorted(hits, key=lambda item: (-item["score"], item["id"]))[:limit]

    def update(self, scope, record_id, content, *, revision):
        with self._transaction() as db:
            record = self._read(db, scope, record_id, active=False)
            if record["revision"] != revision:
                raise MemoryConflict("memory revision changed")
            record.update(content=content.strip(), revision=revision + 1, updated_at=time.time())
            record = MemoryRecord.model_validate(record).model_dump()
            db.execute(
                "UPDATE memories SET fingerprint=?, body=? WHERE scope=? AND id=?",
                (self._fingerprint(record), canonical_json(record), scope.key, record_id),
            )
        return record

    def delete(self, scope, record_id):
        with self._transaction() as db:
            self._read(db, scope, record_id, active=False)
            db.execute(
                "INSERT OR REPLACE INTO ledger.tombstones VALUES (?, ?, ?)",
                (scope.key, record_id, time.time()),
            )
            db.execute("DELETE FROM memories WHERE scope=? AND id=?", (scope.key, record_id))

    def namespace_delete(self, scope):
        with self._transaction() as db:
            count = db.execute(
                "SELECT COUNT(*) FROM memories WHERE scope=?", (scope.key,)
            ).fetchone()[0]
            now = time.time()
            db.execute(
                "INSERT OR REPLACE INTO ledger.tombstones SELECT scope,id,? FROM memories WHERE scope=?",
                (now, scope.key),
            )
            db.execute(
                "INSERT INTO ledger.namespaces VALUES (?, ?) ON CONFLICT(scope) DO UPDATE SET deleted_at=MAX(deleted_at, excluded.deleted_at)",
                (scope.key, now),
            )
            db.execute("DELETE FROM memories WHERE scope=?", (scope.key,))
        return count

    def restore(self, scope, records):
        """Restore an explicit scoped backup; tombstones always take precedence."""
        records = [MemoryRecord.model_validate(record).model_dump() for record in records]
        if any(canonical_json(record["scope"]) != scope.key for record in records):
            raise ValueError("backup contains a different memory scope")
        restored, skipped = 0, 0
        with self._transaction() as db:
            for record in records:
                if not self._visible(db, scope, record):
                    skipped += 1
                    continue
                # Never overwrite more recent live state during restore.
                changed = db.execute(
                    "INSERT OR IGNORE INTO memories VALUES (?, ?, ?, ?)",
                    (scope.key, record["id"], self._fingerprint(record), canonical_json(record)),
                ).rowcount
                restored += changed
                skipped += not changed
        return {"restored": restored, "skipped": skipped}
