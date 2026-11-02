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

from evosprig.config import make_models, make_tools, restore_models
from evosprig.core.journal import Scope
from evosprig.core.runtime import Runtime
from evosprig.core.spec import AgentSpec, Contract, canonical_json, digest
from evosprig.core.version import SECRET, compile_agent, compile_snapshot
from evosprig.exporters.python import builder_source, export_python
from evosprig.plugins.sqlite_journal import SQLiteJournal
from evosprig.plugins.sqlite_memory import SQLiteMemory
from evosprig.plugins.sqlite_projects import ProjectStore, RevisionConflict
from evosprig.plugins.sqlite_studies import StudyStore

from .auth import Principal, current_principal
from .canvas import to_canvas
from .canvas_state import CanvasState
from .evolution_api import install_evolution_routes
from .memory_api import install_memory_routes
from .studies import StudyWorker
from .worker import Worker


class ProjectBody(Contract):
    spec: AgentSpec
    resources: dict[str, str] | None = None
    layout: dict[str, dict[str, float]] = Field(default_factory=dict)
    canvas: CanvasState | None = None


class UpdateBody(ProjectBody):
    revision: int = Field(ge=1)


class RunBody(Contract):
    input: dict[str, Any]
    revision: int = Field(ge=1)
    mock: bool = True
    allow_writes: bool = False
    version_id: str | None = None
    use_release: bool = False


class InputBody(Contract):
    path: str = Field(min_length=1, max_length=2048)
    response: dict[str, Any]


def create_app(
    workspace: str | Path,
    *,
    profile: str | Path | None = None,
    studio_dir: str | Path | None = None,
    token: str | None = None,
    max_concurrent_runs: int = 4,
    principals: dict[str, Principal] | None = None,
) -> FastAPI:
    workspace = Path(workspace)
    workspace.mkdir(parents=True, exist_ok=True)
    store = ProjectStore(workspace / "projects.sqlite")
    journal = SQLiteJournal(workspace / "runs.sqlite")
    memory = SQLiteMemory(workspace / "memory.sqlite")
    if token and principals:
        raise ValueError("choose either a workspace token or per-user principals")
    if principals is not None and not principals:
        raise ValueError("principals cannot be empty")

    def tools_for(scope, bindings=None):
        return make_tools(workspace, scope, profile=profile, bindings=bindings)

    def restore_runtime(record):
        models = restore_models(record["metadata"]["models"])
        return Runtime(
            models,
            tools_for(Scope(**record["scope"]), record["metadata"].get("tools", {})),
            journal=journal,
            allow_writes=record["metadata"]["allow_writes"],
        )

    worker = Worker(journal, restore_runtime, max_concurrent_runs)
    studies = StudyStore(workspace / "studies.sqlite")
    study_worker = StudyWorker(studies, workspace / "evaluation")

    @asynccontextmanager
    async def lifespan(app):
        await worker.start()
        await study_worker.start()
        try:
            yield
        finally:
            await study_worker.stop()
            await worker.stop()

    app = FastAPI(title="EvoSprig", version="0.1.0", lifespan=lifespan)
    app.state.projects = store
    app.state.journal = journal
    app.state.worker = worker
    app.state.memory = memory
    app.state.studies = studies
    app.state.study_worker = study_worker
    install_memory_routes(app, memory, store)

    @app.middleware("http")
    async def boundary(request: Request, call_next):
        if request.url.hostname not in {"localhost", "127.0.0.1", "::1"}:
            return JSONResponse({"detail": "use a loopback host"}, status_code=400)
        origin = request.headers.get("origin")
        if origin and origin.rstrip("/") != str(request.base_url).rstrip("/"):
            return JSONResponse({"detail": "cross-origin requests are disabled"}, status_code=403)
        principal = Principal()
        if request.url.path.startswith("/api/") and principals is not None:
            provided = request.headers.get("authorization", "")
            principal = next(
                (
                    identity
                    for secret, identity in principals.items()
                    if secrets.compare_digest(provided, "Bearer " + secret)
                ),
                None,
            )
            if principal is None:
                return JSONResponse({"detail": "authentication required"}, status_code=401)
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
        context = current_principal.set(principal)
        try:
            return await call_next(request)
        finally:
            current_principal.reset(context)

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
        principal = current_principal.get()
        root = (
            workspace
            if principal == Principal()
            else workspace / "identities" / digest(principal.key)
        )
        return root / "projects" / project_id

    def compile_document(document):
        if document.get("resources") is not None:
            return compile_snapshot(
                AgentSpec.model_validate(document["spec"]), document["resources"]
            )
        return compile_agent(
            AgentSpec.model_validate(document["spec"]), project_root(document["id"])
        )

    def validate_project(body):
        try:
            canonical_json(body.layout)
            if body.canvas is not None:
                body.canvas.validate_for(body.spec)
            if body.resources is None:
                compile_agent(body.spec, project_root(body.spec.id))
            else:
                compile_snapshot(body.spec, body.resources)
        except (ValueError, OSError, ValidationError):
            raise HTTPException(422, "project resources or content failed validation") from None

    install_evolution_routes(
        app, studies, study_worker, store, compile_document, tools_for, profile
    )

    @app.get("/api/health")
    async def health():
        return {
            "status": "degraded" if worker.last_error else "ok",
            "stage": "alpha",
            "spec_version": "0.2",
            "worker_error": worker.last_error,
        }

    @app.get("/api/schema")
    async def schema():
        return AgentSpec.model_json_schema()

    def public_document(document):
        if document.get("resources") is None:
            return {**document, "resources": compile_document(document).resources}
        return document

    @app.get("/api/projects")
    async def projects():
        return [public_document(item) for item in store.list(identity=current_principal.get().key)]

    @app.post("/api/import/inspect")
    async def inspect_import(request: Request):
        from evosprig.exporters.importer import inspect_archive

        data = bytearray()
        async for chunk in request.stream():
            data.extend(chunk)
            if len(data) > 2_000_000:
                raise HTTPException(413, "archive exceeds 2 MB API limit; use CLI")
        try:
            version, report = inspect_archive(bytes(data))
        except ValueError:
            raise HTTPException(422, "invalid or unsupported export archive") from None
        return {
            "spec": version.spec.model_dump(mode="json"),
            "resources": version.resources,
            "report": report,
        }

    @app.post("/api/projects", status_code=201)
    async def create_project(body: ProjectBody):
        validate_project(body)
        return store.create(
            body.spec,
            body.layout,
            resources=body.resources,
            identity=current_principal.get().key,
            canvas=body.canvas.model_dump() if body.canvas is not None else None,
        )

    @app.get("/api/projects/{project_id}")
    async def project(project_id: str):
        return public_document(store.get(project_id, identity=current_principal.get().key))

    @app.put("/api/projects/{project_id}")
    async def update_project(project_id: str, body: UpdateBody):
        if project_id != body.spec.id:
            raise HTTPException(422, "project id cannot change")
        existing = store.get(project_id, identity=current_principal.get().key)
        if body.resources is None and existing.get("resources") is not None:
            body = body.model_copy(update={"resources": existing["resources"]})
        validate_project(body)
        return store.update(
            project_id,
            body.spec,
            body.layout,
            body.revision,
            resources=body.resources,
            canvas=body.canvas.model_dump() if body.canvas is not None else None,
            identity=current_principal.get().key,
        )

    @app.get("/api/projects/{project_id}/canvas")
    async def canvas(project_id: str):
        document = store.get(project_id, identity=current_principal.get().key)
        return to_canvas(AgentSpec.model_validate(document["spec"]), document["layout"])

    @app.get("/api/projects/{project_id}/code")
    async def code(project_id: str):
        return {
            "code": builder_source(
                compile_document(store.get(project_id, identity=current_principal.get().key))
            )
        }

    def run_record(run_id: str):
        try:
            record = journal.get(run_id)
        except KeyError:
            # Legacy data belongs exclusively to the original local principal.
            if current_principal.get() != Principal():
                raise KeyError("run not found") from None
            with store.connect() as db:
                if not db.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name='runs'"
                ).fetchone():
                    raise KeyError("run not found") from None
                row = db.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
            if not row:
                raise KeyError("run not found")
            legacy = {
                "run_id": run_id,
                "project_id": row["project_id"],
                **json.loads(row["result"]),
                "status": row["status"],
                "legacy": True,
            }
            if legacy["status"] in {"queued", "running"}:
                legacy.update(
                    status="failed",
                    error={
                        "code": "legacy_no_checkpoint",
                        "message": "M0 run has no recoverable checkpoint",
                    },
                )
            return legacy

        principal = current_principal.get()
        if record["scope"] != {
            "project": record["scope"]["project"],
            "user": principal.user,
            "tenant": principal.tenant,
        }:
            raise KeyError("run not found")
        checkpoint = record["checkpoint"]
        return {
            "run_id": run_id,
            "project_id": record["scope"]["project"],
            "agent_version": record["version"]["version_id"],
            "status": record["status"],
            "output": checkpoint["output"],
            "error": checkpoint["error"],
            "usage": checkpoint["usage"],
            "waiting": checkpoint["waiting"],
            "duration_seconds": checkpoint["active_seconds"],
            "events": journal.events(run_id),
            "cancel_requested": record["cancel_requested"],
        }

    @app.get("/api/projects/{project_id}/runs")
    async def project_runs(project_id: str):
        store.get(project_id, identity=current_principal.get().key)
        return [
            run_record(record["run_id"])
            for record in journal.list(current_principal.get().scope(project_id))
        ]

    @app.post("/api/projects/{project_id}/runs", status_code=202)
    async def start_run(project_id: str, body: RunBody):
        document = store.get(project_id, identity=current_principal.get().key)
        if document["revision"] != body.revision and not (body.version_id or body.use_release):
            raise RevisionConflict("save or reload the current project before running")
        try:
            if body.version_id and body.use_release:
                raise ValueError("choose a specific version or the active release")
            selected_id = body.version_id or (
                studies.release(current_principal.get().scope(project_id))["version_id"]
                if body.use_release
                else None
            )
            if body.use_release and selected_id is None:
                raise ValueError("project has no active release")
            version = (
                studies.get(current_principal.get().scope(project_id), selected_id)
                if selected_id
                else compile_document(document)
            )
            runtime = Runtime(
                make_models(version.spec, profile, body.mock),
                tools_for(current_principal.get().scope(project_id)),
                journal=journal,
                allow_writes=body.allow_writes,
            )
            run_id = runtime.create_run(
                version, body.input, scope=current_principal.get().scope(project_id)
            )
        except (ValueError, OSError):
            raise HTTPException(
                422, "model configuration or project resources are invalid"
            ) from None
        worker.dispatch(run_id)
        return {"run_id": run_id, "status": "queued", "agent_version": version.version_id}

    @app.get("/api/runs/{run_id}")
    async def run(run_id: str):
        return run_record(run_id)

    @app.post("/api/runs/{run_id}/input", status_code=202)
    async def provide_input(run_id: str, body: InputBody):
        record = run_record(run_id)
        try:
            journal.respond(
                run_id,
                body.path,
                body.response,
                current_principal.get().scope(record["project_id"]),
            )
        except ValueError:
            raise HTTPException(409, "run is not waiting for this response") from None
        except Exception as exc:
            if type(exc).__name__ == "ValidationError":
                raise HTTPException(
                    422, "response does not match the waiting node schema"
                ) from None
            raise
        worker.dispatch(run_id)
        return {"run_id": run_id, "status": "queued"}

    @app.post("/api/runs/{run_id}/resume", status_code=202)
    async def resume_run(run_id: str):
        record = run_record(run_id)
        if record["status"] not in {"queued", "running", "waiting_external"}:
            raise HTTPException(409, "this run is not ready to resume")
        worker.dispatch(run_id)
        return {"run_id": run_id, "status": record["status"]}

    @app.post("/api/runs/{run_id}/cancel", status_code=202)
    async def cancel_run(run_id: str):
        record = run_record(run_id)
        journal.cancel(run_id, current_principal.get().scope(record["project_id"]))
        worker.dispatch(run_id)
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
                if run_record(run_id).get("legacy"):
                    with store.connect() as db:
                        items = [
                            json.loads(row[0])
                            for row in db.execute(
                                "SELECT body FROM events WHERE run_id=? AND sequence>? ORDER BY sequence",
                                (run_id, sequence),
                            )
                        ]
                else:
                    items = journal.events(run_id, sequence)
                for event in items:
                    sequence = event["sequence"]
                    yield f"id: {sequence}\ndata: {canonical_json(event)}\n\n"
                if run_record(run_id)["status"] not in {"queued", "running"}:
                    return
                if await request.is_disconnected():
                    return
                await asyncio.sleep(0.1)

        return StreamingResponse(
            stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"}
        )

    @app.post("/api/projects/{project_id}/export")
    async def export(project_id: str, version_id: str | None = None, target: str = "python"):
        document = store.get(project_id, identity=current_principal.get().key)
        version = (
            studies.get(current_principal.get().scope(project_id), version_id)
            if version_id
            else compile_document(document)
        )
        path = workspace / "exports" / uuid.uuid4().hex
        try:
            export_python(
                version,
                path,
                target=target,
                tool_bindings=tools_for(current_principal.get().scope(project_id)).bindings,
            )
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
