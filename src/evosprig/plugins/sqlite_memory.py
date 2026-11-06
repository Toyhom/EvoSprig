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
from collections import Counter
from contextlib import contextmanager
from dataclasses import asdict
from pathlib import Path

from evosprig.core.memory import MemoryConflict, MemoryRecord, MemoryScope
from evosprig.core.spec import canonical_json, digest


def tokens(text):
    return re.findall(r"[a-z0-9_]+|[\u3400-\u9fff]", text.casefold())


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
            db.execute(
                "CREATE TABLE IF NOT EXISTS ledger.document_sources (scope TEXT, source TEXT, deleted_at REAL NOT NULL, PRIMARY KEY(scope,source))"
            )
            # A materialized lexical index avoids reading/tokenizing an entire knowledge base
            # on each request. Triggers also cover restores and ordinary memory updates.
            indexed = db.execute(
                "SELECT 1 FROM sqlite_master WHERE name='memory_fts'"
            ).fetchone()
            db.execute("CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5(terms, scope UNINDEXED, id UNINDEXED)")
            statements = """
                CREATE TRIGGER IF NOT EXISTS memory_fts_insert AFTER INSERT ON memories BEGIN
                    INSERT INTO memory_fts(rowid,terms,scope,id) VALUES(new.rowid,evosprig_terms(json_extract(new.body,'$.content')),new.scope,new.id);
                END;
                CREATE TRIGGER IF NOT EXISTS memory_fts_delete AFTER DELETE ON memories BEGIN
                    DELETE FROM memory_fts WHERE rowid=old.rowid;
                END;
                CREATE TRIGGER IF NOT EXISTS memory_fts_update AFTER UPDATE ON memories BEGIN
                    DELETE FROM memory_fts WHERE rowid=old.rowid;
                    INSERT INTO memory_fts(rowid,terms,scope,id) VALUES(new.rowid,evosprig_terms(json_extract(new.body,'$.content')),new.scope,new.id);
                END;
            """
            for statement in statements.strip().split("END;"):
                if statement.strip():
                    db.execute(statement + "END;")
            db.execute("CREATE INDEX IF NOT EXISTS memory_documents ON memories(scope,json_extract(body,'$.source'),json_extract(body,'$.content_type'))")
            if not indexed:
                db.execute("INSERT INTO memory_fts(rowid,terms,scope,id) SELECT rowid,evosprig_terms(json_extract(body,'$.content')),scope,id FROM memories")

    @contextmanager
    def _transaction(self, write=True):
        db = sqlite3.connect(self.path, timeout=10)
        db.create_function("evosprig_terms", 1, lambda text: " ".join(tokens(text)), deterministic=True)
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
    def _visible(db, scope, record, seen=None):
        if canonical_json(record["scope"]) != scope.key:
            return False
        if db.execute(
            "SELECT 1 FROM ledger.tombstones WHERE scope=? AND id=?", (scope.key, record["id"])
        ).fetchone():
            return False
        row = db.execute(
            "SELECT deleted_at FROM ledger.namespaces WHERE scope=?", (scope.key,)
        ).fetchone()
        if row is not None and record["created_at"] <= row[0]:
            return False
        if record.get("content_type") == "document":
            row = db.execute(
                "SELECT deleted_at FROM ledger.document_sources WHERE scope=? AND source=?",
                (scope.key, record.get("source")),
            ).fetchone()
            submitted = record.get("metadata", {}).get("submitted_at", record["created_at"])
            if row is not None and submitted <= row[0]:
                return False
        seen = set() if seen is None else set(seen)
        if record["id"] in seen or len(seen) >= 64:
            return False
        seen.add(record["id"])
        for identifier in record.get("metadata", {}).get("derived_from", []):
            source = db.execute(
                "SELECT body FROM memories WHERE scope=? AND id=?", (scope.key, identifier)
            ).fetchone()
            if (
                not source
                or not SQLiteMemory._active(json.loads(source[0]))
                or not SQLiteMemory._visible(db, scope, json.loads(source[0]), seen)
            ):
                return False
            expected_revision = record["metadata"].get("derived_revisions", {}).get(identifier)
            if (
                expected_revision is not None
                and json.loads(source[0])["revision"] != expected_revision
            ):
                return False
        return True

    @staticmethod
    def _active(record, at=None):
        now = time.time() if at is None else at
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

    def replace_documents(self, scope, records, *, source=None):
        """Commit a whole parsed document at once; failed replacements leave the old copy intact."""
        records = [MemoryRecord.model_validate(record).model_dump() for record in records]
        if any(canonical_json(r["scope"]) != scope.key or r["content_type"] != "document" for r in records):
            raise ValueError("document records have a different scope or type")
        with self._transaction() as db:
            old_ids = []
            if source is not None:
                newest = db.execute("SELECT MAX(json_extract(body,'$.metadata.submitted_at')) FROM memories WHERE scope=? AND json_extract(body,'$.source')=? AND json_extract(body,'$.content_type')='document'", (scope.key, source)).fetchone()[0]
                incoming = max((r["metadata"].get("submitted_at", 0) for r in records), default=0)
                deleted = db.execute("SELECT deleted_at FROM ledger.document_sources WHERE scope=? AND source=?", (scope.key, source)).fetchone()
                if deleted and incoming <= deleted[0]:
                    raise MemoryConflict("this source was deleted after the upload began")
                if newest is not None and incoming < newest:
                    raise MemoryConflict("a newer upload of this source has already been indexed")
                old_ids = [r[0] for r in db.execute(
                    "SELECT id FROM memories WHERE scope=? AND json_extract(body,'$.content_type')='document' AND json_extract(body,'$.source')=?",
                    (scope.key, source),
                )]
            for record in records:
                if not self._visible(db, scope, record):
                    raise MemoryConflict("deleted operation cannot recreate memory")
                existing = db.execute("SELECT body FROM memories WHERE scope=? AND id=?", (scope.key, record["id"])).fetchone()
                if existing:
                    if self._fingerprint(json.loads(existing[0])) != self._fingerprint(record):
                        raise MemoryConflict("document key belongs to different content")
                else:
                    db.execute("INSERT INTO memories VALUES (?,?,?,?)", (scope.key, record["id"], self._fingerprint(record), canonical_json(record)))
            retained = {r["id"] for r in records}
            for identifier in set(old_ids) - retained:
                db.execute("INSERT OR REPLACE INTO ledger.tombstones VALUES (?,?,?)", (scope.key, identifier, time.time()))
                db.execute("DELETE FROM memories WHERE scope=? AND id=?", (scope.key, identifier))
        return records

    def export(self, scope):
        with self._transaction(False) as db:
            records = [
                json.loads(row[0])
                for row in db.execute(
                    "SELECT body FROM memories WHERE scope=? ORDER BY id", (scope.key,)
                )
            ]
            return [record for record in records if self._visible(db, scope, record)]

    def search(self, scope, query, *, limit=5, at=None, content_type=None):
        if not isinstance(query, str) or len(query) > 4096 or not 1 <= limit <= 100:
            raise ValueError("invalid search bounds")
        query_terms = terms(query)
        records = [
            r
            for r in self.export(scope)
            if self._active(r, at) and (content_type is None or r["content_type"] == content_type)
        ]
        frequencies = [Counter(tokens(r["content"])) for r in records]
        average = sum(sum(f.values()) for f in frequencies) / max(1, len(records))
        document_counts = Counter(term for f in frequencies for term in f)
        hits = []
        for record, frequency in zip(records, frequencies, strict=True):
            overlap = len(query_terms & frequency.keys())
            if query_terms and not overlap:
                continue
            length = sum(frequency.values())
            score = sum(
                math.log(
                    1 + (len(records) - document_counts[term] + 0.5) / (document_counts[term] + 0.5)
                )
                * frequency[term]
                * 2.2
                / (frequency[term] + 1.2 * (0.25 + 0.75 * length / max(average, 1)))
                for term in query_terms
                if frequency[term]
            )
            hits.append({**record, "score": score})
        return sorted(hits, key=lambda item: (-item["score"], item["id"]))[:limit]

    def search_indexed(self, scope, query, *, limit=5, at=None, content_type=None):
        """FTS5 BM25, with scope and deletion checks before returning any record."""
        if not isinstance(query, str) or len(query) > 4096 or not 1 <= limit <= 100:
            raise ValueError("invalid search bounds")
        words = terms(query)
        match = " OR ".join('"' + word + '"' for word in sorted(words))
        with self._transaction(False) as db:
            if match:
                rows = db.execute(
                    "SELECT m.body,-f.rank FROM memory_fts f JOIN memories m ON m.scope=f.scope AND m.id=f.id "
                    "WHERE memory_fts MATCH ? AND f.scope=? ORDER BY f.rank,f.id",
                    (match, scope.key),
                )
            else:
                rows = db.execute("SELECT body,0 FROM memories WHERE scope=? ORDER BY id", (scope.key,))
            hits = []
            for body, score in rows:
                record = json.loads(body)
                if (content_type is None or record["content_type"] == content_type) and self._active(record, at) and self._visible(db, scope, record):
                    hits.append({**record, "score": score})
                    if len(hits) == limit:
                        break
            return hits

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
            pending = records
            for _ in range(65):
                deferred = []
                for record in pending:
                    if not self._visible(db, scope, record):
                        deferred.append(record)
                        continue
                    # Restore sources before derived summaries, independent of export order.
                    changed = db.execute(
                        "INSERT OR IGNORE INTO memories VALUES (?, ?, ?, ?)",
                        (
                            scope.key,
                            record["id"],
                            self._fingerprint(record),
                            canonical_json(record),
                        ),
                    ).rowcount
                    restored += changed
                    skipped += not changed
                if len(deferred) == len(pending) or not deferred:
                    pending = deferred
                    break
                pending = deferred
            skipped += len(pending)
        return {"restored": restored, "skipped": skipped}
