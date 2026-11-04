# Durable runtime

[English](durable-runtime.md) · [简体中文](zh-CN/durable-runtime.md) · [Documentation](README.md)

AgentSpec 0.2 adds `transform`, `condition`, `join`, bounded `loop`, named `parallel`
branches and `human` input nodes. The original 0.1 documents keep their canonical
representation. Conditions use typed predicates; no Python expressions are evaluated.
Conditional edges carry `when: true|false`, and a `join: selected` node joins the
branches that ran. Loop output becomes the next iteration's input. `max_iterations`
and the shared execution budget bound nested graphs.

The CLI and local API persist the frozen version, node outputs, model messages,
operation receipts and events in SQLite. Workers claim expiring leases and use a
monotonic generation to reject stale commits. Completed work is reused after
restarts. Multiple local workers may share the journal. SQLite files and locks need
a filesystem with supported locking; object storage is unsuitable.

Lease renewal runs independently of the execution loop. SQLite stores lease,
cancellation and scheduling state separately from checkpoints, so polling a
multimodal run does not deserialize its images and message history. Existing
journals migrate atomically when opened; stop older workers before upgrading.
Large checkpoint strings (16 KiB and above), including inline image previews, are
stored once per run in the same SQLite transaction. Checkpoints refer to these
values by content hash; reads restore the original JSON. State changes rewrite
compact references while unchanged media stays in place. Back up the complete
SQLite database, which contains both the state and its blobs.

`Runtime(..., lease_seconds=30)` sets the lease duration for your storage latency.
Snapshot and operation writes continue to check the worker's generation and expiry.

`execution.timeout_seconds` bounds active worker time across resumes. The default
is 60 seconds; AgentSpec 0.3 allows up to 86,400 seconds for long applications.
Time spent suspended for human input or an external job is excluded. Configure an
external tool's `job_timeout_seconds` separately for its rendering or execution deadline.

After downtime, the runtime polls an existing external job before applying its
deadline. A completed result is collected; a job that is still pending or
unreachable past its deadline reports `external_timeout`.

After fixing a service or deployment issue, explicitly queue a failed run again:

```python
runtime.retry_failed(run_id)
result = await runtime.resume(run_id)
```

The retry keeps the frozen version, completed nodes, external job IDs, operation
receipts and consumed budgets. A `run.retry_requested` event records the previous
error. Resolve failed or canceled jobs in their external service before retrying.
To change the workflow or its budget, start a new run or debug a selected subflow.

```bash
evosprig run agent.yaml --input '{"text":"draft"}' --mock --workspace ./workspace
evosprig runs --workspace ./workspace
evosprig resume RUN_ID --workspace ./workspace --path graph/approval --response '{"text":"approved"}'
evosprig cancel RUN_ID --workspace ./workspace
```

`human` nodes validate responses against their output schema and pause in
`waiting_input`. Resume keeps the original version even if the editable project
has changed. The API exposes run history, input, resume, cancel and resumable SSE
under `/api/projects/{id}/runs` and `/api/runs/{id}`.

Inspect a saved step with `GET /api/runs/{id}/nodes/{node_path}`, for example
`graph/shots/item-1/takes/iteration-0/render`. The response contains that step's
inputs, output, status, correction feedback and canvas location. Node failures
emit `node.failed`; the run error includes the first failing `node_id`.
Studio uses these records to open the corresponding item or take for debugging.

Write tools require a durable journal, runtime `allow_writes=True` and spec
`execution.allow_side_effects: true`. Idempotent tools must honor the provided
operation key. A receipt-unknown non-idempotent operation pauses for reconciliation;
it cannot be replayed safely without a `recover` hook. An external job must support
idempotent submission; the journal retains its job ID for polling and cancellation.
The runtime never claims transactionality across arbitrary external services.

Parallel calls share model/tool semaphores and budget reservations. Calls whose
usage was not returned retain their reserved token allowance. Token usage and
unreported calls are observable; currency cost remains unknown without billing data.
Graceful shutdown checkpoints work, while hard interruption waits for lease expiry.
Synchronous Python tool threads may finish after timeout: use idempotency or an
external-job adapter for effects that need recovery.

## Work over a dynamic list

AgentSpec 0.3 adds `map` for task lists produced at runtime. Give it an `items`
binding and a body graph. Each body receives `input.item`, `input.index` and
`input.context` (the map node's resolved `inputs`). Results retain input order in
`nodes.<map>.output.items`.

```python
builder.map(
    "research",
    items={"ref": "nodes.plan.output.tasks"},
    inputs={"question": {"ref": "input.question"}},
    body=research_graph,
    max_items=6,
    output_schema={"type": "object"},
)
```

`Builder.map` selects spec version 0.3. Studio offers the same node, including its
body in the JSON inspector. `max_items` defaults to 32 (maximum 256); an empty list
returns an empty result list. Non-list inputs and oversized lists fail before body
execution. Per-item paths such as `graph/research/item-0/research` keep checkpoints,
approvals and external jobs distinct. Completed items are reused when a run resumes.

Each map bounds in-flight body graphs by `max_parallel_nodes`. All nested work also
shares the run's model/tool semaphores, token allowance and step budget. Set
`max_parallel_tools` when parallel tools are desired. Use the [research team](../examples/research-team/)
and [video studio](../examples/video-studio/) as templates.
