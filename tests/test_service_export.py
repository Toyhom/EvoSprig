import io
import json
import time
import zipfile

import pytest
from fastapi.testclient import TestClient

from evosprig.core.version import compile_agent
from evosprig.exporters.importer import inspect_archive
from evosprig.exporters.python import export_python
from evosprig.server.standalone import create_service


def archive_bytes(root):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(root.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(root))
    return buffer.getvalue()


def test_service_export_fixed_version_auth_and_durable_restart(spec, example_root, tmp_path):
    root = tmp_path / "export"
    version = compile_agent(spec, example_root)
    export_python(version, root, target="container")
    app = create_service(root, tmp_path / "state", token="test-token", mock=True)
    headers = {"Authorization": "Bearer test-token"}
    with TestClient(app) as client:
        assert client.get("/health").json()["agent_version"] == version.version_id
        assert client.post("/runs", json={"input": {}}).status_code == 401
        assert client.post("/runs", headers=headers, json={"input": {}}).status_code == 422
        response = client.post("/runs", headers=headers, json={"input": {"question": "hello"}})
        assert response.status_code == 202
        run_id = response.json()["run_id"]
        for _ in range(100):
            result = client.get("/runs/" + run_id, headers=headers).json()
            if result["status"] == "succeeded":
                break
            time.sleep(0.05)
        assert result["status"] == "succeeded"
        assert client.get("/runs/" + run_id + "/events", headers=headers).text.count("data:") > 1
    with TestClient(
        create_service(root, tmp_path / "state", token="test-token", mock=True)
    ) as client:
        assert client.get("/runs/" + run_id, headers=headers).json()["output"] == result["output"]
    assert "USER 10001:10001" in (root / "Dockerfile").read_text()
    assert "server/app.py" not in (root / "manifest.json").read_text()
    imported, report = inspect_archive(archive_bytes(root))
    assert imported.version_id == version.version_id
    assert report["compatible"]
    (root / "agent.yaml").write_text("tampered")
    with pytest.raises(ValueError, match="checksum"):
        inspect_archive(archive_bytes(root))


def test_import_rejects_paths_duplicates_oversize_and_does_not_execute(
    spec, example_root, tmp_path
):
    root = tmp_path / "export"
    export_python(compile_agent(spec, example_root), root)
    for name in ("../escape", "/absolute", "a/../escape", "a\\b"):
        buffer = io.BytesIO(archive_bytes(root))
        with zipfile.ZipFile(buffer, "a") as archive:
            archive.writestr(name, "bad")
        with pytest.raises(ValueError, match="unsafe"):
            inspect_archive(buffer.getvalue())
    import hashlib

    (root / "build_agent.py").write_text('raise RuntimeError("must never execute")')
    manifest = json.loads((root / "manifest.json").read_text())
    manifest["build_agent.py"] = hashlib.sha256((root / "build_agent.py").read_bytes()).hexdigest()
    (root / "manifest.json").write_text(json.dumps(manifest))
    assert inspect_archive(archive_bytes(root))[0].spec.id == spec.id


async def test_inspected_import_does_not_create_project_and_can_restore_spec(
    spec, example_root, tmp_path
):
    import httpx

    from evosprig.server.app import create_app

    root = tmp_path / "export"
    version = compile_agent(spec, example_root)
    export_python(version, root, target="http")
    app = create_app(tmp_path / "studio")
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://localhost"
    ) as client:
        response = await client.post(
            "/api/import/inspect",
            content=archive_bytes(root),
            headers={"content-type": "application/zip"},
        )
        assert response.status_code == 200
        assert (await client.get("/api/projects")).json() == []
        inspected = response.json()
        created = await client.post(
            "/api/projects", json={"spec": inspected["spec"], "resources": inspected["resources"]}
        )
        assert created.status_code == 201
        assert created.json()["spec_hash"] == version.spec.spec_hash
        exported = await client.post(f"/api/projects/{spec.id}/export?target=container")
        assert exported.status_code == 200
        assert inspect_archive(exported.content)[0].version_id == version.version_id
