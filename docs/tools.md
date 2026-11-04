# Tool connections

Python functions use `Tool` and explicit registration. Input/output JSON schemas,
versions, timeouts, effect class and idempotency are part of the contract. A synchronous
function runs in a thread; an asynchronous function runs on the event loop.
`ExternalTool` defines idempotent `submit`, `poll` and optional `cancel` callbacks for
jobs hosted by an external executor. The journal persists the external job ID.

## Scheduled steps and agent-selected calls

Use a `tool` node for a required step, such as OCR, parsing an invoice or submitting a video render. Its inputs come from the graph and the runtime invokes it directly. Attach the same tool to an `agent` node when the model should decide whether to call it. The tool contract stays the same in both cases.

A local calculation whose result depends only on its arguments can declare `Tool(..., pure=True)`. The runtime can repeat that calculation after interruption and batch its checkpoints with `execution.pure_checkpoint_interval`. ComfyUI preparation nodes use this for graph connections and parameter calculations; model calls, file access and external services use the regular operation journal. See [large ComfyUI graphs](comfyui.md#large-graphs).

## Deployment bindings

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
`output_schema` and an explicit `side_effect`. Structured results are the default;
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

## Tool selection and concurrent calls

AgentSpec 0.3 agent nodes can opt into reusable tool policies:

```yaml
type: agent
model: main
tools: [search, lookup, calculator]
parallel_tool_calls: true
tool_errors: feedback
tool_selection: relevant
tool_limit: 2
```

`parallel_tool_calls` overlaps independent read-only calls from one model response, respecting `execution.max_parallel_tools`. Results return to the model in request order and each operation keeps its durable receipt. Write calls and asynchronous job tools remain sequential inside a model response. Graph-level `parallel` and `map` remain available for independent branches and batches.

`tool_selection: relevant` ranks names/descriptions against the node's inputs and exposes the top `tool_limit` tools from its existing allowlist. It is deterministic lexical discovery, useful for large registries; choose `all` when every tool should be available. A model call to an unexposed tool is rejected. Selection cannot discover or grant access to undeclared tools.

`tool_errors: feedback` lets the agent correct invalid arguments and explicitly declared read-only rejections. Read-only HTTP bindings turn status 400/422 into a generic argument-rejection observation without exposing the upstream response body. Other transport/server failures remain terminal. Uncertain writes still require reconciliation. Together with ReAct-style tool loops, JSON-schema validation, dynamic map and human approvals, these policies work across applications.

## Code, browser and OCR tools

The built-in `code.python` interpreter runs deterministic JSON transformations. These computations use node checkpoints, with `execution.pure_checkpoint_interval` controlling batching; model calls and external tool operations flush pending computations before they start.

The optional [Toolbox](../apps/toolbox/README.md) provides Python execution, HTML interaction checks/screenshots and offline English OCR through standard HTTP bindings. Artifacts are returned as download receipts, so binary images do not fill the model's context. Use the same contracts to bind your own sandbox or media service.

## Bounded output repair

Model and agent nodes in AgentSpec 0.3 can set `output_errors: feedback` and `max_output_retries: 2`. Invalid JSON, schema mismatches and explicit output-limit errors receive a bounded correction turn. Network errors are not automatically retried. All correction calls consume the original run/study budget; reported usage from a truncated response is charged before retrying; calls without usage retain their reservation.

An agent can also set `max_tool_rounds: 4`. Once the limit is reached, the runtime removes tool descriptors and asks for a final answer from the collected observations. This bounds repeated retrieval without changing the application's tools or prompts. Omit it to retain the run-wide call limit.

Original papers and implementation mappings: [Research references](references.md).

## Shared team documents

Use [workspace tools](shared-workspaces.md) for revisioned documents, edit history and durable wake-ups. A write tool can raise `ToolRejectedError(code, message)` when it rejects a request before any side effect; the runtime records the rejection and gives an agent configured with `tool_errors: feedback` a correction turn. Use this for failed preconditions such as revision conflicts. Ambiguous write failures enter reconciliation.
