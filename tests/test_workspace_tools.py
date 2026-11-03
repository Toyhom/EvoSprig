from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from evosprig.core.journal import Scope
from evosprig.core.protocols import ToolRejectedError
from evosprig.plugins.workspace_tools import WorkspaceStore
from evosprig.server.app import create_app


def test_shared_document_conflict_retry_history_and_scope(tmp_path):
    store = WorkspaceStore(tmp_path / "docs.sqlite")
    scope = Scope("office")
    first = store.write(scope, "team/plan.md", "v1", 0, idempotency_key="create")

    def edit(i):
        try:
            return store.write(scope, "team/plan.md", str(i), 1, idempotency_key=f"edit-{i}")
        except ToolRejectedError:
            return None

    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(edit, [1, 2]))
    assert sum(r is not None for r in results) == 1
    assert store.write(scope, "team/plan.md", "v1", 0, idempotency_key="create") == first
    assert store.read(scope, "team/plan.md", 1)["content"] == "v1"
    assert len(store.history(scope, "team/plan.md")["revisions"]) == 2
    assert store.read(Scope("office", "other"), "team/plan.md")["revision"] == 0
    with pytest.raises(ValueError):
        store.write(scope, "team/plan.md", "different", 0, idempotency_key="create")
    with pytest.raises(ValueError):
        store.read(scope, "../outside.md")


def test_wake_survives_restart_and_cancel(tmp_path, monkeypatch):
    now = [1000.0]
    monkeypatch.setattr("evosprig.plugins.workspace_tools.time.time", lambda: now[0])
    path = tmp_path / "documents.sqlite"
    scope = Scope("office")
    store = WorkspaceStore(path)
    job = store.wait(scope, 60, "Review edits", idempotency_key="wake")
    assert store.poll(scope, job).status == "pending"
    now[0] += 30
    store = WorkspaceStore(path)
    assert store.wait(scope, 60, "Review edits", idempotency_key="wake") == job
    with pytest.raises(ValueError, match="different wake-up"):
        store.wait(scope, 600, "Review edits", idempotency_key="wake")
    with pytest.raises(ValueError, match="different wake-up"):
        store.wait(scope, 60, "Changed intent", idempotency_key="wake")
    now[0] += 31
    assert store.poll(scope, job).output["message"] == "Review edits"
    store.cancel(scope, job)
    assert store.poll(scope, job).status == "canceled"


def test_people_and_agents_share_document_revisions(tmp_path):
    from test_evolution_methods import version

    base = version()
    with TestClient(create_app(tmp_path), base_url="http://127.0.0.1") as client:
        created = client.post(
            "/api/projects",
            json={"spec": base.spec.model_dump(mode="json"), "resources": base.resources},
        )
        assert created.status_code == 201
        url = "/api/projects/eval-agent/workspace/document"
        body = {
            "name": "note.md",
            "content": "human edit",
            "expected_revision": 0,
            "operation_id": "web-1",
        }
        assert client.put(url, json=body).status_code == 200
        store = WorkspaceStore(tmp_path / "documents.sqlite")
        assert store.read(Scope("eval-agent"), "note.md")["content"] == "human edit"
        store.write(Scope("eval-agent"), "note.md", "agent edit", 1, idempotency_key="agent-1")
        body.update(content="stale browser edit", operation_id="web-2")
        assert client.put(url, json=body).status_code == 409
        assert client.get(url, params={"name": "note.md"}).json()["content"] == "agent edit"
        assert (
            client.get(
                "/api/projects/eval-agent/workspace/download", params={"name": "note.md"}
            ).text
            == "agent edit"
        )
