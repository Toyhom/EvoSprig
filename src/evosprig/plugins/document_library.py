"""Deployment-configurable document intake and a persistent project knowledge library."""

from __future__ import annotations

import json
import subprocess
import tempfile
import threading
import time
import uuid
import zipfile
from contextlib import closing
from pathlib import Path
from typing import Literal
from xml.etree import ElementTree

from pydantic import Field, model_validator

from evosprig.core.spec import Contract
from evosprig.plugins.documents import DocumentRetriever

_PDF_LOCK = threading.RLock()


class DocumentConfig(Contract):
    # None removes a deployment quota; no upload path relies on Content-Length alone.
    max_file_bytes: int | None = Field(default=50 * 1024 * 1024, gt=0)
    max_batch_files: int | None = Field(default=1000, gt=0)
    max_extracted_chars: int | None = Field(default=20_000_000, gt=0)
    max_ocr_pixels: int | None = Field(default=20_000_000, gt=0)
    max_pages: int | None = Field(default=2000, gt=0)
    chunk_size: int = Field(default=1200, ge=200, le=100000)
    chunk_overlap: int = Field(default=150, ge=0)
    allowed_extensions: list[str] = Field(default_factory=lambda: [".txt", ".md", ".pdf", ".docx", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".webp"])
    ocr: Literal["auto", "always", "disabled"] = "auto"
    ocr_languages: str = Field(default="eng", pattern=r"^[A-Za-z0-9_+\-]+$")
    ocr_timeout_seconds: int = Field(default=180, gt=0)
    ocr_dpi: int = Field(default=180, ge=72, le=600)
    max_pending_jobs: int = Field(default=128, ge=1)
    ingestion_workers: int = Field(default=2, ge=1, le=32)
    customer_uploads: bool = False
    retrieval: Literal["lexical", "hybrid"] = "lexical"
    embeddings: dict | None = None
    embedding_cache_entries: int = Field(default=100000, ge=1)

    @model_validator(mode="after")
    def valid(self):
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("chunk_overlap must be smaller than chunk_size")
        known = {".txt", ".md", ".pdf", ".docx", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".webp"}
        if not self.allowed_extensions or set(self.allowed_extensions) - known:
            raise ValueError("allowed_extensions contains an unsupported parser")
        if self.retrieval == "hybrid":
            from evosprig.plugins.embeddings import EmbeddingConnection
            if not self.embeddings:
                raise ValueError("hybrid retrieval needs an embeddings connection")
            self.embeddings = EmbeddingConnection.model_validate(self.embeddings).model_dump()
        elif self.embeddings:
            from evosprig.plugins.embeddings import EmbeddingConnection
            self.embeddings = EmbeddingConnection.model_validate(self.embeddings).model_dump()
        return self


def check_size(value, maximum, label):
    if maximum is not None and value > maximum:
        raise ValueError(f"{label} exceeds configured limit ({maximum})")


def _ocr(path, config):
    try:
        result = subprocess.run(
            ["tesseract", str(path), "stdout", "-l", config.ocr_languages],
            capture_output=True, timeout=config.ocr_timeout_seconds, check=False,
        )
    except FileNotFoundError:
        raise ValueError("OCR requires Tesseract and the configured language packs; install them or configure ocr: disabled") from None
    except subprocess.TimeoutExpired:
        raise ValueError("OCR exceeded ocr_timeout_seconds") from None
    if result.returncode:
        raise ValueError("Tesseract OCR failed; check the document and installed ocr_languages")
    return result.stdout.decode("utf-8", errors="replace")


def extract_document(path, filename, config):
    """Return extracted text and page offsets. Never follow embedded URLs or macros."""
    path = Path(path)
    extension = Path(filename).suffix.lower()
    if extension not in config.allowed_extensions:
        raise ValueError(f"file type {extension or '(none)'} is not enabled")
    check_size(path.stat().st_size, config.max_file_bytes, "file bytes")
    parts, pages, length = [], [], 0

    def add(text, page=None):
        nonlocal length
        check_size(length + len(text), config.max_extracted_chars, "extracted characters")
        if page is not None:
            pages.append({"page": page, "start": length, "end": length + len(text)})
        parts.append(text)
        length += len(text)

    if extension in {".txt", ".md"}:
        with path.open(encoding="utf-8-sig") as stream:
            while text := stream.read(65536):
                add(text)
    elif extension == ".docx":
        # Read the document XML only, not embedded media, macros or external links.
        with zipfile.ZipFile(path) as archive:
            info = archive.getinfo("word/document.xml")
            # XML markup needs more room than visible text but is still deployment-bounded.
            check_size(info.file_size, config.max_extracted_chars * 20 if config.max_extracted_chars else None, "Word XML bytes")
            with archive.open(info) as xml:
                for _, element in ElementTree.iterparse(xml, events=("end",)):
                    if element.tag.endswith("}p"):
                        text = "".join(item.text or "" for item in element.iter() if item.tag.endswith("}t"))
                        add(text + "\n")
                        element.clear()
    elif extension == ".pdf":
        try:
            import pypdfium2 as pdfium
        except ImportError:
            raise ValueError("PDF import requires pip install 'evosprig[documents]'") from None
        with _PDF_LOCK, closing(pdfium.PdfDocument(path)) as pdf:
            check_size(len(pdf), config.max_pages, "PDF pages")
            for index in range(len(pdf)):
                with closing(pdf[index]) as page:
                    with closing(page.get_textpage()) as text_page:
                        text = text_page.get_text_bounded()
                    needs_ocr = config.ocr == "always" or (config.ocr == "auto" and not text.strip())
                    if needs_ocr:
                        with tempfile.TemporaryDirectory(prefix="evosprig-ocr-", dir=path.parent) as folder:
                            image_path = Path(folder) / "page.png"
                            scale = config.ocr_dpi / 72
                            check_size(int(page.get_width() * page.get_height() * scale * scale), config.max_ocr_pixels, "OCR image pixels")
                            bitmap = page.render(scale=scale)
                            try:
                                bitmap.to_pil().save(image_path)
                            finally:
                                bitmap.close()
                            text = _ocr(image_path, config)
                    elif not text.strip() and config.ocr == "disabled":
                        raise ValueError(f"page {index + 1} has no selectable text; enable OCR for scanned PDFs")
                    add(text + "\n", index + 1)
    else:
        if config.ocr == "disabled":
            raise ValueError("image documents require OCR")
        from PIL import Image
        with Image.open(path) as image:
            check_size(image.width * image.height, config.max_ocr_pixels, "OCR image pixels")
            check_size(getattr(image, "n_frames", 1), config.max_pages, "image pages")
            with tempfile.TemporaryDirectory(prefix="evosprig-ocr-", dir=path.parent) as folder:
                for index in range(getattr(image, "n_frames", 1)):
                    image.seek(index)
                    image_path = Path(folder) / "page.png"
                    image.convert("RGB").save(image_path)
                    add(_ocr(image_path, config) + "\n", index + 1)
    text = "".join(parts)
    if not text.strip():
        raise ValueError("document has no readable text")
    return text, pages


class DocumentLibrary:
    def __init__(self, memory, config=None):
        self.memory = memory
        self.defaults = config if isinstance(config, DocumentConfig) else DocumentConfig.model_validate(config or {})
        with memory._transaction() as db:
            db.execute("CREATE TABLE IF NOT EXISTS document_settings(scope TEXT PRIMARY KEY, body TEXT NOT NULL)")

    def config(self, scope):
        with self.memory._transaction(False) as db:
            row = db.execute("SELECT body FROM document_settings WHERE scope=?", (scope.key,)).fetchone()
        return DocumentConfig.model_validate({**self.defaults.model_dump(), **(json.loads(row[0]) if row else {})})

    def configure(self, scope, values):
        config = DocumentConfig.model_validate(values)
        with self.memory._transaction() as db:
            db.execute("INSERT INTO document_settings VALUES(?,?) ON CONFLICT(scope) DO UPDATE SET body=excluded.body", (scope.key, config.model_dump_json()))
        return config

    def ingest_text(self, scope, *, title, text, source, pages=None, config=None, operation_id=None, submitted_at=None):
        config = config or self.config(scope)
        return DocumentRetriever(self.memory).ingest(
            scope, title=title, text=text, source=source, chunk_size=config.chunk_size,
            chunk_overlap=config.chunk_overlap, max_chars=config.max_extracted_chars,
            pages=pages, replace=True, revision=operation_id or uuid.uuid4().hex, submitted_at=submitted_at or time.time(),
        )

    def ingest_file(self, scope, path, *, filename=None, source=None, config=None, operation_id=None, submitted_at=None):
        filename = filename or Path(path).name
        config = config or self.config(scope)
        submitted_at = submitted_at or time.time()
        text, pages = extract_document(path, filename, config)
        result = self.ingest_text(scope, title=Path(filename).stem[:500], text=text,
                                  source=source or "documents/" + filename, pages=pages, config=config, operation_id=operation_id, submitted_at=submitted_at)
        return {**result, "characters": len(text), "pages": len(pages)}

    def list(self, scope, *, offset=0, limit=100):
        if offset < 0 or not 1 <= limit <= 1000:
            raise ValueError("invalid document list bounds")
        # Select metadata in SQL, not all chunk bodies into Python.
        with self.memory._transaction(False) as db:
            rows = db.execute("""
                SELECT json_extract(body,'$.metadata.document_id'), json_extract(body,'$.metadata.title'),
                       json_extract(body,'$.source'), COUNT(*), MAX(json_extract(body,'$.updated_at'))
                FROM memories m WHERE scope=? AND json_extract(body,'$.content_type')='document'
                AND NOT EXISTS (SELECT 1 FROM ledger.tombstones t WHERE t.scope=m.scope AND t.id=m.id)
                AND NOT EXISTS (SELECT 1 FROM ledger.namespaces n WHERE n.scope=m.scope AND json_extract(m.body,'$.created_at')<=n.deleted_at)
                GROUP BY json_extract(body,'$.metadata.document_id') ORDER BY 5 DESC,1 LIMIT ? OFFSET ?
            """, (scope.key, limit, offset)).fetchall()
        return [dict(zip(("id", "title", "source", "chunks", "updated_at"), row, strict=True)) for row in rows]

    def delete(self, scope, document_id):
        with self.memory._transaction() as db:
            rows = db.execute("SELECT id,json_extract(body,'$.source') FROM memories WHERE scope=? AND json_extract(body,'$.metadata.document_id')=?", (scope.key, document_id)).fetchall()
            if not rows:
                raise KeyError("document not found")
            deleted_at = time.time()
            for source in {row[1] for row in rows}:
                db.execute("INSERT OR REPLACE INTO ledger.document_sources VALUES(?,?,?)", (scope.key, source, deleted_at))
            for identifier, _ in rows:
                db.execute("INSERT OR REPLACE INTO ledger.tombstones VALUES(?,?,?)", (scope.key, identifier, deleted_at))
                db.execute("DELETE FROM memories WHERE scope=? AND id=?", (scope.key, identifier))
        return {"deleted": document_id, "chunks": len(rows)}

    def retriever(self, scope):
        config = self.config(scope)
        memory = self.memory
        if config.retrieval == "hybrid":
            from evosprig.plugins.embeddings import EmbeddingConnection, OpenAIEmbeddings
            from evosprig.plugins.semantic_memory import HybridMemory
            memory = HybridMemory(memory, OpenAIEmbeddings(EmbeddingConnection.model_validate(config.embeddings)), cache_path=memory.path.with_suffix(".embeddings.sqlite"), persistent_cache_size=config.embedding_cache_entries)
        return DocumentRetriever(memory)
