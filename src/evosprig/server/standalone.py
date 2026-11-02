"""Single-agent HTTP deployment, independent of Studio and the project database."""

import asyncio
import json
import secrets
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, StreamingResponse
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

from evosprig.config import make_models, make_tools, restore_models
from evosprig.core.journal import Scope
from evosprig.core.runtime import Runtime
from evosprig.core.spec import Contract, canonical_json, load_spec
from evosprig.core.version import compile_agent
from evosprig.plugins.sqlite_journal import SQLiteJournal

from .worker import Worker


class RunInput(Contract):
    input: dict


class HumanInput(Contract):
    path: str
    response: dict


def create_service(
    root, workspace, *, token, profile=None, mock=False, allow_writes=False, concurrency=4
):
    if not token:
        raise ValueError("EVOSPRIG_SERVICE_TOKEN must be set")
    root, workspace = Path(root), Path(workspace)
    version = compile_agent(load_spec(root / "agent.yaml"), root)
    if version.lock != json.loads((root / "agent.lock.json").read_text()):
        raise ValueError("exported version changed; rebuild its lock")
    scope = Scope(version.spec.id)
    journal = SQLiteJournal(workspace / "runs.sqlite")
    bindings = json.loads((root / "tool-bindings.json").read_text())

    def runtime(record=None):
        if record and record["version"]["version_id"] != version.version_id:
            raise ValueError("workspace contains a different agent version")
        return Runtime(
            restore_models(record["metadata"]["models"])
            if record
            else make_models(version.spec, profile, mock),
            make_tools(
                workspace,
                scope,
                profile=profile,
                bindings=record["metadata"].get("tools", {})
                if record
                else (None if profile else bindings),
            ),
            journal=journal,
            allow_writes=record["metadata"]["allow_writes"] if record else allow_writes,
        )

    worker = Worker(journal, runtime, concurrency)

    @asynccontextmanager
    async def lifespan(app):
        await worker.start()
        try:
            yield
        finally:
            await worker.stop()

    app = FastAPI(title="Exported EvoSprig agent", lifespan=lifespan)

    @app.middleware("http")
    async def boundary(request: Request, call_next):
        if request.url.path != "/health":
            if not secrets.compare_digest(
                request.headers.get("authorization", ""), "Bearer " + token
            ):
                return JSONResponse({"detail": "authentication required"}, status_code=401)
        if request.headers.get("origin"):
            return JSONResponse({"detail": "browser origins are disabled"}, status_code=403)
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > 2_000_000:
                return JSONResponse({"detail": "request exceeds 2 MB"}, status_code=413)
        request._body = bytes(body)
        return await call_next(request)

    @app.exception_handler(RequestValidationError)
    @app.exception_handler(ValidationError)
    async def invalid(request, exc):
        return JSONResponse({"detail": "input does not match schema"}, status_code=422)

    @app.exception_handler(KeyError)
    async def missing(request, exc):
        return JSONResponse({"detail": "run not found"}, status_code=404)

    def read(run_id):
        record = journal.get(run_id, scope)
        if record["version"]["version_id"] != version.version_id:
            raise KeyError(run_id)
        return runtime(record).get(run_id, scope).to_dict()

    @app.get("/health")
    async def health():
        return {
            "status": "degraded" if worker.last_error else "ok",
            "agent_version": version.version_id,
        }

    @app.post("/runs", status_code=202)
    async def start(body: RunInput):
        Draft202012Validator(version.spec.input_schema).validate(body.input)
        run_id = runtime().create_run(version, body.input, scope=scope)
        worker.dispatch(run_id)
        return {"run_id": run_id, "agent_version": version.version_id}

    @app.get("/runs/{run_id}")
    async def get_run(run_id: str):
        return read(run_id)

    @app.post("/runs/{run_id}/input", status_code=202)
    async def respond(run_id: str, body: HumanInput):
        read(run_id)
        try:
            journal.respond(run_id, body.path, body.response, scope)
        except ValueError:
            raise HTTPException(409, "run is not waiting for this input") from None
        worker.dispatch(run_id)
        return {"run_id": run_id}

    @app.post("/runs/{run_id}/cancel", status_code=202)
    async def cancel(run_id: str):
        read(run_id)
        journal.cancel(run_id, scope)
        worker.dispatch(run_id)
        return {"run_id": run_id}

    @app.get("/runs/{run_id}/events")
    async def events(run_id: str, request: Request, after: int = 0):
        read(run_id)
        try:
            after = max(0, after, int(request.headers.get("last-event-id", "0")))
        except ValueError:
            raise HTTPException(422, "invalid Last-Event-ID") from None

        async def stream():
            sequence = after
            while True:
                for event in journal.events(run_id, sequence):
                    sequence = event["sequence"]
                    yield f"id: {sequence}\ndata: {canonical_json(event)}\n\n"
                if read(run_id)["status"] not in {"queued", "running"}:
                    return
                if await request.is_disconnected():
                    return
                await asyncio.sleep(0.1)

        return StreamingResponse(stream(), media_type="text/event-stream")

    return app
