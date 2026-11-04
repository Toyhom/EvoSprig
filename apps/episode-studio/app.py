"""A story-to-film interface backed by the regular EvoSprig server and runtime."""

import argparse
import asyncio
import json
import os
import re
from pathlib import Path

from fastapi import HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from evosprig.config import read_profile
from evosprig.core.spec import load_spec
from evosprig.core.version import compile_agent
from evosprig.plugins.sqlite_projects import ProjectStore
from evosprig.server.app import create_app

ROOT = Path(__file__).resolve().parents[2]


def application(workspace, profile, *, media_root=None, token=None):
    example = ROOT / "examples/episode-studio"
    version = compile_agent(load_spec(example / "agent.yaml"), example)
    store = ProjectStore(Path(workspace) / "projects.sqlite")
    try:
        store.get(version.spec.id)
    except KeyError:
        layout = json.loads((example / "studio.json").read_text())
        store.create(version.spec, layout.get("layout", {}), resources=version.resources,
                     canvas=layout.get("canvas", {}))
    studio = ROOT / "apps/studio/dist"
    app = create_app(workspace, profile=profile, studio_dir=studio if studio.is_dir() else None, token=token)

    @app.get("/api/episode/services")
    async def service_status():
        import httpx

        bindings = read_profile(profile)
        model = bindings.get("models", {}).get("main", {})
        vision_model = bindings.get("models", {}).get("vision", model)
        tools = bindings.get("tools", {})
        image = tools.get("media.generate_image", {})
        render = tools.get("film.render", {})
        addresses = {"director": model.get("base_url", "").rstrip("/") + "/models",
                     "media": image.get("endpoint", "").rsplit("/", 1)[0] + "/health",
                     "render": render.get("base_url", "").rstrip("/") + "/system_stats"}
        if vision_model != model:
            addresses["vision"] = vision_model.get("base_url", "").rstrip("/") + "/models"
        async with httpx.AsyncClient(timeout=2, trust_env=False) as client:
            async def check(name, address):
                try:
                    headers = {}
                    if name in {"director", "vision"}:
                        connection = model if name == "director" else vision_model
                        key = os.environ.get(connection.get("api_key_env", ""))
                        if key:
                            headers["Authorization"] = "Bearer " + key
                    response = await client.get(address, headers=headers)
                    return {"name": name, "ready": response.is_success}
                except (httpx.HTTPError, httpx.InvalidURL):
                    return {"name": name, "ready": False}
            statuses = await asyncio.gather(*(check(name, address) for name, address in addresses.items()))
        return {"ready": all(item["ready"] for item in statuses), "services": statuses}

    @app.get("/episode-media/{name}")
    async def media(name: str):
        if not media_root or not re.fullmatch(r"[a-f0-9]{32,64}(?:_[0-9]+)?\.(mp4|wav|png|jpg)", name):
            raise HTTPException(404, "media not found")
        root = Path(media_root).resolve()
        path = (root / name).resolve()
        if path.parent != root or not path.is_file():
            raise HTTPException(404, "media not found")
        return FileResponse(path)

    if token:
        import hmac

        from fastapi import Request
        from fastapi.responses import JSONResponse

        @app.middleware("http")
        async def media_auth(request: Request, call_next):
            if request.url.path.startswith("/episode-media/") and not hmac.compare_digest(request.headers.get("authorization", ""), "Bearer " + token):
                return JSONResponse({"detail": "authentication required"}, status_code=401)
            return await call_next(request)

    # The generic server's Studio fallback is mounted last.
    from starlette.routing import Mount
    fallback = next((r for r in app.router.routes if isinstance(r, Mount) and r.path == ""), None)
    if fallback:
        app.router.routes.remove(fallback)
    app.mount("/fonts", StaticFiles(directory=ROOT / "apps/studio/public/fonts"), name="episode-fonts")
    app.mount("/episode-gallery", StaticFiles(directory=example / "assets"), name="episode-gallery")
    app.mount("/episode", StaticFiles(directory=Path(__file__).parent / "web", html=True), name="episode")
    if fallback:
        app.router.routes.append(fallback)
    return app


if __name__ == "__main__":
    import os

    import uvicorn

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--workspace", type=Path, default=Path(".evosprig/episode-studio"))
    parser.add_argument("--media-root", type=Path)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=18767)
    args = parser.parse_args()
    token = os.environ.get("EVOSPRIG_TOKEN")
    if args.host not in {"127.0.0.1", "localhost", "::1"} and not token:
        parser.error("set EVOSPRIG_TOKEN when listening outside loopback")
    uvicorn.run(application(args.workspace, args.profile, media_root=args.media_root, token=token),
                host=args.host, port=args.port)
