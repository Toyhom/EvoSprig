"""Multi-query reciprocal-rank fusion with optional lexical diversity selection."""

from .sqlite_memory import terms


def retrieve_many(retriever, scope, queries, *, limit=5, diversity=0.25):
    if not 1 <= len(queries) <= 8 or not 1 <= limit <= 20 or not 0 <= diversity <= 1:
        raise ValueError("invalid retrieval bounds")
    hits, scores = {}, {}
    for query in dict.fromkeys(queries):
        for rank, hit in enumerate(retriever.search(scope, query, limit=20), 1):
            key = hit.get("record_id", hit.get("id"))
            hits[key] = hit
            scores[key] = scores.get(key, 0) + 1 / (60 + rank)
    maximum = max(scores.values(), default=1)
    records = dict(hits)
    selected = []
    signatures = {key: terms(hit.get("text", hit.get("content", ""))) for key, hit in hits.items()}
    while hits and len(selected) < limit:

        def score(key):
            overlap = max(
                (
                    len(signatures[key] & signatures[other])
                    / max(1, len(signatures[key] | signatures[other]))
                    for other in selected
                ),
                default=0,
            )
            return (1 - diversity) * scores[key] / maximum - diversity * overlap

        key = min(hits, key=lambda key: (-score(key), key))
        selected.append(key)
        # Keep the record after removing it from the remaining pool.
        hits.pop(key)
    # Retrieve selected records from the original rank lists without another search.
    return [
        {**records[key], "score": scores[key], "retrieval": "multi_query_rrf"} for key in selected
    ]
