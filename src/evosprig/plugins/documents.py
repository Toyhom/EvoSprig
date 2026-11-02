"""Text document ingestion and lexical retrieval with verifiable source offsets."""

from evosprig.core.spec import digest


class DocumentRetriever:
    def __init__(self, memory):
        self.memory = memory

    def ingest(self, scope, *, title, text, source, chunk_size=1000):
        if not title or len(title) > 500 or not text.strip() or len(text) > 1_000_000:
            raise ValueError("document needs a title and 1..1000000 characters")
        if not 200 <= chunk_size <= 4000:
            raise ValueError("chunk_size must be between 200 and 4000")
        document_id = digest({"title": title, "text": text, "source": source})
        chunks = []
        for start in range(0, len(text), chunk_size):
            end = min(len(text), start + chunk_size)
            chunk = text[start:end]
            if not chunk.strip():
                continue
            chunks.append(
                self.memory.write(
                    scope,
                    chunk,
                    source=source,
                    content_type="document",
                    metadata={
                        "document_id": document_id,
                        "title": title,
                        "start": start,
                        "end": end,
                        "text_hash": digest(text),
                        "excerpt": chunk,
                    },
                    idempotency_key=f"document:{document_id}:{start}",
                )
            )
        return {
            "document_id": document_id,
            "chunks": len(chunks),
            "record_ids": [item["id"] for item in chunks],
        }

    def search(self, scope, query, *, limit=5):
        hits = self.memory.search(scope, query, limit=limit)
        return [
            {
                "citation": f"[{hit['metadata']['document_id'][:12]}:{hit['metadata']['start']}-{hit['metadata']['end']}]",
                "record_id": hit["id"],
                "title": hit["metadata"]["title"],
                "source": hit["source"],
                "start": hit["metadata"]["start"],
                "end": hit["metadata"]["end"],
                "text": hit["metadata"]["excerpt"],
                "score": hit["score"],
            }
            for hit in hits
            if hit["content_type"] == "document" and "document_id" in hit["metadata"]
        ]
