"""Scoped project persistence with transactional revision checks."""

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from evosprig.core.spec import AgentSpec, canonical_json


class RevisionConflict(ValueError):
    pass


class ProjectStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS scoped_projects (user TEXT, tenant TEXT, id TEXT, revision INTEGER NOT NULL, spec TEXT NOT NULL, layout TEXT NOT NULL, PRIMARY KEY(user,tenant,id))"
            )
            if db.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='projects'"
            ).fetchone():
                db.execute(
                    "INSERT OR IGNORE INTO scoped_projects (user,tenant,id,revision,spec,layout) SELECT 'local','local',id,revision,spec,layout FROM projects"
                )
            if "resources" not in {
                row[1] for row in db.execute("PRAGMA table_info(scoped_projects)")
            }:
                db.execute("ALTER TABLE scoped_projects ADD COLUMN resources TEXT")

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

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
            "resources": json.loads(row["resources"]) if row["resources"] is not None else None,
        }

    def create(
        self,
        spec: AgentSpec,
        layout: dict | None = None,
        *,
        identity=("local", "local"),
        resources=None,
    ):
        with self.connect() as db:
            try:
                db.execute(
                    "INSERT INTO scoped_projects (user,tenant,id,revision,spec,layout,resources) VALUES (?, ?, ?, 1, ?, ?, ?)",
                    (
                        *identity,
                        spec.id,
                        spec.canonical(),
                        canonical_json(layout or {}),
                        canonical_json(resources) if resources is not None else None,
                    ),
                )
            except sqlite3.IntegrityError as exc:
                raise RevisionConflict("project already exists") from exc
        return self.get(spec.id, identity=identity)

    def get(self, project_id: str, *, identity=("local", "local")):
        with self.connect() as db:
            return self._document(
                db.execute(
                    "SELECT * FROM scoped_projects WHERE user=? AND tenant=? AND id=?",
                    (*identity, project_id),
                ).fetchone()
            )

    def list(self, *, identity=("local", "local")):
        with self.connect() as db:
            return [
                self._document(row)
                for row in db.execute(
                    "SELECT * FROM scoped_projects WHERE user=? AND tenant=? ORDER BY id", identity
                )
            ]

    def update(
        self,
        project_id: str,
        spec: AgentSpec,
        layout: dict,
        revision: int,
        *,
        identity=("local", "local"),
        resources=None,
    ):
        if spec.id != project_id:
            raise ValueError("project id cannot change")
        with self.connect() as db:
            changed = db.execute(
                "UPDATE scoped_projects SET spec=?, layout=?, resources=COALESCE(?,resources), revision=revision+1 WHERE user=? AND tenant=? AND id=? AND revision=?",
                (
                    spec.canonical(),
                    canonical_json(layout),
                    canonical_json(resources) if resources is not None else None,
                    *identity,
                    project_id,
                    revision,
                ),
            ).rowcount
            if not changed:
                if not db.execute(
                    "SELECT 1 FROM scoped_projects WHERE user=? AND tenant=? AND id=?",
                    (*identity, project_id),
                ).fetchone():
                    raise KeyError("project not found")
                raise RevisionConflict("revision changed; reload and compare before saving")
            row = db.execute(
                "SELECT * FROM scoped_projects WHERE user=? AND tenant=? AND id=?",
                (*identity, project_id),
            ).fetchone()
        return self._document(row)
