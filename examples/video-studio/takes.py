"""Production take history and editable timeline."""

import json
import sqlite3
from pathlib import Path

from evosprig.core.spec import digest


class TakeStore:
    """Immutable shot takes plus compare-and-swap selection for an edit timeline."""

    def __init__(self, path):
        self.path = Path(path)
        with sqlite3.connect(self.path) as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS takes (id TEXT PRIMARY KEY, shot TEXT, body TEXT)"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS timeline (singleton INTEGER PRIMARY KEY, revision INTEGER, body TEXT)"
            )
            db.execute("INSERT OR IGNORE INTO timeline VALUES (1,0,'{}')")

    def add(self, shot, run_id, clip):
        body = {"shot": shot, "run_id": run_id, "clip": clip}
        identifier = digest(body)
        with sqlite3.connect(self.path) as db:
            db.execute(
                "INSERT OR IGNORE INTO takes VALUES (?,?,?)", (identifier, shot, json.dumps(body))
            )
        return identifier

    def select(self, take_id, *, revision):
        with sqlite3.connect(self.path) as db:
            db.execute("BEGIN IMMEDIATE")
            take = db.execute("SELECT shot,body FROM takes WHERE id=?", (take_id,)).fetchone()
            current = db.execute("SELECT revision,body FROM timeline WHERE singleton=1").fetchone()
            if not take:
                raise KeyError("unknown take")
            if current[0] != revision:
                raise ValueError("timeline revision changed")
            body = json.loads(current[1])
            body[take[0]] = {"take_id": take_id, **json.loads(take[1])}
            db.execute(
                "UPDATE timeline SET revision=?,body=? WHERE singleton=1",
                (revision + 1, json.dumps(body)),
            )
        return {"revision": revision + 1, "shots": body}

    def current(self):
        with sqlite3.connect(self.path) as db:
            revision, body = db.execute(
                "SELECT revision,body FROM timeline WHERE singleton=1"
            ).fetchone()
        return {"revision": revision, "shots": json.loads(body)}
