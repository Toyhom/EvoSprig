# Durable runtime

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
