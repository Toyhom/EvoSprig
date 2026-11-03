# Start an agent from an event

Use `Runtime.create_event_run` to turn an incoming event into one durable application run. Repeated deliveries return the same run ID. The first accepted version, inputs and deployment bindings stay attached to that run across restarts and application updates.

```python
from evosprig.core.triggers import Trigger

# Verify the source signature and actor policy in your receiving endpoint.
trigger = Trigger(
    source="github:owner/repository",
    event_id=delivery_id,
    actor=payload["sender"]["login"],
    thread=f"issue-{payload['issue']['number']}",
    payload=payload,
)
run_id = runtime.create_event_run(
    version,
    {"request": payload["issue"]["body"]},
    trigger,
    scope=scope,
)
```

Use a `SQLiteJournal` for durable intake. The event and execution are stored together before this method returns. A worker can discover the queued execution with `journal.due()` and continue it with `runtime.resume(run_id)`. A receiver can acknowledge the source immediately after creating the run.

The source name identifies an account or repository within a project scope. Keep it stable, and use the source's delivery ID for `event_id`. Put stable event content in `payload`; transport retry counters and receipt timestamps belong in receiver logs. Reusing an event ID with different content raises `ValueError`.

The trigger is available in the run's `metadata.context.trigger`. The `thread` field records conversation membership for application routing. Follow-up messages can use [agent mailboxes](shared-workspaces.md), while [human nodes](studio.md) collect decisions during execution.
