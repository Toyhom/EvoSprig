import sqlite3

import pytest

from evosprig.config import make_tools
from evosprig.core.journal import Scope
from evosprig.core.protocols import ModelResponse, ToolCall, ToolFeedbackError
from evosprig.core.runtime import Runtime
from evosprig.core.version import compile_agent
from evosprig.data_cli import load_csv
from evosprig.plugins.mock import MockProvider
from evosprig.plugins.sqlite_tools import SQLiteToolConfig, sqlite_tool
from evosprig.sdk import Builder


@pytest.fixture
def database(tmp_path, monkeypatch):
    path = tmp_path / "orders.sqlite"
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE orders (region TEXT, amount REAL)")
        db.executemany(
            "INSERT INTO orders VALUES (?,?)", [("East", 40), ("East", 60), ("West", 30)]
        )
        db.execute("CREATE TABLE private_notes (content TEXT)")
    monkeypatch.setenv("SQL_TEST_DB", str(path))
    return path


def config(operation="query", **extra):
    return SQLiteToolConfig(
        name="db." + operation,
        operation=operation,
        path_env="SQL_TEST_DB",
        tables=["orders"],
        **extra,
    )


async def test_schema_query_and_row_cap(database):
    schema = await sqlite_tool(config("schema")).invoke({})
    assert [r["name"] for r in schema["tables"]] == ["orders"]
    result = await sqlite_tool(config()).invoke(
        {"sql": "SELECT region,SUM(amount) FROM orders GROUP BY region ORDER BY SUM(amount) DESC"}
    )
    assert result["rows"] == [["East", 100.0], ["West", 30.0]]
    result = await sqlite_tool(config(max_rows=2)).invoke({"sql": "SELECT * FROM orders"})
    assert len(result["rows"]) == 2 and result["truncated"]


@pytest.mark.parametrize(
    "query",
    [
        "DELETE FROM orders",
        "ATTACH DATABASE ':memory:' AS other",
        "PRAGMA user_version=7",
        "SELECT * FROM private_notes",
        "SELECT load_extension('extension')",
        "SELECT 1; DELETE FROM orders",
    ],
)
async def test_queries_cannot_write_or_escape_table_allowlist(database, query):
    with pytest.raises(ToolFeedbackError):
        await sqlite_tool(config()).invoke({"sql": query})
    with sqlite3.connect(database) as db:
        assert db.execute("SELECT COUNT(*) FROM orders").fetchone()[0] == 3


async def test_expensive_recursive_query_is_bounded(database):
    with pytest.raises(ToolFeedbackError, match="interrupted"):
        await sqlite_tool(config(max_vm_steps=2000)).invoke(
            {
                "sql": "WITH RECURSIVE n(x) AS (SELECT 1 UNION ALL SELECT x+1 FROM n) SELECT sum(x) FROM n"
            }
        )


async def test_agent_repairs_sql_using_framework_tool_feedback(database, tmp_path):
    schema = {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}
    spec = (
        Builder("sql-repair", {}, schema, spec_version="0.3")
        .model("main", "main", ["text", "tool_calling"])
        .tool("query", "db.query")
        .node(
            "answer",
            "agent",
            model="main",
            tools=["query"],
            tool_errors="feedback",
            instructions="Query the database and correct invalid SQL.",
            output_schema=schema,
        )
        .output(text={"ref": "nodes.answer.output.text"})
        .build_spec()
    )
    model = MockProvider(
        [
            ModelResponse(
                tool_calls=(ToolCall("bad", "query", {"sql": "SELECT missing FROM orders"}),)
            ),
            ModelResponse(
                tool_calls=(
                    ToolCall("good", "query", {"sql": "SELECT SUM(amount) AS revenue FROM orders"}),
                )
            ),
            ModelResponse(text="Revenue is 130."),
        ]
    )
    tools = make_tools(tmp_path, Scope(spec.id), bindings={"db.query": config().model_dump()})
    result = await Runtime({"main": model}, tools).run(compile_agent(spec), {})
    assert result.status == "succeeded"
    assert result.output["text"] == "Revenue is 130."
    assert "no such column" in str(model.requests[1].messages)
    assert "130" in str(model.requests[2].messages)
    assert len([e for e in result.events if e["type"] == "tool.feedback"]) == 1


def test_csv_setup_is_generic_and_atomic(tmp_path):
    source = tmp_path / "orders.csv"
    source.write_text("region,amount\nEast,40\nWest,30\n")
    database = tmp_path / "data.sqlite"
    assert load_csv(source, database, "orders")["rows"] == 2
    with sqlite3.connect(database) as db:
        assert db.execute("SELECT SUM(amount) FROM orders").fetchone()[0] == 70
    malformed = tmp_path / "bad.csv"
    malformed.write_text("a,b\nonly-one\n")
    with pytest.raises(ValueError):
        load_csv(malformed, database, "bad")
    with sqlite3.connect(database) as db:
        assert db.execute("SELECT name FROM sqlite_master WHERE name='bad'").fetchall() == []


@pytest.mark.parametrize("with_profile", [False, True])
def test_exported_map_queries_database_without_platform(tmp_path, database, with_profile):
    import json
    import os
    import subprocess
    import sys

    from evosprig.exporters.python import export_python

    body = {
        "entry": "query",
        "nodes": {
            "query": {
                "type": "tool",
                "tool": "query",
                "inputs": {"sql": {"ref": "input.item"}},
                "output_schema": {"type": "object"},
            }
        },
        "edges": [],
        "output": {"rows": {"ref": "nodes.query.output.rows"}},
    }
    spec = (
        Builder("portable-analysis", {"type": "object"}, {"type": "object"})
        .tool("query", "db.query")
        .map(
            "queries",
            items={"value": ["SELECT SUM(amount) FROM orders", "SELECT COUNT(*) FROM orders"]},
            body=body,
            output_schema={"type": "object"},
        )
        .output(results={"ref": "nodes.queries.output.items"})
        .build_spec()
    )
    target = tmp_path / "exported"
    export_python(compile_agent(spec), target, tool_bindings={"db.query": config().model_dump()})
    result = subprocess.run(
        [
            sys.executable,
            "app.py",
            "--input",
            "{}",
            *(["--profile", "deployment.example.yaml"] if with_profile else []),
        ],
        cwd=target,
        env={**os.environ, "PYTHONPATH": str(target / "src")},
        check=True,
        text=True,
        capture_output=True,
        timeout=30,
    )
    record = json.loads(result.stdout)
    assert record["status"] == "succeeded"
    assert record["output"] == {"results": [{"rows": [[130.0]]}, {"rows": [[3]]}]}
    assert not list((target / "src").rglob("server"))
