from __future__ import annotations

import asyncio
import io
import json
import secrets
import shutil
import uuid
import zipfile
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import Field, ValidationError

from evosprig.config import make_models
from evosprig.core.runtime import Runtime
from evosprig.core.spec import AgentSpec, Contract, canonical_json
from evosprig.core.version import SECRET, compile_agent
from evosprig.exporters.python import builder_source, export_python
from evosprig.plugins.builtin_tools import builtin_registry
from evosprig.plugins.sqlite_projects import ProjectStore, RevisionConflict

from .canvas import to_canvas


class ProjectBody(Contract):
    spec: AgentSpec
    layout: dict[str, dict[str, float]] = Field(default_factory=dict)


class UpdateBody(ProjectBody):
    revision: int = Field(ge=1)


class RunBody(Contract):
    input: dict[str, Any]
    revision: int = Field(ge=1)
    mock: bool = True


def create_app(
    workspace: str | Path,
    *,
    profile: str | Path | None = None,
    studio_dir: str | Path | None = None,
    token: str | None = None,
) -> FastAPI:
    workspace = Path(workspace)
    workspace.mkdir(parents=True, exist_ok=True)
    store = ProjectStore(workspace / "projects.sqlite")
    tasks: dict[str, asyncio.Task] = {}
    with store.connect() as db:
        db.execute(
            "CREATE TABLE IF NOT EXISTS runs (id TEXT PRIMARY KEY, project_id TEXT, status TEXT, result TEXT)"
        )
        db.execute(
            "CREATE TABLE IF NOT EXISTS events (run_id TEXT, sequence INTEGER, body TEXT, PRIMARY KEY(run_id, sequence))"
        )
        db.execute(
            "UPDATE runs SET status='failed', result=? WHERE status IN ('queued','running')",
            (
                canonical_json(
                    {
                        "status": "failed",
                        "error": {
                            "code": "worker_interrupted",
                            "message": "M0 worker stopped; start a new run",
                        },
                    }
                ),
            ),
        )

    @asynccontextmanager
    async def lifespan(app):
        yield
        for task in list(tasks.values()):
            task.cancel()
        await asyncio.gather(*list(tasks.values()), return_exceptions=True)

    app = FastAPI(title="EvoSprig", version="0.1.0.dev0", lifespan=lifespan)
    app.state.projects = store

    @app.middleware("http")
    async def boundary(request: Request, call_next):
        if request.url.hostname not in {"localhost", "127.0.0.1", "::1"}:
            return JSONResponse({"detail": "use a loopback host"}, status_code=400)
        origin = request.headers.get("origin")
        if origin and origin.rstrip("/") != str(request.base_url).rstrip("/"):
            return JSONResponse({"detail": "cross-origin requests are disabled"}, status_code=403)
        if request.url.path.startswith("/api/") and token:
            provided = request.headers.get("authorization", "")
            if not secrets.compare_digest(provided, "Bearer " + token):
                return JSONResponse({"detail": "authentication required"}, status_code=401)
        try:
            size = int(request.headers.get("content-length", "0"))
        except ValueError:
            return JSONResponse({"detail": "invalid content length"}, status_code=400)
        if size > 2_000_000:
            return JSONResponse({"detail": "request exceeds 2 MB"}, status_code=413)
        return await call_next(request)

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request, exc):
        return JSONResponse(
            {
                "detail": [
                    {
                        "loc": error["loc"],
                        "type": error["type"],
                        "message": SECRET.sub("[redacted]", error["msg"])[:500],
                    }
                    for error in exc.errors()
                ]
            },
            status_code=422,
        )

    @app.exception_handler(RevisionConflict)
    async def conflict(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=409)

    @app.exception_handler(KeyError)
    async def missing(request, exc):
        return JSONResponse({"detail": "record not found"}, status_code=404)

    def project_root(project_id: str):
        return workspace / "projects" / project_id

    def compile_document(document):
        return compile_agent(
            AgentSpec.model_validate(document["spec"]), project_root(document["id"])
        )

    def validate_project(body):
        try:
            canonical_json(body.layout)
            compile_agent(body.spec, project_root(body.spec.id))
        except (ValueError, OSError, ValidationError):
            raise HTTPException(422, "project resources or content failed validation") from None

    @app.get("/api/health")
    async def health():
        return {"status": "ok", "stage": "M0", "spec_version": "0.1"}

    @app.get("/api/schema")
    async def schema():
        return AgentSpec.model_json_schema()

    @app.get("/api/projects")
    async def projects():
        return store.list()

    @app.post("/api/projects", status_code=201)
    async def create_project(body: ProjectBody):
        validate_project(body)
        return store.create(body.spec, body.layout)

    @app.get("/api/projects/{project_id}")
    async def project(project_id: str):
        return store.get(project_id)

    @app.put("/api/projects/{project_id}")
    async def update_project(project_id: str, body: UpdateBody):
        if project_id != body.spec.id:
            raise HTTPException(422, "project id cannot change")
        validate_project(body)
        return store.update(project_id, body.spec, body.layout, body.revision)

    @app.get("/api/projects/{project_id}/canvas")
    async def canvas(project_id: str):
        document = store.get(project_id)
        return to_canvas(AgentSpec.model_validate(document["spec"]), document["layout"])

    @app.get("/api/projects/{project_id}/code")
    async def code(project_id: str):
        return {"code": builder_source(compile_document(store.get(project_id)))}

    def run_record(run_id: str):
        with store.connect() as db:
            row = db.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
        if not row:
            raise KeyError(run_id)
        return {
            "run_id": run_id,
            "project_id": row["project_id"],
            **json.loads(row["result"]),
            "status": row["status"],
        }

    @app.post("/api/projects/{project_id}/runs", status_code=202)
    async def start_run(project_id: str, body: RunBody):
        document = store.get(project_id)
        if document["revision"] != body.revision:
            raise RevisionConflict("save or reload the current project before running")
        if len(tasks) >= 4:
            raise HTTPException(429, "four runs are already active")
        try:
            version = compile_document(document)
            runtime = Runtime(make_models(version.spec, profile, body.mock), builtin_registry())
        except (ValueError, OSError):
            raise HTTPException(
                422, "model configuration or project resources are invalid"
            ) from None
        run_id = uuid.uuid4().hex
        with store.connect() as db:
            db.execute(
                "INSERT INTO runs VALUES (?, ?, 'queued', ?)",
                (run_id, project_id, canonical_json({"agent_version": version.version_id})),
            )

        def record_event(event):
            with store.connect() as db:
                db.execute(
                    "INSERT INTO events VALUES (?, ?, ?)",
                    (run_id, event["sequence"], canonical_json(event)),
                )

        async def work():
            try:
                with store.connect() as db:
                    db.execute("UPDATE runs SET status='running' WHERE id=?", (run_id,))
                result = await runtime.run(
                    version, body.input, run_id=run_id, on_event=record_event
                )
                with store.connect() as db:
                    db.execute(
                        "UPDATE runs SET status=?, result=? WHERE id=?",
                        (result.status, canonical_json(result.to_dict()), run_id),
                    )
            finally:
                with store.connect() as db:
                    db.execute(
                        "UPDATE runs SET status='canceled' WHERE id=? AND status IN ('queued','running')",
                        (run_id,),
                    )

        task = asyncio.create_task(work())
        tasks[run_id] = task
        task.add_done_callback(lambda _: tasks.pop(run_id, None))
        return {"run_id": run_id, "status": "queued", "agent_version": version.version_id}

    @app.get("/api/runs/{run_id}")
    async def run(run_id: str):
        return run_record(run_id)

    @app.post("/api/runs/{run_id}/cancel")
    async def cancel_run(run_id: str):
        run_record(run_id)
        if task := tasks.get(run_id):
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            with store.connect() as db:
                db.execute(
                    "UPDATE runs SET status='canceled' WHERE id=? AND status IN ('queued','running')",
                    (run_id,),
                )
        return run_record(run_id)

    @app.get("/api/runs/{run_id}/events")
    async def events(run_id: str, request: Request, after: int = 0):
        run_record(run_id)
        try:
            after = max(after, int(request.headers.get("last-event-id", "0")))
        except ValueError:
            raise HTTPException(422, "Last-Event-ID must be an integer") from None

        async def stream():
            sequence = after
            while True:
                with store.connect() as db:
                    rows = db.execute(
                        "SELECT sequence,body FROM events WHERE run_id=? AND sequence>? ORDER BY sequence",
                        (run_id, sequence),
                    ).fetchall()
                for row in rows:
                    sequence = row["sequence"]
                    yield f"id: {sequence}\ndata: {row['body']}\n\n"
                if run_record(run_id)["status"] not in {"queued", "running"}:
                    return
                if await request.is_disconnected():
                    return
                await asyncio.sleep(0.1)

        return StreamingResponse(
            stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"}
        )

    @app.post("/api/projects/{project_id}/export")
    async def export(project_id: str):
        version = compile_document(store.get(project_id))
        path = workspace / "exports" / uuid.uuid4().hex
        try:
            export_python(version, path)
            output = io.BytesIO()
            with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
                for file in sorted(path.rglob("*")):
                    if file.is_file():
                        archive.write(file, file.relative_to(path))
            output.seek(0)
        except ValueError:
            raise HTTPException(422, "project has unsupported export capabilities") from None
        finally:
            if path.exists():
                shutil.rmtree(path)
        return StreamingResponse(
            output,
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="{project_id}.zip"'},
        )

    if studio_dir:
        app.mount("/", StaticFiles(directory=studio_dir, html=True), name="studio")
    return app
