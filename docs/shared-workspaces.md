# Shared documents, peer messages and wake-ups

Agents and people can edit the same project documents. EvoSprig stores content, revision history and write receipts in `documents.sqlite`, scoped by tenant, user and project.

```python
from evosprig.core.journal import Scope
from evosprig.plugins.workspace_tools import WorkspaceStore

store = WorkspaceStore(".evosprig/documents.sqlite")
scope = Scope("office")
draft = store.read(scope, "deliverables/plan.md")
saved = store.write(scope, "deliverables/plan.md", "# Launch plan\n...",
                    draft["revision"], idempotency_key="plan-edit-1")
```

A new document starts at revision 0. Every successful edit creates a revision. A stale edit raises `ToolRejectedError("revision_conflict", ...)`; reread and merge before retrying. Repeating the same operation ID and content returns the original result.

## Agent tools

| Plugin | Arguments | Result |
| --- | --- | --- |
| `workspace.list` | `prefix` | Document names and revisions |
| `workspace.read` | `name` | Latest content and revision |
| `workspace.write` | `name`, `content`, `expected_revision` | Name, revision and timestamp |
| `workspace.history` | `name` | Revision metadata |
| `workspace.wait` | `seconds`, `message` | A durable external job; resumes when due |

These tools are available through `make_tools`. Declare the ones an agent needs with `Builder.tool`. Set `tool_errors="feedback"` so an agent can respond to a revision conflict. Enable writes for document edits and scheduled wake-ups.

`workspace.wait` persists the deadline before returning its job ID. Studio's worker resumes the run when the job is ready; CLI users resume the same run explicitly. Restarting the worker preserves the original deadline. Canceling the run cancels its outstanding wake-up. Maximum delay: seven days.

## Browser and service clients

All routes use the current authenticated project scope:

| Route under `/api/projects/{id}/workspace` | Operation |
| --- | --- |
| `GET /documents?prefix=` | List documents |
| `GET /document?name=&revision=` | Read latest or historical content |
| `PUT /document` | Save with `name`, `content`, `expected_revision`, `operation_id`; optional `media_type` |
| `GET /history?name=` | Revision list |
| `GET /download?name=` | Download the document |

A conflicting browser save returns HTTP 409 and preserves its draft. The [Cowork workbench](../apps/cowork/) uses these routes to display, edit and download team deliverables.

## Peer-to-peer messages

Any agent with a mailbox can message another agent in the same run. Give fixed roles
names such as `analyst` and `writer`, or use `mailbox={"ref":"input.item.role"}` in a map body.
The runtime supplies the sender identity; model arguments contain only the recipient and content.

```python
builder.tool("send", "messages.send")
builder.tool("inbox", "messages.receive")
builder.tool("wait_for_reply", "messages.wait")
builder.node("analyst", "agent", model="main", mailbox="analyst",
             tools=["send", "inbox", "wait_for_reply"],
             instructions="Share findings with writer; answer peer questions.",
             inputs={"request": {"ref": "input.request"}},
             output_schema={"type": "object"})
```

| Plugin | Arguments | Behavior |
| --- | --- | --- |
| `messages.send` | `recipient`, `content`, optional `reply_to` | Idempotent delivery; returns ID and sequence |
| `messages.receive` | Optional `after`, `limit` | Read this agent's unacknowledged messages |
| `messages.ack` | `ids` | Mark handled messages; accepts only this inbox's IDs |
| `messages.wait` | Optional `after`, `timeout_seconds` | Persist a wait, resume on arrival or timeout |

Agents with `messages.receive` get new arrivals between model/tool turns. Explicit reads
and waits can retrieve replies during a task. A completed specialist reads queued messages
when the workflow schedules its next wave; keep its mailbox name stable across waves.
Sending and waiting require the same durable storage and write permissions as shared documents.
Messages are scoped to tenant, user, project and run. Message IDs, cursors, original wait
deadlines and acknowledgements survive worker restarts. Replies link to a message actually
received by the replying agent.

With `tool_errors="feedback"`, an invalid reply or acknowledgement returns a correction
to the agent. Acknowledgement IDs come from received messages; the receipt from sending
a message belongs to the recipient's inbox.

[CoworkOS (EvoSprig)](../examples/cowork/) combines direct peer messages with shared documents,
lead-agent review and targeted follow-up waves.
