# Memory and documents

[English](memory.md) · [简体中文](zh-CN/memory.md) · [Documentation](README.md)

SQLite is the baseline `MemoryStore`. Each record belongs to an exact
`tenant / user / project / role / namespace` scope. Selection applies that scope
before relevance ranking. The baseline supports explicit writes, exact deduplication,
revision-checked updates, validity windows, lexical search, deletion, export and
namespace reset. Conflicting facts remain separate records with their sources;
automatic semantic conflict resolution is an extension capability.

```python
from evosprig.core.journal import Scope
from evosprig.core.memory import MemoryScope
from evosprig.plugins.sqlite_memory import SQLiteMemory

memory = SQLiteMemory("workspace/memory.sqlite")
scope = MemoryScope(Scope("research", user="alice", tenant="team"))
record = memory.write(scope, "Use concise Chinese replies", source="user:explicit")
assert memory.search(scope, "Chinese")[0]["id"] == record["id"]
memory.delete(scope, record["id"])
```

`memory.search`, `memory.write` and `documents.search` can be declared as tool
plugins. CLI, Studio and independent exports bind their scope outside tool
arguments. A model cannot supply another user or project. Writes follow the same
three-part write opt-in as other effectful tools. Retrieval results are untrusted
data and retain source attribution; keep system policies in versioned prompt/skill
resources.

`DocumentRetriever.ingest` accepts bounded plain text, a title and source identifier.
It creates deterministic chunks and citation references containing exact offsets.
Default document search uses BM25, including Chinese characters. Wrap the store in
`HybridMemory` to add semantic ranking. Documents use the `documents` namespace.
A citation can be verified by slicing the original text at `[start:end]`.

## Deletion and restore

`memory.sqlite` contains records. `memory.deletions.sqlite` is an independent,
monotonic deletion ledger containing IDs, scopes and deletion times, without the
deleted content. Delete removes the live row and records a tombstone in one attached
SQLite transaction. Namespace reset also records a cutoff for older backups.
Every read, search, export and restore checks the current ledger.

Use `memory.export(scope)` and `memory.restore(scope, records)` for a scoped backup
and restore. Restore never overwrites newer live records or crosses scope. Retain
the latest ledger when restoring a backup of the memory database. Restoring both
files from an old backup would erase later deletion history and is unsupported.
Backing up/migrating the ledger separately is required for disaster recovery.
These are operational databases; generated application exports exclude both.

## API identities

The development server defaults to the `local` principal. For separate users, pass
`--auth-file identities.yaml` with environment references:

```yaml
- user: alice
  tenant: team
  token_env: ALICE_API_TOKEN
- user: bob
  tenant: team
  token_env: BOB_API_TOKEN
```

Set the corresponding tokens in the server environment and use bearer authentication.
Each principal owns its projects, runs, facts and documents. Request bodies cannot
choose the identity; unknown and out-of-scope records both return 404. The server
continues to bind to loopback; expose it through an authenticated TLS reverse proxy
with the allowed loopback Host forwarded. Manage the identity list through the
server configuration file.

Memory routes are under `/api/projects/{id}/memory`; document upload, listing,
search and delete are under `/api/projects/{id}/documents`. A memory data export is
an explicit separate operation from an application export.

## Retrieval strategies

SQLite search uses BM25 term-frequency and length normalization, with English word and CJK character tokenization. Pass `at=<unix timestamp>` for historical validity and `content_type` to filter records.

`HybridMemory(memory, embedder)` combines BM25 and cosine ranks through reciprocal rank fusion. An embedder supplies `model_id` and `embed(list[str]) -> list[list[float]]`. Batches and the vector cache are bounded; every query re-reads the authorized records and deletion ledger before ranking. Configure your embedding provider outside model-controlled arguments.

```python
from evosprig.plugins.semantic_memory import HybridMemory

# embedding_provider implements the Embeddings protocol.
semantic = HybridMemory(memory, embedding_provider)
hits = semantic.search(scope, "preferred communication style", limit=5)
```

## Context blocks and temporal relations

```python
from evosprig.plugins.structured_memory import StructuredMemory

structured = StructuredMemory(memory)
profile = structured.set_context(scope, "profile", "Alice prefers concise replies.",
                                 source="user:explicit", max_chars=1000)
structured.set_context(scope, "profile", "Alice prefers concise replies in English.",
                       source="user:explicit", revision=profile["revision"])
structured.set_relation(scope, "Alice", "works_on", "Orion", source="user", valid_from=100)
structured.set_relation(scope, "Alice", "works_on", "Atlas", source="user", valid_from=200)
assert structured.relations(scope, "Alice", at=150)[0]["metadata"]["relation"][2] == "Orion"
```

Context blocks use revision-checked updates and a configurable character budget. Temporal relation updates close the previous interval atomically; bounded graph traversal follows relations valid at the query time. All records share the existing scope and deletion ledger.

The API exposes `/api/projects/{id}/context`, `/context/{name}` and `/relations`. The runtime's `memory.context` and `memory.relations` tools provide read access in the deployment-bound user scope. These tools are included in standalone exports. See the [personal assistant](../examples/personal-memory/).

A compatible embedding API can be used directly:

```python
from evosprig.plugins.embeddings import EmbeddingConnection, OpenAIEmbeddings

provider = OpenAIEmbeddings(EmbeddingConnection(
    base_url="https://api.openai.com/v1", model="text-embedding-3-small",
    api_key_env="OPENAI_API_KEY",
))
semantic = HybridMemory(memory, provider)
```

Install the `models` extra for the HTTP client. This synchronous memory adapter should run in a worker/thread when called from an asynchronous application. Its requests have explicit timeouts, bounded response sizes and no automatic retries.

## Load a document collection

```bash
evosprig data add-documents ./documents --project document-chat --workspace .evosprig/docs
```

The shared loader accepts a text file or a folder of `.md`/`.txt` files (up to 128
files, 1 MB each). It preserves source labels and excerpt offsets for citations.
Adding unchanged files is idempotent. A changed file creates a new document version;
remove obsolete records in Studio when replacing a collection. The CLI uses the
local identity. In an authenticated deployment, add documents through the signed-in
user's Studio/API to retain that user's scope. Run the agent with the same workspace
and project ID. See [Chat with your documents](../examples/document-chat/).

## Experience recall and linked summaries

`EpisodicMemory` ranks authorized records using query relevance, importance and exponential recency decay. Weights and half-life are configurable in the SDK. Links connect related records inside the same scope, and recall can include those neighbors.

```python
from evosprig.plugins.episodic_memory import EpisodicMemory

experiences = EpisodicMemory(memory)
record = experiences.remember(scope, "The user avoids peanuts", source="user:explicit",
                              importance=1.0, tags=["food"])
experiences.summarize(scope, "Avoid peanuts when planning meals", [record["id"]])
hits = experiences.recall(scope, "meal preferences", limit=5)
```

Native tools `memory.remember`, `memory.recall` and `memory.summarize` expose these operations to agents. Summaries are supplied by the calling model and retain their source IDs and revisions. Deleting, expiring or changing a source hides stale derived summaries, including after restoration. The agent chooses when to summarize and which experiences to link.

This adds relevance/importance/recency recall and linked experience notes alongside BM25, hybrid semantic retrieval, context blocks and temporal relationships. It draws on ideas used by [Generative Agents](https://github.com/joonspk-research/generative_agents) and [A-Mem](https://github.com/agiresearch/A-mem), implemented as native memory policies.

## Multi-query retrieval

`documents.retrieve` accepts `queries` (up to eight), `limit` and `diversity`. An agent can formulate complementary queries, combine their results with reciprocal-rank fusion and reduce near-duplicate excerpts with a lexical diversity penalty. Every result keeps its original citation and source offsets. It uses the same document store and scope checks as single-query search.

Use single-query BM25 for exact terms, multi-query retrieval for questions with several facets, hybrid retrieval when paraphrases matter, and context blocks for short facts that must always be available. Embeddings remain optional; none of these strategies requires training model weights.

Original papers and implementation mappings: [Research references](references.md).
