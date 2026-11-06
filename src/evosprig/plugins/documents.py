"""Document chunks, exact source offsets, page citations and indexed retrieval."""

import time
from dataclasses import asdict

from evosprig.core.memory import MemoryRecord
from evosprig.core.spec import digest


class DocumentRetriever:
    def __init__(self, memory):
        self.memory = memory

    def ingest(self, scope, *, title, text, source, chunk_size=1000, chunk_overlap=0,
               max_chars=None, pages=None, replace=False, revision=None, submitted_at=None):
        if not title or len(title) > 500 or not text.strip():
            raise ValueError("document needs a title and nonempty text")
        if max_chars is not None and len(text) > max_chars:
            raise ValueError(f"document exceeds configured {max_chars} extracted characters")
        if not 200 <= chunk_size <= 100000 or not 0 <= chunk_overlap < chunk_size:
            raise ValueError("chunk_size must be 200..100000; overlap must be smaller than the chunk")
        document_id = digest({"title": title, "text": text, "source": source,
                              "chunk_size": chunk_size, "chunk_overlap": chunk_overlap, "revision": revision})
        text_hash, records, now = digest(text), [], time.time()
        for start in range(0, len(text), chunk_size - chunk_overlap):
            end = min(len(text), start + chunk_size)
            chunk = text[start:end]
            if not chunk.strip():
                continue
            metadata = {"document_id": document_id, "title": title, "start": start,
                        "end": end, "text_hash": text_hash, "excerpt": chunk}
            if submitted_at is not None:
                metadata["submitted_at"] = submitted_at
            selected = [p["page"] for p in (pages or []) if p["start"] < end and p["end"] > start]
            if selected:
                metadata["pages"] = selected
            records.append(MemoryRecord(
                id=digest([scope.key, f"document:{document_id}:{start}"]), scope=asdict(scope),
                content=chunk.strip(), source=source, content_type="document", metadata=metadata,
                confidence=1.0, created_at=now, updated_at=now,
            ).model_dump())
            if end == len(text):
                break
        if hasattr(self.memory, "replace_documents"):
            self.memory.replace_documents(scope, records, source=source if replace else None)
        else:
            if replace:
                raise ValueError("this memory adapter does not support atomic document replacement")
            records = [self.memory.write(
                scope, r["content"], source=source, content_type="document", metadata=r["metadata"],
                idempotency_key=f"document:{document_id}:{r['metadata']['start']}",
            ) for r in records]
        return {"document_id": document_id, "chunks": len(records), "record_ids": [r["id"] for r in records]}

    def search(self, scope, query, *, limit=5):
        # Semantic wrappers implement search themselves. Do not bypass their rank fusion.
        search = self.memory.search if hasattr(self.memory, "embedder") else getattr(self.memory, "search_indexed", self.memory.search)
        hits = search(scope, query, limit=limit, content_type="document")
        return [{
            "citation": f"[{hit['metadata']['document_id'][:12]}:{hit['metadata']['start']}-{hit['metadata']['end']}]",
            "record_id": hit["id"], "title": hit["metadata"]["title"], "source": hit["source"],
            "start": hit["metadata"]["start"], "end": hit["metadata"]["end"],
            "text": hit["metadata"]["excerpt"], "score": hit["score"],
            **({"pages": hit["metadata"]["pages"]} if "pages" in hit["metadata"] else {}),
        } for hit in hits if hit["content_type"] == "document" and "document_id" in hit["metadata"]]
