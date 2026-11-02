# Memory and documents

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
resources. The runtime does not automatically promote retrieved text into policy.

`DocumentRetriever.ingest` accepts bounded plain text, a title and source identifier.
It creates deterministic chunks and citation references containing exact offsets.
Search is a reproducible lexical baseline, including Chinese characters. It does
not claim embedding or semantic retrieval. Documents use the `documents` namespace.
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
with the allowed loopback Host forwarded. This Alpha baseline does not implement
organization sharing, an identity provider or account administration.

Memory routes are under `/api/projects/{id}/memory`; document upload, listing,
search and delete are under `/api/projects/{id}/documents`. A memory data export is
an explicit separate operation from an application export.
