"""Memory and document routes whose authority comes exclusively from the server principal."""

from fastapi import HTTPException, Query
from pydantic import Field

from evosprig.core.memory import MemoryConflict, MemoryScope
from evosprig.core.spec import Contract
from evosprig.plugins.documents import DocumentRetriever

from .auth import current_principal


class MemoryBody(Contract):
    content: str = Field(min_length=1, max_length=100000)
    source: str = Field(min_length=1, max_length=2048)


class MemoryUpdate(Contract):
    content: str = Field(min_length=1, max_length=100000)
    revision: int = Field(ge=1)


class DocumentBody(Contract):
    title: str = Field(min_length=1, max_length=500)
    text: str = Field(min_length=1, max_length=1000000)
    source: str = Field(min_length=1, max_length=2048)


def install_memory_routes(app, memory, projects):
    def scope(project, namespace="default"):
        principal = current_principal.get()
        projects.get(project, identity=principal.key)
        return MemoryScope(principal.scope(project), namespace=namespace)

    @app.exception_handler(MemoryConflict)
    async def memory_conflict(request, exc):
        from fastapi.responses import JSONResponse

        return JSONResponse({"detail": str(exc)}, status_code=409)

    @app.get("/api/projects/{project_id}/memory")
    async def search_memory(project_id: str, query: str = "", limit: int = Query(20, ge=1, le=100)):
        return memory.search(scope(project_id), query, limit=limit)

    @app.post("/api/projects/{project_id}/memory", status_code=201)
    async def write_memory(project_id: str, body: MemoryBody):
        if not body.content.strip():
            raise HTTPException(422, "memory content cannot be whitespace")
        return memory.write(scope(project_id), body.content, source=body.source)

    @app.get("/api/projects/{project_id}/memory/export")
    async def export_memory(project_id: str):
        return memory.export(scope(project_id))

    @app.get("/api/projects/{project_id}/memory/{record_id}")
    async def get_memory(project_id: str, record_id: str):
        return memory.get(scope(project_id), record_id)

    @app.put("/api/projects/{project_id}/memory/{record_id}")
    async def update_memory(project_id: str, record_id: str, body: MemoryUpdate):
        if not body.content.strip():
            raise HTTPException(422, "memory content cannot be whitespace")
        return memory.update(scope(project_id), record_id, body.content, revision=body.revision)

    @app.delete("/api/projects/{project_id}/memory/{record_id}")
    async def delete_memory(project_id: str, record_id: str):
        memory.delete(scope(project_id), record_id)
        return {"deleted": record_id}

    @app.get("/api/projects/{project_id}/documents")
    async def documents(project_id: str):
        grouped = {}
        for record in memory.export(scope(project_id, "documents")):
            metadata = record["metadata"]
            identifier = metadata["document_id"]
            grouped.setdefault(
                identifier,
                {
                    "id": identifier,
                    "title": metadata["title"],
                    "source": record["source"],
                    "chunks": 0,
                },
            )["chunks"] += 1
        return list(grouped.values())

    @app.post("/api/projects/{project_id}/documents", status_code=201)
    async def ingest_document(project_id: str, body: DocumentBody):
        try:
            return DocumentRetriever(memory).ingest(
                scope(project_id, "documents"), **body.model_dump()
            )
        except ValueError:
            raise HTTPException(422, "invalid document") from None

    @app.get("/api/projects/{project_id}/documents/search")
    async def search_documents(project_id: str, query: str, limit: int = Query(5, ge=1, le=20)):
        return DocumentRetriever(memory).search(scope(project_id, "documents"), query, limit=limit)

    @app.delete("/api/projects/{project_id}/documents/{document_id}")
    async def delete_document(project_id: str, document_id: str):
        selected = scope(project_id, "documents")
        ids = [
            record["id"]
            for record in memory.export(selected)
            if record["metadata"].get("document_id") == document_id
        ]
        if not ids:
            raise KeyError("document not found")
        for identifier in ids:
            memory.delete(selected, identifier)
        return {"deleted": document_id, "chunks": len(ids)}
