"""Memory and document routes whose authority comes exclusively from the server principal."""

from fastapi import HTTPException, Query
from pydantic import Field

from evosprig.core.memory import MemoryConflict, MemoryScope
from evosprig.core.spec import Contract
from evosprig.plugins.structured_memory import StructuredMemory

from .auth import current_principal


class MemoryBody(Contract):
    content: str = Field(min_length=1, max_length=100000)
    source: str = Field(min_length=1, max_length=2048)


class MemoryUpdate(Contract):
    content: str = Field(min_length=1, max_length=100000)
    revision: int = Field(ge=1)


class ContextBody(MemoryBody):
    revision: int = Field(default=0, ge=0)
    max_chars: int = Field(default=4000, ge=1, le=100000)


class RelationBody(Contract):
    subject: str = Field(min_length=1, max_length=1024)
    predicate: str = Field(min_length=1, max_length=1024)
    object_: str = Field(min_length=1, max_length=1024)
    source: str = Field(min_length=1, max_length=2048)
    valid_from: float | None = None


def install_memory_routes(app, memory, projects):
    structured = StructuredMemory(memory)

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

    @app.get("/api/projects/{project_id}/context")
    async def context_blocks(project_id: str, max_chars: int = Query(12000, ge=1, le=1000000)):
        return structured.context(scope(project_id), max_chars=max_chars)

    @app.put("/api/projects/{project_id}/context/{name}")
    async def set_context(project_id: str, name: str, body: ContextBody):
        try:
            return structured.set_context(scope(project_id), name, **body.model_dump())
        except MemoryConflict:
            raise
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None

    @app.get("/api/projects/{project_id}/relations")
    async def relations(
        project_id: str, subject: str, at: float | None = None, hops: int = Query(1, ge=1, le=4)
    ):
        return structured.relations(scope(project_id), subject, at=at, hops=hops)

    @app.post("/api/projects/{project_id}/relations", status_code=201)
    async def set_relation(project_id: str, body: RelationBody):
        try:
            return structured.set_relation(scope(project_id), **body.model_dump())
        except MemoryConflict:
            raise
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None

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
