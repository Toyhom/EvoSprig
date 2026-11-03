"""Create one durable execution for an authenticated source event."""

from __future__ import annotations

import json

from pydantic import Field

from .journal import Scope
from .spec import Contract, canonical_json, digest


class Trigger(Contract):
    source: str = Field(min_length=1, max_length=128)
    event_id: str = Field(min_length=1, max_length=256)
    payload: dict
    thread: str | None = Field(default=None, max_length=512)
    actor: str | None = Field(default=None, max_length=256)


def create_event_run(runtime, version, inputs, trigger, *, scope=None):
    """Atomically persist the source event and its run through the run journal.

    Source authentication and admission belong to the calling application.
    Re-delivery preserves the first accepted version, input and bindings, even
    after a deployment update. Changed content under the same event ID fails.
    """
    trigger = Trigger.model_validate(trigger)
    envelope = json.loads(canonical_json(trigger.model_dump(mode="json")))
    scope = scope or Scope(version.spec.id)
    if scope.project != version.spec.id:
        raise ValueError("trigger scope must match the agent project")
    run_id = digest(["source-event-v1", scope.key, trigger.source, trigger.event_id])

    def existing():
        try:
            record = runtime.journal.get(run_id, scope)
        except KeyError:
            return None
        if record["metadata"].get("context", {}).get("trigger") != envelope:
            raise ValueError("source event ID already belongs to different content")
        return run_id

    found = existing()
    if found:
        return found
    try:
        return runtime.create_run(version, inputs, run_id=run_id, scope=scope,
                                  context={"trigger": envelope})
    except ValueError:
        # Another receiver may have committed this event after our first read.
        found = existing()
        if found:
            return found
        raise
