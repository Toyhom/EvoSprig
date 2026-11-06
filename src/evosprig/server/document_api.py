"""Shared document management for Studio and independently exported applications."""

import asyncio
import json
import time
import uuid
from dataclasses import asdict
from pathlib import Path

from fastapi import HTTPException, Query, Request
from pydantic import Field

from evosprig.core.journal import Scope
from evosprig.core.memory import MemoryConflict, MemoryScope
from evosprig.core.spec import Contract
from evosprig.plugins.document_library import DocumentConfig, check_size


class TextDocument(Contract):
    title: str = Field(min_length=1, max_length=500)
    text: str = Field(min_length=1)
    source: str = Field(min_length=1, max_length=2048)


class DocumentJobs:
    """Disk-backed intake, bounded workers, and renewable claims for process recovery."""
    def __init__(self, library, directory):
        self.library, self.memory = library, library.memory
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.tasks = []
        self.stopping = False
        with self.memory._transaction() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS document_jobs(
                id TEXT PRIMARY KEY, scope TEXT, body TEXT, status TEXT, lease REAL,
                result TEXT, error TEXT, created REAL)""")
            if "claim_token" not in {row[1] for row in db.execute("PRAGMA table_info(document_jobs)")} :
                db.execute("ALTER TABLE document_jobs ADD COLUMN claim_token TEXT")
            db.execute("CREATE INDEX IF NOT EXISTS document_jobs_queue ON document_jobs(status,created)")

    def reserve(self, scope, filename, source, config):
        if not filename or filename != Path(filename).name or '\\' in filename or len(filename) > 240:
            raise ValueError("provide a filename without directory components (maximum 240 characters)")
        if Path(filename).suffix.lower() not in config.allowed_extensions:
            raise ValueError("this file type is not enabled")
        identifier = uuid.uuid4().hex
        body = {"scope": asdict(scope), "filename": filename, "source": source or "documents/" + filename, "config": config.model_dump(), "submitted_at": time.time()}
        with self.memory._transaction() as db:
            count = db.execute("SELECT COUNT(*) FROM document_jobs WHERE scope=? AND status IN ('uploading','queued','processing')", (scope.key,)).fetchone()[0]
            if count >= config.max_pending_jobs:
                raise HTTPException(429, "document intake queue is full; retry after current imports finish")
            db.execute("INSERT INTO document_jobs(id,scope,body,status,lease,result,error,created) VALUES(?,?,?,'uploading',?,NULL,NULL,?)", (identifier, scope.key, json.dumps(body), time.time() + 600, time.time()))
        return identifier

    def get(self, scope, identifier):
        with self.memory._transaction(False) as db:
            row = db.execute("SELECT id,body,status,result,error,created FROM document_jobs WHERE scope=? AND id=?", (scope.key, identifier)).fetchone()
        if not row:
            raise KeyError("document job not found")
        return {"id": row[0], "filename": json.loads(row[1])["filename"], "status": row[2],
                "result": json.loads(row[3]) if row[3] else None, "error": row[4], "created_at": row[5]}

    def list(self, scope):
        with self.memory._transaction(False) as db:
            ids = [r[0] for r in db.execute("SELECT id FROM document_jobs WHERE scope=? ORDER BY created DESC LIMIT 50", (scope.key,))]
        return [self.get(scope, identifier) for identifier in ids]

    def update(self, identifier, status, *, result=None, error=None, claim_token=None):
        with self.memory._transaction() as db:
            cursor = db.execute("UPDATE document_jobs SET status=?,result=?,error=?,lease=? WHERE id=? AND (? IS NULL OR claim_token=?)",
                       (status, json.dumps(result) if result else None, error, time.time() + 600, identifier, claim_token, claim_token))
            return cursor.rowcount == 1

    async def upload(self, request, scope, filename, source=None):
        config = self.library.config(scope)
        identifier = self.reserve(scope, filename, source, config)
        path = self.directory / identifier
        size = 0
        heartbeat = asyncio.create_task(self.heartbeat(identifier, uploading=True))
        try:
            with path.open("wb") as output:
                async for chunk in request.stream():
                    size += len(chunk)
                    check_size(size, config.max_file_bytes, "file bytes")
                    await asyncio.to_thread(output.write, chunk)
            if not size:
                raise ValueError("file is empty")
            self.update(identifier, "queued")
        except BaseException as exc:
            self.update(identifier, "failed", error="Upload did not complete")
            path.unlink(missing_ok=True)
            if isinstance(exc, ValueError):
                raise HTTPException(413 if "limit" in str(exc) else 422, str(exc)) from None
            raise
        finally:
            heartbeat.cancel()
            await asyncio.gather(heartbeat, return_exceptions=True)
        return self.get(scope, identifier)

    def claim(self):
        with self.memory._transaction() as db:
            row = db.execute("SELECT id,body FROM document_jobs WHERE status='queued' OR (status='processing' AND lease<?) ORDER BY created LIMIT 1", (time.time(),)).fetchone()
            if row:
                token = uuid.uuid4().hex
                db.execute("UPDATE document_jobs SET status='processing',lease=?,claim_token=? WHERE id=?", (time.time() + 600, token, row[0]))
                row = (*row, token)
        # Interrupted uploads never become parseable jobs; clear their temporary files.
        with self.memory._transaction() as db:
            abandoned = [r[0] for r in db.execute("SELECT id FROM document_jobs WHERE status='uploading' AND lease<?", (time.time(),))]
            for identifier in abandoned:
                db.execute("UPDATE document_jobs SET status='failed',error='Upload interrupted' WHERE id=?", (identifier,))
        for identifier in abandoned:
            (self.directory / identifier).unlink(missing_ok=True)
        return row

    async def heartbeat(self, identifier, uploading=False, claim_token=None):
        while True:
            await asyncio.sleep(30)
            with self.memory._transaction() as db:
                db.execute("UPDATE document_jobs SET lease=? WHERE id=? AND status=? AND (? IS NULL OR claim_token=?)", (time.time() + 600, identifier, "uploading" if uploading else "processing", claim_token, claim_token))

    async def loop(self):
        while not self.stopping:
            row = await asyncio.to_thread(self.claim)
            if not row:
                await asyncio.sleep(.2)
                continue
            identifier, content, claim_token = row
            body = json.loads(content)
            raw_scope = body["scope"]
            scope = MemoryScope(identity=Scope(**raw_scope.pop("identity")), **raw_scope)
            heartbeat = asyncio.create_task(self.heartbeat(identifier, claim_token=claim_token))
            try:
                result = await asyncio.to_thread(self.library.ingest_file, scope, self.directory / identifier,
                                                filename=body["filename"], source=body["source"],
                                                config=DocumentConfig.model_validate(body["config"]), operation_id=identifier, submitted_at=body["submitted_at"])
                finished = self.update(identifier, "succeeded", result=result, claim_token=claim_token)
            except (ValueError, MemoryConflict) as exc:
                finished = self.update(identifier, "failed", error=str(exc)[:500], claim_token=claim_token)
            except Exception:
                finished = self.update(identifier, "failed", error="Document parsing failed; check the file format and parser installation", claim_token=claim_token)
            finally:
                heartbeat.cancel()
                await asyncio.gather(heartbeat, return_exceptions=True)
            if finished:
                (self.directory / identifier).unlink(missing_ok=True)

    async def start(self):
        self.stopping = False
        self.tasks = [asyncio.create_task(self.loop()) for _ in range(self.library.defaults.ingestion_workers)]

    async def stop(self):
        # Let active parser threads finish before closing the service.
        self.stopping = True
        await asyncio.gather(*self.tasks, return_exceptions=True)
        self.tasks = []


def install_document_routes(app, library, jobs, scope_for, *, prefix, editable=True):
    def selected(project_id):
        scope = scope_for(project_id)
        if not editable and not library.config(scope).customer_uploads:
            raise HTTPException(403, "customer document management is disabled in this deployment")
        return scope

    @app.get(prefix + "/settings")
    async def settings(project_id: str = ""):
        return library.config(selected(project_id)).model_dump()

    if editable:
        @app.put(prefix + "/settings")
        async def configure(body: DocumentConfig, project_id: str = ""):
            return library.configure(selected(project_id), body.model_dump()).model_dump()

    @app.get(prefix)
    async def documents(project_id: str = "", offset: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=1000)):
        return await asyncio.to_thread(library.list, selected(project_id), offset=offset, limit=limit)

    @app.post(prefix, status_code=201)
    async def ingest(body: TextDocument, project_id: str = ""):
        try:
            return await asyncio.to_thread(library.ingest_text, selected(project_id), **body.model_dump())
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None

    @app.post(prefix + "/upload", status_code=202)
    async def upload(request: Request, filename: str, project_id: str = "", source: str | None = Query(None, max_length=2048)):
        try:
            return await jobs.upload(request, selected(project_id), filename, source)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None

    @app.get(prefix + "/jobs")
    async def list_jobs(project_id: str = ""):
        return jobs.list(selected(project_id))

    @app.get(prefix + "/jobs/{job_id}")
    async def get_job(job_id: str, project_id: str = ""):
        return jobs.get(selected(project_id), job_id)

    @app.get(prefix + "/search")
    async def search(query: str, project_id: str = "", limit: int = Query(5, ge=1, le=100)):
        scope = selected(project_id)
        return await asyncio.to_thread(library.retriever(scope).search, scope, query, limit=limit)

    @app.delete(prefix + "/{document_id}")
    async def delete(document_id: str, project_id: str = ""):
        return await asyncio.to_thread(library.delete, selected(project_id), document_id)
