"""Run local media models as asynchronous tools: python app.py --help."""

import argparse
import asyncio
import hmac
import json
import os
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from isolated import IsolatedMediaBackend
from store import JobStore

OPERATIONS = {"assets", "image", "video", "compose", "generate-image", "generate-video",
              "stage-reference", "ingest-comfy", "inspect-video", "generate-voice", "warmup"}
CPU_OPERATIONS = {"compose", "stage-reference", "ingest-comfy", "inspect-video"}


def create_app(store, backend, *, token=None, start_worker=True, idle_unload_seconds=0, preload=None):
    stop = threading.Event()
    readiness = {"ready": preload is None, "error": None}
    def work(cpu=False):
        last_work = time.monotonic()
        try:
            if preload and not cpu:
                payload = {"family": preload}
                if preload == "image":
                    payload["probe"] = True
                backend.execute("warmup", payload, "warmup", stop.is_set)
                readiness["ready"] = True
                last_work = time.monotonic()
            while not stop.is_set():
                if store.run_once(backend, CPU_OPERATIONS if cpu else OPERATIONS - CPU_OPERATIONS):
                    last_work = time.monotonic()
                else:
                    if not cpu and idle_unload_seconds > 0 and time.monotonic() - last_work >= idle_unload_seconds and hasattr(backend, "close"):
                        backend.close()
                        last_work = time.monotonic()
                    stop.wait(0.5)
        except Exception as exc:
            readiness.update(ready=False, error=type(exc).__name__)
            raise
        finally:
            if not cpu and hasattr(backend, "close"):
                backend.close()

    @asynccontextmanager
    async def lifespan(app):
        workers = []
        if start_worker:
            store.recover()
            for cpu in (False, True):
                worker = threading.Thread(target=work, args=(cpu,), daemon=True)
                worker.start()
                workers.append(worker)
        yield
        stop.set()
        if hasattr(backend, "shutdown"):
            backend.shutdown()
        for worker in workers:
            await asyncio.to_thread(worker.join)

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
        if not readiness["ready"]:
            from fastapi.responses import JSONResponse
            return JSONResponse({"status": "failed" if readiness["error"] else "loading",
                                 "family": preload, "error": readiness["error"]}, status_code=503)
        return {"status": "ok", "loaded": backend.loaded, "seed": backend.seed,
                "queue": await asyncio.to_thread(store.counts),
                "idle_unload_seconds": idle_unload_seconds,
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
        if operation == "warmup" and (
            payload.get("family") not in ("image", "video", "voice")
            or type(payload.get("probe", False)) is not bool
            or (payload.get("probe") and payload["family"] != "image")
        ):
            raise HTTPException(422, "warmup accepts a model family and an optional image probe")
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

    @app.post("/jobs/{identifier}/retry")
    async def retry(identifier: str):
        try:
            store.retry(identifier)
        except KeyError:
            raise HTTPException(404, "job not found") from None
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from None
        return {"job_id": identifier, "status": "pending"}

    return app


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image-model", required=True, type=Path)
    parser.add_argument("--image-backend", choices=["flux-klein", "qwen-image-2.1"], default="flux-klein")
    parser.add_argument("--comfy-input", type=Path)
    parser.add_argument("--comfy-output", type=Path)
    parser.add_argument("--speech-model", type=Path, help="Local Faster Whisper model for dialogue checks")
    parser.add_argument("--voice-model", type=Path, help="Qwen Omni Instruct checkpoint with speech output")
    parser.add_argument("--idle-unload-seconds", type=float, default=0,
                        help="0 retains models until shutdown; positive values unload idle models")
    parser.add_argument("--preload", choices=["image", "video", "voice"], help="Load this model before the service becomes ready")
    parser.add_argument("--video-model", type=Path)
    parser.add_argument("--outputs", required=True, type=Path)
    parser.add_argument("--database", required=True, type=Path)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=18880)
    parser.add_argument("--public-url", default="http://127.0.0.1:18880")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--image-steps", type=int)
    parser.add_argument("--video-steps", type=int, default=12)
    parser.add_argument("--width", type=int, default=848)
    parser.add_argument("--height", type=int, default=480)
    args = parser.parse_args()
    token = os.environ.get("EVOSPRIG_MEDIA_TOKEN")
    if args.host not in {"127.0.0.1", "::1", "localhost"} and not token:
        parser.error("non-loopback listening requires EVOSPRIG_MEDIA_TOKEN")
    backend = IsolatedMediaBackend(args.outputs, args.image_model, args.video_model, args.public_url,
                           seed=args.seed, image_steps=args.image_steps or (40 if args.image_backend == "qwen-image-2.1" else 4), video_steps=args.video_steps,
                           width=args.width, height=args.height, image_backend=args.image_backend,
                           comfy_input=args.comfy_input, comfy_output=args.comfy_output, speech_model=args.speech_model,
                           voice_model=args.voice_model)
    import uvicorn
    uvicorn.run(create_app(JobStore(args.database), backend, token=token, idle_unload_seconds=args.idle_unload_seconds, preload=args.preload), host=args.host, port=args.port,
                access_log=False)


if __name__ == "__main__":
    main()
