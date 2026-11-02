"""Local single-worker renderer with durable idempotent job records."""

import asyncio
import json
import os
import secrets
import sqlite3
import threading
from contextlib import asynccontextmanager
from pathlib import Path

from build_agent import STORY
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from jsonschema import Draft202012Validator
from render import render


def create_renderer(state, artifacts, token):
    state, artifacts = Path(state), Path(artifacts)
    state.mkdir(parents=True, exist_ok=True)
    if not token:
        raise ValueError("EVOSPRIG_RENDER_TOKEN must be set")
    database = state / "jobs.sqlite"

    def connect():
        db = sqlite3.connect(database, timeout=30)
        db.row_factory = sqlite3.Row
        return db

    with connect() as db:
        db.execute(
            "CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, payload TEXT NOT NULL, status TEXT NOT NULL, output TEXT, attempts INTEGER NOT NULL DEFAULT 0)"
        )
    signals = {}
    shutdown = asyncio.Event()

    async def worker():
        while not shutdown.is_set():
            with connect() as db:
                row = db.execute(
                    "SELECT * FROM jobs WHERE status='pending' ORDER BY rowid LIMIT 1"
                ).fetchone()
            if row:
                job_id = row["id"]
                event = signals.setdefault(job_id, threading.Event())
                with connect() as db:
                    db.execute("UPDATE jobs SET attempts=attempts+1 WHERE id=?", (job_id,))
                output = artifacts / (job_id + ".mp4")
                try:
                    checksum = await asyncio.to_thread(
                        render, json.loads(row["payload"]), output, event
                    )
                    result = {
                        "path": str(output.resolve()),
                        "sha256": checksum,
                        "media_type": "video/mp4",
                        "duration_seconds": 18,
                        "job_id": job_id,
                    }
                    status = "succeeded"
                except InterruptedError:
                    status, result = "canceled", None
                except Exception:
                    status, result = "failed", None
                with connect() as db:
                    db.execute(
                        "UPDATE jobs SET status=?, output=? WHERE id=? AND status='pending'",
                        (status, json.dumps(result), job_id),
                    )
                signals.pop(job_id, None)
            else:
                try:
                    await asyncio.wait_for(shutdown.wait(), 0.2)
                except TimeoutError:
                    pass

    @asynccontextmanager
    async def lifespan(app):
        task = asyncio.create_task(worker())
        try:
            yield
        finally:
            shutdown.set()
            await task

    app = FastAPI(lifespan=lifespan)

    @app.middleware("http")
    async def auth(request: Request, call_next):
        if request.url.path != "/health" and not secrets.compare_digest(
            request.headers.get("authorization", ""), "Bearer " + token
        ):
            return JSONResponse({"detail": "authentication required"}, status_code=401)
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > 100_000:
                return JSONResponse({"detail": "request too large"}, status_code=413)
        request._body = bytes(body)
        return await call_next(request)

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.post("/jobs")
    async def submit(request: Request):
        import re

        key = request.headers.get("idempotency-key", "")
        if not re.fullmatch(r"[a-f0-9]{64}", key):
            raise HTTPException(422, "a SHA-256 operation key is required")
        try:
            body = await request.json()
            if set(body) != {"storyboard"}:
                raise ValueError("invalid body")
            Draft202012Validator(STORY).validate(body["storyboard"])
            payload = json.dumps(body["storyboard"], sort_keys=True)
        except Exception:
            raise HTTPException(422, "invalid storyboard") from None
        with connect() as db:
            db.execute(
                "INSERT OR IGNORE INTO jobs(id,payload,status) VALUES (?,?,?)",
                (key, payload, "pending"),
            )
            old = db.execute("SELECT payload FROM jobs WHERE id=?", (key,)).fetchone()
            if old["payload"] != payload:
                raise HTTPException(409, "idempotency key payload mismatch")
        return {"job_id": key}

    @app.get("/jobs/{job_id}")
    async def get_job(job_id: str):
        with connect() as db:
            row = db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        if row is None:
            raise HTTPException(404, "job not found")
        return {
            "status": row["status"],
            "output": json.loads(row["output"] or "null"),
            "attempts": row["attempts"],
        }

    @app.delete("/jobs/{job_id}")
    async def cancel(job_id: str):
        signals.setdefault(job_id, threading.Event()).set()
        with connect() as db:
            db.execute(
                "UPDATE jobs SET status='canceled' WHERE id=? AND status='pending'", (job_id,)
            )
        return {"status": "canceled"}

    return app


if __name__ == "__main__":
    import argparse

    import uvicorn

    parser = argparse.ArgumentParser()
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--artifacts", type=Path, required=True)
    parser.add_argument("--port", type=int, default=18880)
    args = parser.parse_args()
    uvicorn.run(
        create_renderer(args.state, args.artifacts, os.environ.get("EVOSPRIG_RENDER_TOKEN")),
        host="127.0.0.1",
        port=args.port,
        access_log=False,
    )
