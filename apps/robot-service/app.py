"""Franka simulation tools with atomic snapshots and intent-bound action receipts."""

import argparse
import hashlib
import json
import sqlite3
import subprocess
import tempfile
from contextlib import closing
from pathlib import Path
from typing import Literal

import imageio_ffmpeg
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field
from world import World


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Start(Contract):
    scene: Literal["tabletop"] = "tabletop"


class Episode(Contract):
    episode: str = Field(pattern=r"^[a-f0-9]{32}$")


class Action(Contract):
    kind: Literal["move", "finish"]
    object: Literal["red", "blue", "yellow"]
    position: list[float] = Field(min_length=3, max_length=3)


class Act(Episode):
    action: Action


class Goal(Contract):
    object: Literal["red", "blue", "yellow"]
    kind: Literal["in_tray", "on", "unchanged"]
    target: Literal["red", "blue", "yellow"] = "blue"


class Check(Episode):
    goals: list[Goal] = Field(min_length=1, max_length=12)


class Store:
    def __init__(self, root, base_url):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.base_url = base_url.rstrip("/")
        self.path = self.root / "worlds.sqlite"
        with closing(self.connect()) as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS episodes(id TEXT PRIMARY KEY, state TEXT, initial TEXT);
                CREATE TABLE IF NOT EXISTS operations(id TEXT PRIMARY KEY, intent TEXT, result TEXT);
            """)

    def connect(self):
        return sqlite3.connect(self.path, timeout=60)

    def transact(self, kind, payload, key):
        if not key or len(key) > 256:
            raise ValueError("a bounded Idempotency-Key is required")
        op = hashlib.sha256(key.encode()).hexdigest()
        intent = json.dumps([kind, payload], sort_keys=True, allow_nan=False)
        with closing(self.connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            old = db.execute("SELECT intent,result FROM operations WHERE id=?", (op,)).fetchone()
            if old:
                if old[0] != intent:
                    raise ValueError("operation key already belongs to another intent")
                return json.loads(old[1])
            episode = op[:32] if kind == "start" else payload["episode"]
            row = db.execute("SELECT state,initial FROM episodes WHERE id=?", (episode,)).fetchone()
            if kind != "start" and not row:
                raise KeyError("episode not found")
            world = World(json.loads(row[0]) if row else None)
            try:
                result = world.act(payload["action"]) if kind == "act" else {"success": True}
                snapshot = world.snapshot()
                initial = row[1] if row else json.dumps(snapshot)
                db.execute(
                    "INSERT OR REPLACE INTO episodes VALUES(?,?,?)",
                    (episode, json.dumps(snapshot), initial),
                )
                name = op + ".png"
                world.image().save(self.root / name)
                result.update(episode=episode, image=self.base_url + "/files/" + name)
                if world.frames:
                    movie = op + ".mp4"
                    self.movie(world.frames, self.root / movie)
                    result["video"] = self.base_url + "/files/" + movie
                db.execute("INSERT INTO operations VALUES(?,?,?)", (op, intent, json.dumps(result)))
                return result
            finally:
                world.close()

    def state(self, episode):
        with closing(self.connect()) as db:
            row = db.execute("SELECT state,initial FROM episodes WHERE id=?", (episode,)).fetchone()
        if not row:
            raise KeyError("episode not found")
        return [json.loads(value) for value in row]

    def observe(self, episode):
        state, _ = self.state(episode)
        world = World(state)
        try:
            return world.observation()
        finally:
            world.close()

    def check(self, episode, goals):
        import math

        state, initial = self.state(episode)
        positions = {name: obj["position"] for name, obj in state["objects"].items()}
        checks = []
        for goal in goals:
            xyz = positions[goal.object]
            if goal.kind == "in_tray":
                passed = 0.475 <= xyz[0] <= 0.705 and 0.185 <= xyz[1] <= 0.315 and xyz[2] < 0.065
            elif goal.kind == "unchanged":
                passed = math.dist(xyz, initial["objects"][goal.object]["position"]) < 0.015
            else:
                base = positions[goal.target]
                passed = math.dist(xyz[:2], base[:2]) < 0.025 and 0.04 < xyz[2] - base[2] < 0.06
            checks.append({**goal.model_dump(), "passed": passed})
        return {
            "success": all(x["passed"] for x in checks),
            "checks": checks,
            "positions": positions,
        }

    def movie(self, frames, out):
        with tempfile.TemporaryDirectory(dir=self.root) as directory:
            directory = Path(directory)
            for i, frame in enumerate(frames):
                frame.save(directory / f"{i:04d}.png")
            subprocess.run(
                [
                    imageio_ffmpeg.get_ffmpeg_exe(),
                    "-y",
                    "-v",
                    "error",
                    "-framerate",
                    "20",
                    "-i",
                    str(directory / "%04d.png"),
                    "-c:v",
                    "libx264",
                    "-pix_fmt",
                    "yuv420p",
                    "-movflags",
                    "+faststart",
                    str(out),
                ],
                check=True,
                timeout=60,
            )


def create_app(store):
    app = FastAPI(title="EvoSprig robot simulation tools")

    @app.middleware("http")
    async def local_tools(request, call_next):
        if request.headers.get("origin"):
            from fastapi.responses import JSONResponse

            return JSONResponse({"detail": "use the application API"}, status_code=403)
        return await call_next(request)

    def invoke(fn, *args):
        try:
            return fn(*args)
        except KeyError:
            raise HTTPException(404, "episode not found") from None
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from None

    @app.post("/start")
    def start(body: Start, idempotency_key: str = Header()):
        return invoke(store.transact, "start", body.model_dump(), idempotency_key)

    @app.post("/observe")
    def observe(body: Episode):
        return invoke(store.observe, body.episode)

    @app.post("/act")
    def act(body: Act, idempotency_key: str = Header()):
        return invoke(store.transact, "act", body.model_dump(), idempotency_key)

    @app.post("/check")
    def check(body: Check):
        return invoke(store.check, body.episode, body.goals)

    @app.get("/files/{name}")
    def asset(name: str):
        import re

        if not re.fullmatch(r"[a-f0-9]{64}\.(png|mp4)", name) or not (store.root / name).is_file():
            raise HTTPException(404, "asset not found")
        return FileResponse(store.root / name)

    @app.get("/health")
    def health():
        return {"status": "ok", "backend": "pybullet", "robot": "Franka Panda"}

    return app


if __name__ == "__main__":
    import uvicorn

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=Path(".evosprig/robot"))
    parser.add_argument("--port", type=int, default=18890)
    args = parser.parse_args()
    uvicorn.run(
        create_app(Store(args.workspace, f"http://127.0.0.1:{args.port}")),
        host="127.0.0.1",
        port=args.port,
    )
