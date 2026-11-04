import concurrent.futures
import json
import socket
import sys

import pytest
import yaml

from evosprig.local_services import ServiceConfig, ServiceManager, prepare_services


@pytest.fixture
def service(tmp_path):
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    source = tmp_path / "model.py"
    source.write_text('''from http.server import HTTPServer,BaseHTTPRequestHandler
import json
class Handler(BaseHTTPRequestHandler):
    loads=0
    def log_message(self,*args): pass
    def do_GET(self):
        self.send_response(200);self.end_headers()
        self.wfile.write(json.dumps({"loaded":self.loads>0,"loads":self.loads}).encode())
    def do_POST(self):
        if not self.headers.get("Idempotency-Key"):
            self.send_response(422);self.end_headers();return
        Handler.loads+=1
        self.send_response(200);self.end_headers();self.wfile.write(b'{}')
HTTPServer(("127.0.0.1",'''+str(port)+'''),Handler).serve_forever()
''')
    profile = tmp_path / "deployment.yaml"
    profile.write_text(yaml.safe_dump({"models": {}, "services": {"model": {
        "command": [sys.executable, str(source)], "health_url": f"http://127.0.0.1:{port}/health",
        "warmup_url": f"http://127.0.0.1:{port}/warmup", "ready": {"loaded": True},
        "timeout_seconds": 10, "poll_seconds": .05}}}))
    manager = ServiceManager(profile)
    try:
        yield profile, manager
    finally:
        manager.stop("model")


def test_concurrent_preload_reuses_one_process_across_managers(service):
    profile, manager = service
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        values = list(pool.map(lambda _: prepare_services(profile)[0], range(3)))
    assert len({row["pid"] for row in values}) == 1
    assert all(row["ready"] and row["health"]["loads"] == 1 for row in values)
    assert ServiceManager(profile).status("model")["ready"]
    assert manager.stop("model")["stopped"]
    assert not manager.status("model")["reachable"]


def test_external_service_is_not_stopped(service, tmp_path):
    profile, manager = service
    manager.ensure("model")
    attached = ServiceManager(profile, tmp_path / "other-state")
    assert attached.ensure("model")["ready"]
    assert not attached.stop("model")["stopped"]
    assert manager.status("model")["health"]["loads"] == 1


def test_changed_command_and_recycled_pid_are_not_owned(service):
    profile, manager = service
    manager.ensure("model")
    raw = yaml.safe_load(profile.read_text())
    raw["services"]["model"]["command"].append("changed")
    profile.write_text(yaml.safe_dump(raw))
    with pytest.raises(ValueError, match="configuration changed"):
        ServiceManager(profile).ensure("model")
    path = manager.root / "model.json"
    state = json.loads(path.read_text())
    original = path.read_text()
    state["birth"] = "recycled"
    path.write_text(json.dumps(state))
    try:
        assert not manager.stop("model")["stopped"]
        assert manager.status("model")["reachable"]
    finally:
        path.write_text(original)


def test_service_config_rejects_remote_and_credential_urls():
    for url in ["https://host/health", "http://" + "user:password@localhost/health"]:
        with pytest.raises(ValueError):
            ServiceConfig(health_url=url)
