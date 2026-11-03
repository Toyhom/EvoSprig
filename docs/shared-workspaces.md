# Shared documents and wake-ups

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
