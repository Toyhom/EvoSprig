"""Read-only SQLite tools with deployment-bound databases and bounded queries."""

from __future__ import annotations

import json
import math
import os
import sqlite3
from pathlib import Path
from typing import Literal

from pydantic import Field

from evosprig.core.protocols import ExecutionError, Tool, ToolFeedbackError
from evosprig.core.spec import Contract


class SQLiteToolConfig(Contract):
    kind: Literal["sqlite"] = "sqlite"
    name: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_.-]{0,127}$")
    version: Literal["1"] = "1"
    operation: Literal["schema", "query"]
    path_env: str = Field(pattern=r"^[A-Za-z_][A-Za-z0-9_]*$")
    tables: list[str] = Field(default_factory=list, max_length=128)
    max_rows: int = Field(default=200, ge=1, le=2000)
    max_vm_steps: int = Field(default=1000000, ge=1000, le=10000000)
    timeout_seconds: float = Field(default=10, gt=0, le=60)


def sqlite_tool(config: SQLiteToolConfig):
    def connect():
        value = os.environ.get(config.path_env)
        if not value or not Path(value).is_file():
            raise ExecutionError(
                "SQLite database is unavailable; configure its path environment variable"
            )
        db = sqlite3.connect(
            Path(value).resolve().as_uri() + "?mode=ro", uri=True, timeout=config.timeout_seconds
        )
        db.enable_load_extension(False)
        db.execute("PRAGMA query_only=ON")
        db.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, 1000000)
        db.setlimit(sqlite3.SQLITE_LIMIT_SQL_LENGTH, 12000)
        db.setlimit(sqlite3.SQLITE_LIMIT_COLUMN, 128)
        return db

    def schema():
        db = connect()
        try:
            names = [
                row[0]
                for row in db.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
                )
            ]
            if config.tables:
                names = [name for name in names if name in config.tables]
            if len(names) > 128:
                raise ToolFeedbackError(
                    "schema_limit", "Configure a table allowlist for this database"
                )
            return {
                "tables": [
                    {
                        "name": name,
                        "columns": [
                            {
                                "name": row[1],
                                "type": row[2],
                                "nullable": not bool(row[3]),
                                "primary_key": bool(row[5]),
                            }
                            for row in db.execute(
                                'PRAGMA table_info("' + name.replace('"', '""') + '")'
                            )
                        ],
                    }
                    for name in names
                ]
            }
        finally:
            db.close()

    def query(sql, parameters=None):
        db = connect()
        steps = 0

        def progress():
            nonlocal steps
            steps += 1000
            return int(steps >= config.max_vm_steps)

        def authorize(action, first, second, database, trigger):
            if action == sqlite3.SQLITE_READ:
                return (
                    sqlite3.SQLITE_OK
                    if not config.tables or first in config.tables
                    else sqlite3.SQLITE_DENY
                )
            if action == sqlite3.SQLITE_FUNCTION:
                return (
                    sqlite3.SQLITE_DENY
                    if (second or "").lower() in {"load_extension", "readfile", "writefile"}
                    else sqlite3.SQLITE_OK
                )
            return (
                sqlite3.SQLITE_OK
                if action in {sqlite3.SQLITE_SELECT, sqlite3.SQLITE_RECURSIVE}
                else sqlite3.SQLITE_DENY
            )

        db.set_authorizer(authorize)
        db.set_progress_handler(progress, 1000)
        try:
            cursor = db.execute(sql, parameters or [])
            if cursor.description is None:
                raise ToolFeedbackError("read_only", "Use a SELECT query")
            rows, size, truncated = [], 0, False
            for row in cursor:
                if len(rows) >= config.max_rows:
                    truncated = True
                    break
                values = [
                    "0x" + value.hex() if isinstance(value, bytes) else value for value in row
                ]
                if any(isinstance(value, float) and not math.isfinite(value) for value in values):
                    raise ToolFeedbackError("invalid_result", "Query produced a non-finite number")
                size += len(json.dumps(values, ensure_ascii=False).encode())
                if size > 2000000:
                    raise ToolFeedbackError(
                        "result_limit", "Result exceeds 2 MB; aggregate or select fewer columns"
                    )
                rows.append(values)
            return {
                "columns": [item[0] for item in cursor.description],
                "rows": rows,
                "truncated": truncated,
            }
        except sqlite3.Error as exc:
            # SQLite messages describe query/schema problems; never include the database path.
            message = str(exc)[:500]
            if "unable to open" in message or "disk" in message:
                raise ExecutionError("SQLite storage is unavailable") from None
            raise ToolFeedbackError("sql_error", message) from None
        finally:
            db.close()

    input_schema = {"type": "object", "properties": {}, "additionalProperties": False}
    if config.operation == "query":
        input_schema.update(
            properties={
                "sql": {"type": "string", "minLength": 1, "maxLength": 12000},
                "parameters": {
                    "type": "array",
                    "maxItems": 100,
                    "items": {"type": ["string", "number", "boolean", "null"]},
                },
            },
            required=["sql"],
        )
    return Tool(
        config.name,
        "Inspect available database tables and columns."
        if config.operation == "schema"
        else "Execute one read-only SQL query. Use the schema tool first; correct query errors using their feedback.",
        input_schema,
        {"type": "object"},
        schema if config.operation == "schema" else query,
        timeout_seconds=config.timeout_seconds,
    )
