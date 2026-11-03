"""Shared document editing for people and agents using the same revision checks."""

from fastapi import HTTPException, Query
from fastapi.responses import Response
from pydantic import Field

from evosprig.core.protocols import ToolRejectedError
from evosprig.core.spec import Contract

from .auth import current_principal


class DocumentEdit(Contract):
    name: str = Field(min_length=1, max_length=240)
    content: str = Field(max_length=1000000)
    expected_revision: int = Field(ge=0)
    operation_id: str = Field(min_length=1, max_length=128)
    media_type: str = "text/markdown"


def install_workspace_routes(app, documents, projects):
    def scope(project_id):
        principal = current_principal.get()
        projects.get(project_id, identity=principal.key)
        return principal.scope(project_id)

    @app.get("/api/projects/{project_id}/workspace/documents")
    async def catalog(project_id: str, prefix: str = Query("", max_length=240)):
        return documents.list(scope(project_id), prefix)

    @app.get("/api/projects/{project_id}/workspace/document")
    async def read(project_id: str, name: str, revision: int | None = Query(None, ge=1)):
        try:
            return documents.read(scope(project_id), name, revision)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None

    @app.get("/api/projects/{project_id}/workspace/history")
    async def history(project_id: str, name: str):
        try:
            return documents.history(scope(project_id), name)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None

    @app.put("/api/projects/{project_id}/workspace/document")
    async def edit(project_id: str, body: DocumentEdit):
        try:
            return documents.write(
                scope(project_id),
                body.name,
                body.content,
                body.expected_revision,
                idempotency_key=body.operation_id,
                media_type=body.media_type,
            )
        except ToolRejectedError as exc:
            raise HTTPException(409, str(exc)) from None
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None

    @app.get("/api/projects/{project_id}/workspace/download")
    async def download(project_id: str, name: str):
        from urllib.parse import quote

        try:
            item = documents.read(scope(project_id), name)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None
        if item["revision"] == 0:
            raise HTTPException(404, "document not found")
        return Response(
            item["content"],
            media_type=item["media_type"],
            headers={
                "Content-Disposition": "attachment; filename*=UTF-8''"
                + quote(name.rsplit("/", 1)[-1]),
                "X-Content-Type-Options": "nosniff",
            },
        )
