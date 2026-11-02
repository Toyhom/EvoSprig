"""Named context blocks and temporal relations using the same scoped deletion ledger."""

import json
import time
import uuid
from dataclasses import asdict

from evosprig.core.memory import MemoryConflict, MemoryRecord
from evosprig.core.spec import canonical_json


class StructuredMemory:
    def __init__(self, memory):
        self.memory = memory

    def _records(self, db, scope):
        for row in db.execute("SELECT body FROM memories WHERE scope=?", (scope.key,)):
            record = json.loads(row[0])
            if self.memory._visible(db, scope, record):
                yield record

    def _save(self, db, scope, record):
        record = MemoryRecord.model_validate(record).model_dump()
        db.execute(
            "INSERT INTO memories VALUES (?,?,?,?) ON CONFLICT(scope,id) DO UPDATE SET fingerprint=excluded.fingerprint,body=excluded.body",
            (scope.key, record["id"], self.memory._fingerprint(record), canonical_json(record)),
        )
        return record

    @staticmethod
    def _new(scope, content, source, content_type, metadata, **kwargs):
        now = time.time()
        return MemoryRecord(
            id=uuid.uuid4().hex,
            scope=asdict(scope),
            content=content,
            source=source,
            content_type=content_type,
            metadata=metadata,
            created_at=now,
            updated_at=now,
            **kwargs,
        ).model_dump()

    def set_context(self, scope, name, content, *, source, revision=0, max_chars=4000):
        if not isinstance(name, str) or not name or len(name) > 128 or not 1 <= max_chars <= 100000:
            raise ValueError("invalid context block configuration")
        if not content.strip() or len(content) > max_chars:
            raise ValueError("context block exceeds its character budget or is empty")
        with self.memory._transaction() as db:
            old = next(
                (
                    r
                    for r in self._records(db, scope)
                    if r["content_type"] == "context" and r["metadata"].get("block") == name
                ),
                None,
            )
            if revision != (old["revision"] if old else 0):
                raise MemoryConflict("context block revision changed")
            record = self._new(
                scope, content, source, "context", {"block": name, "max_chars": max_chars}
            )
            if old:
                record.update(id=old["id"], created_at=old["created_at"], revision=revision + 1)
            return self._save(db, scope, record)

    def context(self, scope, *, max_chars=12000):
        if not 1 <= max_chars <= 1000000:
            raise ValueError("invalid context budget")
        blocks = sorted(
            (
                r
                for r in self.memory.export(scope)
                if r["content_type"] == "context"
                and "block" in r["metadata"]
                and self.memory._active(r)
            ),
            key=lambda r: r["metadata"]["block"],
        )
        selected, used = [], 0
        for block in blocks:
            size = len(block["content"])
            if used + size <= max_chars:
                selected.append(block)
                used += size
        return {"blocks": selected, "characters": used, "omitted": len(blocks) - len(selected)}

    def set_relation(self, scope, subject, predicate, object_, *, source, valid_from=None):
        for value in (subject, predicate, object_):
            if not isinstance(value, str) or not value.strip() or len(value) > 1024:
                raise ValueError("relation components must be nonempty bounded strings")
        when = time.time() if valid_from is None else valid_from
        with self.memory._transaction() as db:
            prior = [
                r
                for r in self._records(db, scope)
                if r["metadata"].get("relation", [])[:2] == [subject, predicate]
            ]
            latest = max(prior, key=lambda r: r["valid_from"], default=None)
            if latest and when < latest["valid_from"]:
                raise MemoryConflict("relation updates must follow their existing timeline")
            if latest and latest["metadata"]["relation"][2] == object_:
                return latest
            if latest:
                if when == latest["valid_from"]:
                    raise MemoryConflict("two relation values cannot start at the same instant")
                latest.update(
                    valid_until=when, updated_at=time.time(), revision=latest["revision"] + 1
                )
                self._save(db, scope, latest)
            record = self._new(
                scope,
                f"{subject} {predicate} {object_}",
                source,
                "fact",
                {"relation": [subject, predicate, object_]},
                valid_from=when,
            )
            return self._save(db, scope, record)

    def relations(self, scope, subject, *, at=None, hops=1, limit=50):
        if not 1 <= hops <= 4 or not 1 <= limit <= 100:
            raise ValueError("invalid relation traversal bounds")
        records = [
            r
            for r in self.memory.export(scope)
            if "relation" in r["metadata"] and self.memory._active(r, at)
        ]
        frontier, visited, hits = {subject}, set(), []
        for _ in range(hops):
            next_frontier = set()
            for record in sorted(records, key=lambda r: r["id"]):
                a, _, b = record["metadata"]["relation"]
                if a in frontier and record["id"] not in visited:
                    visited.add(record["id"])
                    hits.append(record)
                    next_frontier.add(b)
                    if len(hits) == limit:
                        return hits
            frontier = next_frontier
        return hits
