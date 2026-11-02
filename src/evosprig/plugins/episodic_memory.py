"""Experience recall by relevance, importance and recency, with scoped associations."""

import math
import time


class EpisodicMemory:
    def __init__(self, memory):
        self.memory = memory

    def remember(
        self,
        scope,
        content,
        *,
        source,
        importance=0.5,
        tags=None,
        links=None,
        valid_until=None,
        idempotency_key=None,
    ):
        if (
            not isinstance(importance, (int, float))
            or not math.isfinite(importance)
            or not 0 <= importance <= 1
        ):
            raise ValueError("importance must be in [0,1]")
        tags, links = tags or [], links or []
        if (
            len(tags) > 16
            or len(links) > 16
            or any(not isinstance(tag, str) or not 1 <= len(tag) <= 80 for tag in tags)
        ):
            raise ValueError("invalid experience tags or links")
        for identifier in links:
            self.memory.get(scope, identifier)
        return self.memory.write(
            scope,
            content,
            source=source,
            content_type="experience",
            metadata={"importance": importance, "tags": tags, "links": links},
            valid_until=valid_until,
            idempotency_key=idempotency_key,
        )

    def summarize(self, scope, content, source_ids, *, idempotency_key=None):
        if not 1 <= len(source_ids) <= 32 or len(set(source_ids)) != len(source_ids):
            raise ValueError("summary needs 1..32 unique source records")
        revisions = {
            identifier: self.memory.get(scope, identifier)["revision"] for identifier in source_ids
        }
        return self.memory.write(
            scope,
            content,
            source="memory:summary",
            content_type="experience",
            metadata={
                "derived_from": source_ids,
                "derived_revisions": revisions,
                "importance": 0.6,
            },
            idempotency_key=idempotency_key,
        )

    def recall(
        self,
        scope,
        query,
        *,
        limit=5,
        half_life_hours=168,
        relevance_weight=0.6,
        importance_weight=0.2,
        recency_weight=0.2,
        include_links=True,
    ):
        weights = [relevance_weight, importance_weight, recency_weight]
        if (
            not 1 <= limit <= 20
            or not 0 < half_life_hours <= 87600
            or any(not math.isfinite(w) or w < 0 for w in weights)
            or not sum(weights)
        ):
            raise ValueError("invalid recall policy")
        lexical = {r["id"]: r["score"] for r in self.memory.search(scope, query, limit=100)}
        maximum = max(lexical.values(), default=1) or 1
        now = time.time()
        ranked = []
        for record in self.memory.export(scope):
            if not self.memory._active(record):
                continue
            relevance = lexical.get(record["id"], 0) / maximum
            importance = record["metadata"].get("importance", 0.5)
            if not isinstance(importance, (int, float)) or not math.isfinite(importance):
                importance = 0.5
            importance = min(1, max(0, importance))
            recency = 2 ** (-max(0, now - record["updated_at"]) / (half_life_hours * 3600))
            score = sum(w * v for w, v in zip(weights, [relevance, importance, recency])) / sum(
                weights
            )
            ranked.append(
                {
                    **record,
                    "score": score,
                    "recall": {
                        "relevance": relevance,
                        "importance": importance,
                        "recency": recency,
                    },
                }
            )
        selected = sorted(ranked, key=lambda r: (-r["score"], r["id"]))[:limit]
        seen = {r["id"] for r in selected}
        if include_links:
            for record in list(selected):
                for identifier in record["metadata"].get("links", [])[:16]:
                    if identifier in seen:
                        continue
                    try:
                        linked = self.memory.get(scope, identifier)
                    except KeyError:
                        continue
                    selected.append(
                        {**linked, "score": record["score"], "linked_from": record["id"]}
                    )
                    seen.add(identifier)
                    if len(selected) >= limit * 2:
                        return selected
        return selected
