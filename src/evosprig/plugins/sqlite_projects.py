"""Single-workspace project persistence with transactional revision checks."""

import json
import sqlite3
from pathlib import Path

from evosprig.core.spec import AgentSpec, canonical_json


class RevisionConflict(Exception):
    pass


class ProjectStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS projects (id TEXT PRIMARY KEY, revision INTEGER NOT NULL, spec TEXT NOT NULL, layout TEXT NOT NULL)"
            )

    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        return db

    @staticmethod
    def _document(row) -> dict:
        if row is None:
            raise KeyError("project not found")
        spec = AgentSpec.model_validate_json(row["spec"])
        return {
            "id": row["id"],
            "revision": row["revision"],
            "spec": spec.model_dump(mode="json"),
            "layout": json.loads(row["layout"]),
            "spec_hash": spec.spec_hash,
        }

    def create(self, spec: AgentSpec, layout: dict | None = None):
        with self.connect() as db:
            try:
                db.execute(
                    "INSERT INTO projects VALUES (?, 1, ?, ?)",
                    (spec.id, spec.canonical(), canonical_json(layout or {})),
                )
            except sqlite3.IntegrityError as exc:
                raise RevisionConflict("project already exists") from exc
        return self.get(spec.id)

    def get(self, project_id: str):
        with self.connect() as db:
            return self._document(
                db.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
            )

    def list(self):
        with self.connect() as db:
            return [self._document(row) for row in db.execute("SELECT * FROM projects ORDER BY id")]

    def update(self, project_id: str, spec: AgentSpec, layout: dict, revision: int):
        if spec.id != project_id:
            raise ValueError("project id cannot change")
        with self.connect() as db:
            changed = db.execute(
                "UPDATE projects SET spec=?, layout=?, revision=revision+1 WHERE id=? AND revision=?",
                (spec.canonical(), canonical_json(layout), project_id, revision),
            ).rowcount
            if not changed:
                raise RevisionConflict("revision changed; reload and compare before saving")
            row = db.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
        return self._document(row)
