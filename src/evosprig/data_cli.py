"""Shared data setup commands for every CLI/Studio application."""

import csv
import json
import re
import sqlite3
from pathlib import Path

from evosprig.core.journal import Scope
from evosprig.core.memory import MemoryScope
from evosprig.plugins.documents import DocumentRetriever
from evosprig.plugins.sqlite_memory import SQLiteMemory


def add_commands(commands):
    parser = commands.add_parser("data", help="Prepare data for an agent")
    kinds = parser.add_subparsers(dest="data_command", required=True)
    csv_parser = kinds.add_parser("load-csv", help="Import a CSV file into a new SQLite table")
    csv_parser.add_argument("file", type=Path)
    csv_parser.add_argument("--database", type=Path, required=True)
    csv_parser.add_argument("--table", required=True)
    docs = kinds.add_parser("add-documents", help="Add text documents to project memory")
    docs.add_argument("path", type=Path)
    docs.add_argument("--project", required=True)
    docs.add_argument("--workspace", type=Path, default=Path(".evosprig"))


def load_csv(path, database, table):
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,63}", table):
        raise ValueError("table name must be a simple SQL identifier")
    path, database = Path(path), Path(database)
    if path.stat().st_size > 20000000:
        raise ValueError("CSV exceeds 20 MB")
    with path.open(newline="", encoding="utf-8-sig") as source:
        reader = csv.reader(source)
        columns = next(reader, [])
        if (
            not 1 <= len(columns) <= 128
            or len(set(columns)) != len(columns)
            or any(not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,63}", column) for column in columns)
        ):
            raise ValueError("CSV needs unique, simple column identifiers")
        database.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(database)
        try:
            db.execute("BEGIN IMMEDIATE")
            # NUMERIC affinity preserves text and converts unambiguous numeric cells.
            db.execute(
                f'CREATE TABLE "{table}" ('
                + ",".join(f'"{name}" NUMERIC' for name in columns)
                + ")"
            )
            count = 0
            for row in reader:
                if len(row) != len(columns) or count >= 100000:
                    raise ValueError("CSV row shape or row limit is invalid")
                db.execute(
                    f'INSERT INTO "{table}" VALUES (' + ",".join("?" for _ in columns) + ")", row
                )
                count += 1
            db.commit()
            return {"table": table, "rows": count, "columns": columns}
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()


def add_documents(path, workspace, project):
    path = Path(path)
    if not path.exists():
        raise ValueError("document path does not exist")
    files = (
        [path]
        if path.is_file()
        else sorted(
            file
            for file in path.rglob("*")
            if file.is_file()
            and not file.is_symlink()
            and file.suffix.lower() in {".txt", ".md"}
            and not any(part.startswith(".") for part in file.relative_to(path).parts)
        )
    )
    if not 1 <= len(files) <= 128:
        raise ValueError("choose 1..128 text documents")
    documents = []
    for file in files:
        if file.stat().st_size > 1000000:
            raise ValueError("document exceeds 1 MB")
        text = file.read_text(encoding="utf-8")
        if not text.strip():
            raise ValueError("document is empty")
        documents.append((file, text))
    retriever = DocumentRetriever(SQLiteMemory(Path(workspace) / "memory.sqlite"))
    scope = MemoryScope(Scope(project), namespace="documents")
    return {
        "documents": [
            retriever.ingest(
                scope,
                title=file.stem,
                text=text,
                source="documents/"
                + (file.relative_to(path).as_posix() if path.is_dir() else file.name),
            )
            for file, text in documents
        ]
    }


def run_command(args):
    if args.data_command == "load-csv":
        try:
            result = load_csv(args.file, args.database, args.table)
        except sqlite3.Error:
            raise ValueError(
                "CSV import failed; choose a new table in a writable database"
            ) from None
    else:
        result = add_documents(args.path, args.workspace, args.project)
    print(json.dumps(result, indent=2))
