# Agent memory

<a id="memory-and-documents"></a>

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

## Memory, context and application data

| Concern | Contents | Studio / runtime |
| --- | --- | --- |
| Long-term memory | Preferences, facts, experiences, relationships | **Memory**; `memory.*` tools |
| Working context | Current goals, progress, conversation summary and recent turns | Context blocks, graph inputs and ordinary model/agent nodes |
| Knowledge library | Manuals, contracts, business documents | **Knowledge**; `documents.search` / `documents.retrieve` |

Agents can use memory without a knowledge library. Both can use the same storage or retrieval algorithms while retaining separate scopes and lifecycles. Documents remain application data that customers can update after deployment; see [Knowledge libraries and RAG](rag.md).

### Managing long conversations

**Node settings → Memory** selects memory tools, pre-task recall and the tool-history budget. The budget shortens older tool observations sent to the model, preserving recent tool rounds, call/result pairs and the full run record. It counts characters, not model tokens. System and user messages are retained; protected content can exceed that budget.

Semantic compression uses an ordinary model or agent node. Pass it an earlier summary and older messages; connect its output and the unchanged recent messages to the answering node. Choose its model and prompt independently. The application decides when to invoke it, such as after a length threshold or before the next turn. See the [working-context walkthrough](tutorials/working-context.md), with importable Python code and no document dependency.

`memory.summarize` stores a model-written summary of selected memory records with their source IDs. It does not automatically compress a conversation. Context blocks hold bounded working notes; graph outputs let the deployed application retain a new summary between requests.

## Configure retrieval-based external memory

External memory keeps records outside the model context window and retrieves relevant records for a task. Configure it separately from the business knowledge library. In **Memory**, create a bank, add facts or experiences, and choose **Retrieval & writes**:

| Mode | How records are selected | Extra service |
| --- | --- | --- |
| `lexical` | BM25 keyword relevance | None |
| `semantic` | Cosine similarity of embeddings | Local or API embedding model |
| `hybrid` | BM25 and vector ranks fused with RRF | Local or API embedding model |

Use **Retrieval test** to inspect the selected bank's hits and sources. A minimum cosine similarity can filter vector matches; hybrid search can still return keyword matches. The embedding model is separate from the agent's language model.

On an agent node, open **Memory → Retrieval-based memory**, select the bank, and click **Connect memory bank**. Enable **Retrieve automatically before each task** for harness recall, or let the agent call the search tool as needed. Automatic recall exposes query input, result count and context character budget. **Add a memory write tool** attaches its write tool. Workflow and runtime write permissions still apply.

Nodes attached to the same bank share records within the same user and project. Give nodes different banks for separate memories. A bank's **Agent writes** setting can disable agent write tools while developers continue maintaining records in Studio. Context blocks and temporal relationships also belong to the selected bank.

### Deployment configuration

Add `memory` beside `models` in `deployment.yaml`:

```yaml
memory:
  banks:
    default:
      retrieval: lexical
    writer:
      retrieval: hybrid
      embeddings:
        base_url: http://127.0.0.1:8011/v1
        model: your-embedding-model
        api_key_env: MEMORY_EMBEDDING_API_KEY
        timeout_seconds: 30
      min_similarity: 0.3
      embedding_batch_size: 64
      embedding_cache_entries: 100000
      retrieval_timeout_seconds: 120
      agent_writes: true
```

Use an OpenAI-compatible `/embeddings` endpoint, including a local embedding server. Set `MEMORY_EMBEDDING_API_KEY` in the process environment; a local service without authentication can use a placeholder value. The URL, model, batch size, cache size, similarity threshold and tool timeout are configurable. Studio saves per-project bank settings in the workspace; those settings override the corresponding profile bank.

### Use from Python

```python
from evosprig.sdk import Builder

builder = Builder("remembering-assistant", {"type": "object"},
                  {"type": "object"}, spec_version="0.3")
builder.default_model("main", requires=["text", "tool_calling"])
builder.memory_tool("recall_preferences", bank="writer", operation="search")
builder.memory_tool("save_preference", bank="writer", operation="write")
builder.node(
    "assistant", "agent", instructions="Use the user's preferences when relevant.",
    inputs={"question": {"ref": "input.question"}},
    output_schema={"type": "object"},
    tools=["recall_preferences", "save_preference"],
    harness={"memory": {"tool": "recall_preferences", "query_input": "question",
                        "limit": 5, "max_chars": 4000}},
)
builder.output(answer={"ref": "nodes.assistant.output.text"})
builder.execution(allow_side_effects=True)
spec = builder.build_spec()
```

Declare `writer` in the deployment profile above. Run with `--profile deployment.yaml --allow-writes` to allow the selected write tool. The tool plugins are `memory.writer.search` and `memory.writer.write`; the default bank retains `memory.search` and `memory.write`. Other operations are `recall`, `remember`, `summarize`, `context` and `relations`. Named `recall` uses the bank's retrieval strategy before applying experience relevance, importance and recency ranking.

Python, HTTP and container exports carry the selected banks in `memory-config.json` and `deployment.example.yaml`. Importing the ZIP restores these settings. Records remain in the runtime workspace, so reuse that workspace across sessions; application exports contain configuration, not personal memories. Embedding vectors are cached on disk and reused after restart. Changed or deleted source records are checked again on each retrieval.

### Studio API

- `GET /api/projects/{id}/memory/banks`: list configured banks.
- `PUT /api/projects/{id}/memory/banks/{name}`: create or configure a bank.
- Add `?bank=writer` to memory record, search, export, context and relationship routes to select a bank. Omission selects `default`.

The server derives user and project identity before selecting the bank. A model's tool arguments cannot change that identity or choose another bank. To connect a different storage implementation from Python, implement the `MemoryStore` contract and bind it with `register_memory_tools`; the built-in configurable banks use SQLite and local or API embeddings.

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

The shared loader supports documents and folders, retains sources and page/character citations, and replaces an updated source after successful parsing. Configure parser, chunking and upload quotas in the deployment profile. See [Knowledge libraries and RAG](rag.md).

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
