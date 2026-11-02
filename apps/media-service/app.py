"""Run local media models as asynchronous tools: python app.py --help."""

import argparse
import asyncio
import hmac
import json
import os
import threading
from contextlib import asynccontextmanager
from pathlib import Path

from backend import MediaBackend
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from store import JobStore

OPERATIONS = {"assets", "image", "video", "compose", "generate-image", "generate-video"}


def create_app(store, backend, *, token=None, start_worker=True):
    stop = threading.Event()
    def work():
        while not stop.is_set():
            if not store.run_once(backend):
                stop.wait(0.5)

    @asynccontextmanager
    async def lifespan(app):
        if start_worker:
            store.recover()
            threading.Thread(target=work, daemon=True).start()
        yield
        stop.set()

    app = FastAPI(title="EvoSprig local media", lifespan=lifespan)

    @app.middleware("http")
    async def authenticate(request, call_next):
        from fastapi.responses import JSONResponse
        if token and not hmac.compare_digest(request.headers.get("authorization", ""), "Bearer " + token):
            return JSONResponse({"detail": "authentication required"}, status_code=401)
        if request.headers.get("origin"):
            return JSONResponse({"detail": "browser origins are not accepted by the tool service"}, status_code=403)
        return await call_next(request)

    async def body(request):
        raw = bytearray()
        async for chunk in request.stream():
            raw.extend(chunk)
            if len(raw) > 20 * 1024 * 1024:
                raise HTTPException(413, "request exceeds 20 MiB")
        try:
            value = json.loads(raw)
            if not isinstance(value, dict):
                raise ValueError()
            return value
        except ValueError:
            raise HTTPException(422, "request must be a JSON object") from None

    @app.get("/health")
    async def health():
        return {"status": "ok", "loaded": backend.loaded, "seed": backend.seed,
                "image_steps": backend.image_steps, "video_steps": backend.video_steps,
                "width": backend.width, "height": backend.height}

    @app.get("/files/{name}")
    async def file(name):
        try:
            path = backend.resolve(backend.base_url + "/files/" + name)
        except ValueError:
            raise HTTPException(404, "asset not found") from None
        return FileResponse(path)

    @app.post("/upload")
    async def upload(request: Request):
        try:
            payload = await body(request)
            return await asyncio.to_thread(backend.upload, payload["image"])
        except (KeyError, ValueError, OSError):
            raise HTTPException(422, "invalid image upload") from None

    @app.post("/vision")
    async def vision(request: Request):
        try:
            payload = await body(request)
            assets = payload["assets"] if "assets" in payload else [payload["asset"]]
            return await asyncio.to_thread(backend.vision, assets, payload.get("max_side", 768))
        except (KeyError, ValueError, OSError):
            raise HTTPException(422, "invalid vision input") from None

    @app.post("/{operation}")
    async def submit(operation: str, request: Request):
        if operation not in OPERATIONS:
            raise HTTPException(404, "unknown tool")
        key = request.headers.get("idempotency-key", "")
        if not key or len(key) > 200:
            raise HTTPException(422, "Idempotency-Key is required (max 200 characters)")
        payload = await body(request)
        try:
            identifier = store.submit(operation, key, payload)
        except ValueError:
            raise HTTPException(409, "idempotency key belongs to a different request") from None
        return {"job_id": identifier}

    @app.get("/{operation}/{identifier}")
    async def status(operation: str, identifier: str):
        try:
            row = store.get(identifier, operation)
        except KeyError:
            raise HTTPException(404, "job not found") from None
        result = {"status": "pending" if row["status"] == "running" else row["status"]}
        if row["status"] == "succeeded":
            result["output"] = json.loads(row["output"])
        if row["error"]:
            result["error"] = row["error"]
        return result

    @app.delete("/{operation}/{identifier}")
    async def cancel(operation: str, identifier: str):
        try:
            store.get(identifier, operation)
            store.cancel(identifier)
        except KeyError:
            raise HTTPException(404, "job not found") from None
        return {"status": store.get(identifier)["status"]}

    return app


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image-model", required=True, type=Path)
    parser.add_argument("--video-model", required=True, type=Path)
    parser.add_argument("--outputs", required=True, type=Path)
    parser.add_argument("--database", required=True, type=Path)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=18880)
    parser.add_argument("--public-url", default="http://127.0.0.1:18880")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--image-steps", type=int, default=4)
    parser.add_argument("--video-steps", type=int, default=12)
    parser.add_argument("--width", type=int, default=848)
    parser.add_argument("--height", type=int, default=480)
    args = parser.parse_args()
    token = os.environ.get("EVOSPRIG_MEDIA_TOKEN")
    if args.host not in {"127.0.0.1", "::1", "localhost"} and not token:
        parser.error("non-loopback listening requires EVOSPRIG_MEDIA_TOKEN")
    backend = MediaBackend(args.outputs, args.image_model, args.video_model, args.public_url,
                           seed=args.seed, image_steps=args.image_steps, video_steps=args.video_steps,
                           width=args.width, height=args.height)
    import uvicorn
    uvicorn.run(create_app(JobStore(args.database), backend, token=token), host=args.host, port=args.port,
                access_log=False)


if __name__ == "__main__":
    main()
