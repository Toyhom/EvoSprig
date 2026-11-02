"""Deterministic media contract simulator. Produces fixture URIs, never a video."""

import json
import sqlite3
from pathlib import Path

import httpx
from build_agent import profile

from evosprig.core.protocols import ToolRegistry
from evosprig.plugins.external_http import ExternalHTTPConfig, external_http_tool

PLAN = {
    "title": "The Last Library",
    "style": "warm cinematic illustration",
    "characters": [
        {"id": "librarian", "description": "Young librarian in a mustard coat with round glasses."}
    ],
    "shots": [
        {
            "id": "arrival",
            "description": "The librarian enters an empty library at dawn.",
            "camera": "wide dolly in",
            "dialogue": "",
            "characters": ["librarian"],
            "duration_seconds": 5,
        },
        {
            "id": "discovery",
            "description": "A glowing book opens in the librarian's hands.",
            "camera": "close-up",
            "dialogue": "Every story needs a reader.",
            "characters": ["librarian"],
            "duration_seconds": 5,
        },
        {
            "id": "departure",
            "description": "Words rise from the book and fill the library with light.",
            "camera": "slow crane up",
            "dialogue": "",
            "characters": ["librarian"],
            "duration_seconds": 5,
        },
    ],
}


class MediaSimulator:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, kind TEXT, payload TEXT, output TEXT, polls INTEGER DEFAULT 0)"
            )

    def connect(self):
        db = sqlite3.connect(self.path)
        db.row_factory = sqlite3.Row
        return db

    def handle(self, request):
        kind = request.url.path.strip("/").split("/")[0]
        if request.method == "POST":
            payload = json.loads(request.content)
            identifier = request.headers["idempotency-key"]
            media_type = "video/mp4" if kind in {"video", "compose"} else "image/png"
            asset = {
                "id": identifier,
                "uri": f"fixture://{kind}/{identifier}",
                "media_type": media_type,
            }
            output = (
                {
                    "assets": [
                        {
                            "character_id": character["id"],
                            "asset": {**asset, "id": identifier + "-" + character["id"]},
                        }
                        for character in payload["characters"]
                    ]
                }
                if kind == "assets"
                else asset
            )
            with self.connect() as db:
                old = db.execute("SELECT * FROM jobs WHERE id=?", (identifier,)).fetchone()
                if old and json.loads(old["payload"]) != payload:
                    return httpx.Response(409, json={"error": "idempotency mismatch"})
                db.execute(
                    "INSERT OR IGNORE INTO jobs (id,kind,payload,output) VALUES (?,?,?,?)",
                    (identifier, kind, json.dumps(payload), json.dumps(output)),
                )
            return httpx.Response(202, json={"job_id": identifier})
        identifier = request.url.path.rsplit("/", 1)[-1]
        with self.connect() as db:
            row = db.execute(
                "SELECT * FROM jobs WHERE id=? AND kind=?", (identifier, kind)
            ).fetchone()
            if not row:
                return httpx.Response(404)
            if request.method == "DELETE":
                db.execute("UPDATE jobs SET polls=-100 WHERE id=?", (identifier,))
                return httpx.Response(200, json={"canceled": True})
            db.execute("UPDATE jobs SET polls=polls+1 WHERE id=?", (identifier,))
        status = "canceled" if row["polls"] < 0 else "pending" if row["polls"] == 0 else "succeeded"
        return httpx.Response(
            200,
            json={
                "status": status,
                "output": json.loads(row["output"]) if status == "succeeded" else None,
            },
        )

    def registry(self):
        registry = ToolRegistry()
        for name, raw in profile()["tools"].items():
            raw = {**raw, "auth_env": None}
            registry.register(
                external_http_tool(
                    ExternalHTTPConfig.model_validate(raw),
                    transport=httpx.MockTransport(self.handle),
                )
            )
        return registry

    def jobs(self):
        with self.connect() as db:
            return [dict(row) for row in db.execute("SELECT * FROM jobs ORDER BY rowid")]
