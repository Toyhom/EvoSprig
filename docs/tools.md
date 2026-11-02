# Tool connections

Python functions use `Tool` and explicit registration. Input/output JSON schemas,
versions, timeouts, effect class and idempotency are part of the contract. A synchronous
function runs in a thread; an asynchronous function runs on the event loop.
`ExternalTool` defines idempotent `submit`, `poll` and optional `cancel` callbacks for
jobs hosted by an external executor. The journal persists the external job ID.

HTTP and MCP tools are administrator-configured deployment bindings. Specs refer to
the logical plugin name and version. Profiles may contain `models` and `tools`:

```yaml
models: {}
tools:
  http.lookup:
    kind: http
    name: http.lookup
    version: '1'
    description: Look up a fact in the project service
    endpoint: https://tools.example/lookup
    method: GET
    auth_env: LOOKUP_TOKEN
    side_effect: read_only
    input_schema:
      type: object
      properties:
        query: {type: string}
      required: [query]
      additionalProperties: false
    output_schema:
      type: object
      properties:
        answer: {type: string}
      required: [answer]
      additionalProperties: false
```

`GET` encodes scalar inputs as query parameters; other supported methods send JSON.
Responses must satisfy the output schema. Redirects are rejected, response size and
time are bounded, and errors exclude upstream bodies. Use HTTPS or a loopback HTTP
endpoint. A write that supports deduplication sets `idempotent: true`; the service
must honor the `Idempotency-Key` header. Authorization is read from the referenced
environment variable and is never serialized in a run or export.

Use `evosprig run agent.yaml --profile deployment.yaml ...`. Runs record the validated
tool bindings, so restarting a worker uses the original endpoint and contract.
`evosprig export agent.yaml --profile deployment.yaml --out exported` bundles the
required adapter and declared non-secret bindings. It excludes memory, databases and
unrelated deployment connections. Changing a service's behavior requires a new tool
version and a fresh contract verification.

## MCP subset

Install `evosprig[mcp]`. Alpha pins Python SDK **1.30.0**, protocol **2025-11-25**, and
**Streamable HTTP**. The adapter initializes a session, discovers tools with bounded
pagination, checks pinned schemas before calling, and closes its session. Resource
reads and prompt retrieval are available through `MCPClient`. Received instructions,
resources and prompts are returned as data; using them is an explicit application
choice. Sampling, elicitation, roots, OAuth flows, stdio and experimental task
extensions are outside this adapter's support matrix.

```python
from evosprig.plugins.mcp_tools import MCPClient, MCPConnection

client = MCPClient(MCPConnection(endpoint="http://127.0.0.1:8000/mcp"))
manifest = await client.discover()
print(manifest["protocol_version"], manifest["tools"])
```

Copy the selected tool's `inputSchema` and `outputSchema` into a deployment entry
with `kind: mcp`, `name`, `remote_name`, `description`, `endpoint`, `input_schema`,
`output_schema` and an audited `side_effect`. Structured results are the default;
`result_format: content` returns a JSON object with content blocks for tools without
a structured output contract. MCP annotations alone do not grant write permission.
MCP writes have no generic idempotency guarantee, so receipt-unknown writes pause
under the same reconciliation rules as non-idempotent Python tools.

The official SDK allows method-preserving redirects on the same origin. Credentials
remain environment references. The adapter rejects tool schemas that differ from the pinned deployment contract.

Sources: [MCP specification](https://modelcontextprotocol.io/specification/2025-11-25),
[official Python SDK](https://github.com/modelcontextprotocol/python-sdk).

## Asynchronous HTTP jobs

`kind: external_http` is a write-only, idempotent job binding. Configure `endpoint`,
input/output schemas and optional `auth_env`, using the same HTTPS/loopback endpoint
rules as ordinary HTTP tools. POST sends the validated arguments as JSON and a stable
`Idempotency-Key` header, expecting `{"job_id":"safe-id"}`. GET `endpoint/{job_id}`
returns `{"status":"pending|succeeded|failed|canceled","output":...}`. DELETE cancels.
The job ID is journaled before polling; resume queries the saved ID. The remote service
must atomically bind an idempotency key to its original arguments. See the short-film
renderer for an executable example. Imported/exported bindings contain environment
references, and restored runs reject binding changes.

## Read-only SQLite

Use the same database tools in CLI runs, Studio and exported applications:

```yaml
models: {}  # Add your model binding here.
tools:
  database.schema:
    kind: sqlite
    name: database.schema
    operation: schema
    path_env: EVOSPRIG_SQLITE_PATH
    tables: [orders]
  database.query:
    kind: sqlite
    name: database.query
    operation: query
    path_env: EVOSPRIG_SQLITE_PATH
    tables: [orders]
    max_rows: 200
    max_vm_steps: 1000000
```

The database path is resolved from the environment. SQLite opens read-only; an
authorizer blocks writes, attachments, extensions and tables outside the allowlist.
`schema` takes `{}`. `query` takes `{"sql":"SELECT ...","parameters":[]}` and returns
`columns`, `rows` and `truncated`. Aggregate large datasets instead of requesting
all rows. An empty table allowlist permits reading all tables in the database.

To prepare a database from a CSV, use `evosprig data load-csv orders.csv --database
shop.sqlite --table orders`. Headers must be unique SQL identifiers. The importer
creates a new table transactionally and refuses to overwrite an existing table.
SQLite NUMERIC affinity converts numeric-looking values, including leading-zero
identifiers; use a preconfigured database when you need explicit column types.
Database files are never included in exports. See the [data analyst](../examples/data-analyst/).

## Let an agent correct a tool call

AgentSpec 0.3 agent nodes can set `tool_errors: feedback`. Invalid arguments and
explicit `ToolFeedbackError` rejections from read-only tools become tool observations:

```json
{"error":{"code":"sql_error","message":"no such column: sales"}}
```

The model can then correct its call. Rejections are journaled and the normal run
budgets bound retries. Custom read-only tools may raise `ToolFeedbackError(code,
message)` with a brief message intended for the model. Keep credentials and private
transport details out of that message. General exceptions, output-schema failures
and tool-allowlist violations still stop the run. Write operations with an unknown
outcome pause for reconciliation. The default `tool_errors: raise` preserves the
existing fail-fast behavior.
