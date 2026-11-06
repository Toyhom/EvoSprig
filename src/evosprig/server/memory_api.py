"""Memory and document routes whose authority comes exclusively from the server principal."""

import asyncio

from fastapi import HTTPException, Query
from pydantic import Field

from evosprig.core.memory import MemoryConflict
from evosprig.core.spec import Contract
from evosprig.plugins.memory_banks import MemoryBankConfig, MemoryBanks
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


def install_memory_routes(app, memory, projects, *, banks=None):
    structured = StructuredMemory(memory)
    banks = banks or MemoryBanks(memory)

    def scope(project, bank="default"):
        principal = current_principal.get()
        projects.get(project, identity=principal.key)
        return banks.scope(principal.scope(project), bank)

    @app.exception_handler(MemoryConflict)
    async def memory_conflict(request, exc):
        from fastapi.responses import JSONResponse

        return JSONResponse({"detail": str(exc)}, status_code=409)

    @app.get("/api/projects/{project_id}/memory/banks")
    async def memory_banks(project_id: str):
        return banks.config(scope(project_id).identity).model_dump()

    @app.put("/api/projects/{project_id}/memory/banks/{bank}")
    async def configure_bank(project_id: str, bank: str, body: MemoryBankConfig):
        try:
            return banks.configure(scope(project_id).identity, bank, body.model_dump()).model_dump()
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None

    @app.get("/api/projects/{project_id}/memory")
    async def search_memory(project_id: str, query: str = "", limit: int = Query(20, ge=1, le=100), bank: str = "default"):
        selected = scope(project_id, bank)
        return await asyncio.to_thread(banks.backend(selected.identity, bank).search, selected, query, limit=limit)

    @app.post("/api/projects/{project_id}/memory", status_code=201)
    async def write_memory(project_id: str, body: MemoryBody, bank: str = "default"):
        if not body.content.strip():
            raise HTTPException(422, "memory content cannot be whitespace")
        return memory.write(scope(project_id, bank), body.content, source=body.source)

    @app.get("/api/projects/{project_id}/memory/export")
    async def export_memory(project_id: str, bank: str = "default"):
        return memory.export(scope(project_id, bank))

    @app.get("/api/projects/{project_id}/context")
    async def context_blocks(project_id: str, max_chars: int = Query(12000, ge=1, le=1000000), bank: str = "default"):
        return structured.context(scope(project_id, bank), max_chars=max_chars)

    @app.put("/api/projects/{project_id}/context/{name}")
    async def set_context(project_id: str, name: str, body: ContextBody, bank: str = "default"):
        try:
            return structured.set_context(scope(project_id, bank), name, **body.model_dump())
        except MemoryConflict:
            raise
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None

    @app.get("/api/projects/{project_id}/relations")
    async def relations(
        project_id: str, subject: str, at: float | None = None, hops: int = Query(1, ge=1, le=4), bank: str = "default"
    ):
        return structured.relations(scope(project_id, bank), subject, at=at, hops=hops)

    @app.post("/api/projects/{project_id}/relations", status_code=201)
    async def set_relation(project_id: str, body: RelationBody, bank: str = "default"):
        try:
            return structured.set_relation(scope(project_id, bank), **body.model_dump())
        except MemoryConflict:
            raise
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None

    @app.get("/api/projects/{project_id}/memory/{record_id}")
    async def get_memory(project_id: str, record_id: str, bank: str = "default"):
        return memory.get(scope(project_id, bank), record_id)

    @app.put("/api/projects/{project_id}/memory/{record_id}")
    async def update_memory(project_id: str, record_id: str, body: MemoryUpdate, bank: str = "default"):
        if not body.content.strip():
            raise HTTPException(422, "memory content cannot be whitespace")
        return memory.update(scope(project_id, bank), record_id, body.content, revision=body.revision)

    @app.delete("/api/projects/{project_id}/memory/{record_id}")
    async def delete_memory(project_id: str, record_id: str, bank: str = "default"):
        memory.delete(scope(project_id, bank), record_id)
        return {"deleted": record_id}
