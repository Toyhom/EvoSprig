"""Scope-first semantic retrieval with content-addressed embeddings and rank fusion."""

from __future__ import annotations

import json
import math
import sqlite3
import time
from typing import Protocol

from evosprig.core.spec import digest


class Embeddings(Protocol):
    model_id: str

    def embed(self, texts: list[str]) -> list[list[float]]: ...


def vectors(values, count):
    if not isinstance(values, list) or len(values) != count:
        raise ValueError("embedding provider returned a different batch size")
    dimension = None
    result = []
    for vector in values:
        if not isinstance(vector, (list, tuple)) or not vector:
            raise ValueError("embedding must be a nonempty vector")
        vector = [float(x) for x in vector]
        if any(not math.isfinite(x) for x in vector) or not sum(x * x for x in vector):
            raise ValueError("embedding must be finite and nonzero")
        dimension = dimension or len(vector)
        if dimension != len(vector):
            raise ValueError("embedding dimensions differ")
        norm = math.sqrt(sum(x * x for x in vector))
        result.append([x / norm for x in vector])
    return result


class HybridMemory:
    """Delegate writes to a MemoryStore; combine BM25 and cosine ranks at retrieval.

    The bounded process-local cache contains only vectors. Authoritative records and
    deletion checks are re-read on every query, including after a restore.
    """

    def __init__(self, memory, embedder: Embeddings, *, cache_size=4096, batch_size=64,
                 cache_path=None, persistent_cache_size=100000, mode="hybrid", min_similarity=None):
        if cache_size < 1 or not 1 <= batch_size <= 256:
            raise ValueError("invalid embedding cache/batch size")
        if mode not in {"semantic", "hybrid"} or (min_similarity is not None and
                (not math.isfinite(min_similarity) or not -1 <= min_similarity <= 1)):
            raise ValueError("invalid vector retrieval policy")
        self.memory, self.embedder = memory, embedder
        self.mode, self.min_similarity = mode, min_similarity
        self.cache_size, self.batch_size, self.cache = cache_size, batch_size, {}
        self.cache_path, self.persistent_cache_size = cache_path, persistent_cache_size
        if cache_path:
            with sqlite3.connect(cache_path, timeout=10) as db:
                db.execute("CREATE TABLE IF NOT EXISTS embedding_cache(key TEXT PRIMARY KEY, vector TEXT, used REAL)")

    def __getattr__(self, name):
        return getattr(self.memory, name)

    def search(self, scope, query, *, limit=5, at=None, content_type=None):
        if not isinstance(query, str) or len(query) > 4096 or not 1 <= limit <= 100:
            raise ValueError("invalid search bounds")
        if not query.strip():
            return self.memory.search(scope, query, limit=limit, at=at, content_type=content_type)
        records = [
            r
            for r in self.memory.export(scope)
            if self.memory._active(r, at)
            and (content_type is None or r["content_type"] == content_type)
        ]
        if not records:
            return []
        # Include scope in cache keys; embeddings never grant access to source text.
        keys = [digest([scope.key, self.embedder.model_id, r["content"]]) for r in records]
        cached = dict(self.cache)
        if self.cache_path:
            with sqlite3.connect(self.cache_path, timeout=10) as db:
                for start in range(0, len(keys), 500):
                    batch = keys[start:start + 500]
                    cached.update((key, json.loads(vector)) for key, vector in db.execute(
                        "SELECT key,vector FROM embedding_cache WHERE key IN (" + ",".join("?" for _ in batch) + ")", batch))
        embeddings = {}
        missing = [
            (key, r["content"])
            for key, r in zip(keys, records, strict=True)
            if key not in cached
        ]
        for start in range(0, len(missing), self.batch_size):
            batch = missing[start : start + self.batch_size]
            output = vectors(self.embedder.embed([text for _, text in batch]), len(batch))
            embeddings.update(zip([key for key, _ in batch], output, strict=True))
        if self.cache_path and embeddings:
            with sqlite3.connect(self.cache_path, timeout=10) as db:
                db.executemany("INSERT OR REPLACE INTO embedding_cache VALUES(?,?,?)",
                               [(key, json.dumps(vector), time.time()) for key, vector in embeddings.items()])
                db.execute("DELETE FROM embedding_cache WHERE key IN (SELECT key FROM embedding_cache ORDER BY used DESC LIMIT -1 OFFSET ?)", (self.persistent_cache_size,))
        embeddings.update({key: cached[key] for key in keys if key in cached})
        q = vectors(self.embedder.embed([query]), 1)[0]
        if any(len(embeddings[key]) != len(q) for key in keys):
            raise ValueError("query and document embedding dimensions differ")
        similarities = {r["id"]: sum(a * b for a, b in zip(q, embeddings[key], strict=True))
                        for r, key in zip(records, keys, strict=True)}
        semantic = sorted(
            zip(records, keys, strict=True),
            key=lambda pair: (
                -similarities[pair[0]["id"]],
                pair[0]["id"],
            ),
        )
        semantic = [(r, key) for r, key in semantic
                    if self.min_similarity is None or similarities[r["id"]] >= self.min_similarity]
        lexical = self.memory.search(scope, query, limit=100, at=at, content_type=content_type) if self.mode == "hybrid" else []
        scores = {r["id"]: (similarities[r["id"]] if self.mode == "semantic" else 1 / (60 + rank))
                  for rank, (r, _) in enumerate(semantic, 1)}
        for rank, r in enumerate(lexical, 1):
            if r["id"] in similarities:
                scores[r["id"]] = scores.get(r["id"], 0) + 1 / (60 + rank)
        self.cache.update(embeddings)
        while len(self.cache) > self.cache_size:
            del self.cache[next(iter(self.cache))]
        return sorted(
            ({**r, "score": scores[r["id"]], "similarity": similarities[r["id"]]} for r in records if r["id"] in scores), key=lambda r: (-r["score"], r["id"])
        )[:limit]
