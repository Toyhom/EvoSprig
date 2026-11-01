import asyncio
import io
import zipfile
from concurrent.futures import ThreadPoolExecutor

import httpx
import pytest

from evosprig.plugins.sqlite_projects import ProjectStore, RevisionConflict
from evosprig.server.app import create_app


@pytest.fixture
def app(tmp_path, spec, example_root):
    root = tmp_path / "projects" / spec.id / "prompts"
    root.mkdir(parents=True)
    (root / "assistant.md").write_bytes((example_root / "prompts/assistant.md").read_bytes())
    return create_app(tmp_path)


async def test_api_edit_run_events_export_and_conflict(app, spec):
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://localhost"
    ) as client:
        created = await client.post("/api/projects", json={"spec": spec.model_dump()})
        assert created.status_code == 201
        original = created.json()
        update = {
            "spec": spec.model_dump(),
            "layout": {"measure": {"x": 10, "y": 20}},
            "revision": 1,
        }
        saved = await client.put("/api/projects/hello", json=update)
        assert saved.status_code == 200
        assert saved.json()["spec_hash"] == original["spec_hash"]
        assert (await client.put("/api/projects/hello", json=update)).status_code == 409
        assert (
            await client.post(
                "/api/projects/hello/runs", json={"input": {"question": "hi"}, "revision": 1}
            )
        ).status_code == 409
        started = await client.post(
            "/api/projects/hello/runs", json={"input": {"question": "hi"}, "revision": 2}
        )
        assert started.status_code == 202
        run_id = started.json()["run_id"]
        for _ in range(100):
            result = (await client.get(f"/api/runs/{run_id}")).json()
            if result["status"] not in {"queued", "running"}:
                break
            await asyncio.sleep(0.01)
        assert result["status"] == "succeeded"
        events = await client.get(f"/api/runs/{run_id}/events", headers={"Last-Event-ID": "2"})
        assert "id: 1\n" not in events.text
        assert "id: 3\n" in events.text
        exported = await client.post("/api/projects/hello/export")
        assert exported.status_code == 200
        with zipfile.ZipFile(io.BytesIO(exported.content)) as archive:
            assert "app.py" in archive.namelist()
            assert not any(name.endswith("sqlite") for name in archive.namelist())


def test_atomic_revision_compare_and_swap(spec, tmp_path):
    store = ProjectStore(tmp_path / "db.sqlite")
    store.create(spec)

    def update(_):
        try:
            return store.update(spec.id, spec, {}, 1)["revision"]
        except RevisionConflict:
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(update, [1, 2]))
    assert sorted(map(str, results)) == ["2", "conflict"]


async def test_auth_origin_and_sanitized_validation(tmp_path):
    app = create_app(tmp_path, token="example-token")
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://localhost"
    ) as client:
        assert (await client.get("/api/health")).status_code == 401
        headers = {"Authorization": "Bearer example-token"}
        assert (await client.get("/api/health", headers=headers)).status_code == 200
        assert (
            await client.get("/api/health", headers={**headers, "Origin": "https://other.example"})
        ).status_code == 403
        response = await client.post(
            "/api/projects", headers=headers, json={"spec": {"private": "do-not-echo"}}
        )
        assert response.status_code == 422
        assert "do-not-echo" not in response.text
