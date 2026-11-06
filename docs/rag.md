# Knowledge libraries and RAG

[English](rag.md) · [简体中文](zh-CN/rag.md)

A knowledge library belongs to an application and its user/tenant scope. Documents can be added from Studio, Python, the CLI or an exported HTTP service. Updating a source makes the new text available to the next retrieval without changing the agent graph.

## Install parsers

```bash
python -m pip install 'evosprig[documents,server,models]'
# Debian / Ubuntu: OCR and language packs
sudo apt-get install tesseract-ocr tesseract-ocr-eng tesseract-ocr-chi-sim
```

For a source checkout, use `python -m pip install -e '.[documents,server,models]'`.
An exported application includes `requirements-documents.lock`; install it alongside
`requirements.lock` for PDF and image imports. Install Tesseract in that application's
runtime as well when using OCR. Container exports support `docker build --build-arg DOCUMENT_PARSERS=1 -t my-agent .`; `OCR_LANGUAGES="eng chi-sim"` selects the installed language packs.

| Input | Parser | Citation location |
| --- | --- | --- |
| Markdown / TXT | UTF-8, including BOM | Extracted-text character range |
| PDF | PDFium text extraction; OCR on scanned pages | Page number and character range |
| Word `.docx` | Paragraphs and tables from document XML | Character range |
| PNG, JPEG, TIFF, WebP | Tesseract OCR, including multipage TIFF | Image page and character range |

Set `ocr: auto` to recognize pages without selectable text, `always` to OCR every
PDF page, or `disabled` for text-only extraction. `ocr_languages: chi_sim+eng` uses
both installed language packs. OCR text is searchable; check the retrieved page
when exact names or numbers matter.

## Configure intake and retrieval

Put this section beside `models` and `tools` in `deployment.yaml`:

```yaml
documents:
  customer_uploads: true
  max_file_bytes: 52428800       # 50 MiB; null removes this quota
  max_batch_files: 1000         # CLI folder / Studio file selection
  max_extracted_chars: 20000000 # per document; null removes this quota
  max_pages: 2000               # per PDF / multipage image; null removes this quota
  max_ocr_pixels: 20000000      # per rendered page; null removes this quota
  allowed_extensions: [.md, .txt, .pdf, .docx, .png, .jpg, .jpeg, .tif, .tiff, .webp]
  chunk_size: 1200              # characters, 200..100000
  chunk_overlap: 150            # smaller than chunk_size
  ocr: auto
  ocr_languages: chi_sim+eng
  ocr_dpi: 180
  ocr_timeout_seconds: 180
  max_pending_jobs: 128         # per scope; return 429 when the queue is full
  ingestion_workers: 2         # service-wide worker count at startup
  retrieval: lexical
```

These are editable deployment defaults. Studio's **Memory and documents → Intake &
deployment** saves project overrides and includes them in exports. Changing chunk
settings affects subsequent imports; upload an existing source again to reindex it.
Uploads stream to temporary files, then parse in worker threads. File byte limits are
checked while reading, including requests without `Content-Length`. PDFium operations
are serialized because its native library is not thread-safe.

The lexical index persists in SQLite FTS5. Chinese text is indexed by character and
Latin text by word. Retrieval reads indexed matches instead of tokenizing the entire
corpus on every question. The independent deletion ledger also applies to indexed
results and restored backups.

For semantic retrieval, configure a compatible embedding endpoint:

```yaml
documents:
  retrieval: hybrid
  embeddings:
    base_url: http://127.0.0.1:8000/v1
    model: your-embedding-model
    api_key_env: EMBEDDING_API_KEY
    timeout_seconds: 60
  embedding_cache_entries: 100000
```

The endpoint can be a provider API or a local embedding service. The selected model
must expose `/embeddings`; a chat-only model is not an embedder. Hybrid search fuses
BM25 and cosine ranks. Content-addressed vectors persist across calls and service
restarts; query authorization always comes from the current document store. This
adapter performs an exact vector scan. For an existing large vector database, bind
its search API as an [HTTP or MCP tool](tools.md), return text/source/page fields and
use that tool in the same retrieval node or agent.

## Import, update and delete

```bash
evosprig data add-documents ./knowledge --project document-chat \
  --workspace .evosprig/docs --profile deployment.yaml
```

The CLI processes one document at a time. It uses `documents/<relative path>` as the
source ID. Reimporting the same source replaces it in one transaction after parsing
succeeds; a failed import leaves the prior version available. Concurrent uploads of
the same source cannot let an older submission overwrite a newer indexed version.
Deleting a source also prevents an already queued upload from restoring it later;
an explicit new upload can add it again.

Python applications use the same library:

```python
from evosprig.core.journal import Scope
from evosprig.core.memory import MemoryScope
from evosprig.plugins.document_library import DocumentConfig, DocumentLibrary
from evosprig.plugins.sqlite_memory import SQLiteMemory

scope = MemoryScope(Scope("document-chat"), namespace="documents")
library = DocumentLibrary(SQLiteMemory(".evosprig/docs/memory.sqlite"),
                          DocumentConfig(ocr_languages="chi_sim+eng"))
result = library.ingest_file(scope, "manual.pdf", source="manuals/product")
print(library.retriever(scope).search(scope, "How long is the warranty?"))
print(library.list(scope, offset=0, limit=50))
library.delete(scope, result["document_id"])
```

Use the same workspace and application ID for ingestion and execution. In an
authenticated Studio, upload through the logged-in project's API to retain the
server-assigned user and tenant. Models cannot select another user's scope.

## Three graph patterns

| Pattern | Canvas / SDK | Use it when |
| --- | --- | --- |
| Retrieve every time | A tool node using `documents.search`, then a model node whose inputs include `nodes.retrieve.output.citations` | Every answer must consult the knowledge library |
| Let the agent decide | Declare `documents.search` in an agent's tools; optionally configure harness memory retrieval | Some questions require documents, others do not |
| Expand and diversify | A model generates up to eight query formulations; `documents.retrieve` combines them with rank fusion and diversity | Terminology varies or one question spans several sections |

`documents.search` accepts `query` and optional `limit`. `documents.retrieve` accepts
`queries`, `limit` and `diversity` (0..1). Both return `citations`, containing the
passage, source, title, character offsets, score and page numbers when available.
Put retrieved passages in the model's **inputs**, with instructions to use and cite
them as source data. The [tools reference](tools.md) covers custom retrieval APIs;
[agent resources](agent-resources.md) covers automatic harness retrieval.

In Studio, use **Retrieval test** to inspect exact passages first. Then debug the
retrieval node, the answering node with those passages, and the combined graph.
Evaluate real customer questions for answer correctness, citation validity and
missing-information behavior. [Scoped self-evolution](tutorials/scoped-evolution.md)
can search one answer prompt, a query-rewriting skill or declared harness settings
against that task set.

## Let customers maintain the deployed library

Enable `customer_uploads`, export the HTTP target, configure its models and start it:

```bash
python -m pip install -r requirements.lock -r requirements-documents.lock
python -m pip install --no-deps .
export EVOSPRIG_SERVICE_TOKEN='replace-with-a-secret'
python serve.py --profile deployment.yaml --workspace ./customer-state --port 8080
```

Keep the token in your business backend, which authenticates your customer and
proxies the allowed actions. The export is a backend; it does not automatically
supply a customer website. Use a separate deployment workspace for each customer's
knowledge library.

```bash
curl -H "Authorization: Bearer $EVOSPRIG_SERVICE_TOKEN" \
  -H 'Content-Type: application/octet-stream' --data-binary @manual.pdf \
  'http://127.0.0.1:8080/documents/upload?filename=manual.pdf'
```

| Method | Route | Result |
| --- | --- | --- |
| POST | `/documents/upload?filename=manual.pdf&source=manuals/product` | 202 with ingestion job ID; `source` is optional |
| GET | `/documents/jobs/{id}` | `queued`, `processing`, `succeeded` or `failed`, with result/error |
| GET | `/documents/jobs` | The scope's 50 most recent imports |
| POST | `/documents` | JSON `{title, text, source}` for short text |
| GET | `/documents?offset=0&limit=100` | Paged document list |
| GET | `/documents/search?query=warranty&limit=5` | Source passages |
| DELETE | `/documents/{id}` | Delete this document version and its chunks |
| GET | `/documents/settings` | Effective deployment settings |

Customers cannot modify deployment settings through these routes. Set them as the
developer, in the profile or Studio before export. When `customer_uploads` is false,
the management API returns 403 and the agent can still search preloaded documents.
Queued jobs survive a service restart; a crashed worker's processing claim is
recovered after its ten-minute lease expires. Graceful shutdown finishes active
parsing. Successful or failed parsing removes the temporary upload. Keep the workspace
persistent and include the current deletion ledger in backup/recovery procedures.

Studio provides the corresponding routes under
`/api/projects/{project_id}/documents`, including developer-only `PUT /settings`.
