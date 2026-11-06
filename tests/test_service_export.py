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


def test_exported_service_binds_models_later_and_switches_without_reexport(spec, example_root, tmp_path):
    import os
    import subprocess
    import sys
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from threading import Thread

    import yaml

    root = tmp_path / 'export'
    version = compile_agent(spec, example_root)
    export_python(version, root, target='http')
    env = {**os.environ, 'PYTHONPATH': str(root / 'src')}
    contract = subprocess.run([sys.executable, str(root / 'app.py'), '--model-contract'],
                              cwd=tmp_path, env=env, capture_output=True, text=True, check=True)
    assert json.loads(contract.stdout) == json.loads((root / 'model-contract.json').read_text())
    assert json.loads(contract.stdout)['bindings'] == {'main-model': {'aliases': ['main'], 'requires': ['text']}}
    assert not (root / '.evosprig').exists()
    lock = (root / 'agent.lock.json').read_bytes()
    profile = tmp_path / 'deployment.yaml'
    profile.write_text('models: {}\n')
    headers = {'Authorization': 'Bearer application-token'}
    requests = []

    class ModelServer(BaseHTTPRequestHandler):
        def do_POST(self):
            assert self.path == '/v1/chat/completions'
            assert self.headers.get('Authorization') is None
            body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            requests.append(body['model'])
            data = json.dumps({'model': body['model'], 'choices': [{'message': {
                'content': body['model']}}],
                'usage': {'prompt_tokens': 10, 'completion_tokens': 5}}).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *args):
            pass

    app = create_service(root, tmp_path / 'state', token='application-token', profile=profile)
    with TestClient(app) as client:
        assert client.get('/health').status_code == 200
        assert client.get('/model-contract').status_code == 401
        assert client.get('/model-contract', headers=headers).json() == json.loads(contract.stdout)
        assert client.post('/runs', headers=headers, json={'input': {'question': 'hello'}}).status_code == 503
        # The application is already running before either model endpoint exists.
        for model in ('local-a', 'server-b'):
            server = ThreadingHTTPServer(('127.0.0.1', 0), ModelServer)
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                profile.write_text(yaml.safe_dump({'models': {'main-model': {
                    'base_url': f'http://127.0.0.1:{server.server_port}/v1',
                    'model': model, 'api_key_env': None, 'capabilities': ['text']}}}))
                started = client.post('/runs', headers=headers, json={'input': {'question': 'hello'}})
                assert started.status_code == 202, started.text
                assert started.json()['agent_version'] == version.version_id
                for _ in range(100):
                    result = client.get('/runs/' + started.json()['run_id'], headers=headers).json()
                    if result['status'] in {'succeeded', 'failed'}:
                        break
                    time.sleep(0.02)
                assert result['status'] == 'succeeded', result
                assert result['output'] == {'answer': model}
            finally:
                server.shutdown()
                thread.join(timeout=2)
                server.server_close()
    assert requests == ['local-a', 'server-b']
    assert (root / 'agent.lock.json').read_bytes() == lock
