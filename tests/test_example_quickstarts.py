import json
import os
import runpy
import sqlite3
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from evosprig.config import make_tools
from evosprig.core.journal import Scope
from evosprig.core.spec import load_spec
from evosprig.core.version import compile_agent
from evosprig.exporters.importer import inspect_archive

ROOT = Path(__file__).resolve().parents[1]
HELPER = runpy.run_path(str(ROOT / "examples/quickstart.py"))
CATALOG = json.loads((ROOT / "examples/quickstarts.json").read_text())


@pytest.mark.parametrize("name", CATALOG)
def test_example_setup_and_export_import_without_runtime_data(name, tmp_path):
    state = tmp_path / "state"
    HELPER["configure"](name, state)
    (state / "private-note.txt").write_text("private workspace content")
    destination = tmp_path / "application.zip"
    HELPER["package"](name, state, destination)
    version, report = inspect_archive(destination.read_bytes())
    root = ROOT / "examples" / name
    original = compile_agent(load_spec(root / CATALOG[name].get("spec", "agent.yaml")), root)
    assert version.version_id == original.version_id
    assert report["compatible"]
    import zipfile
    with zipfile.ZipFile(destination) as archive:
        assert "private-note.txt" not in archive.namelist()
        assert "deployment.yaml" not in archive.namelist()
    with pytest.raises(FileExistsError):
        HELPER["package"](name, state, destination)


def test_setup_preserves_edits_seeds_database_and_rejects_reconfiguration(tmp_path):
    HELPER["configure"]("data-analyst", tmp_path)
    profile = tmp_path / "deployment.yaml"
    edited = profile.read_text().replace("deepseek-flash", "chosen-model")
    profile.write_text(edited)
    sample = tmp_path / "input.json"
    sample.write_text('{"question":"My own question"}')
    with sqlite3.connect(tmp_path / "shop.sqlite") as db:
        count = db.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
    HELPER["configure"]("data-analyst", tmp_path)
    assert profile.read_text() == edited
    assert json.loads(sample.read_text())["question"] == "My own question"
    with sqlite3.connect(tmp_path / "shop.sqlite") as db:
        assert db.execute("SELECT COUNT(*) FROM orders").fetchone()[0] == count
    with pytest.raises(ValueError, match="Configuration exists"):
        HELPER["configure"]("data-analyst", tmp_path, model="other", base_url="https://model.example/v1")


def test_launcher_uses_configured_api_and_native_runtime(tmp_path, monkeypatch):
    requests = []

    class Endpoint(BaseHTTPRequestHandler):
        def do_POST(self):
            data = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            requests.append((self.path, self.headers["Authorization"], data))
            result = json.dumps({"choices": [{"message": {"role": "assistant", "content": "A working team"},
                                               "finish_reason": "stop"}],
                                 "usage": {"prompt_tokens": 12, "completion_tokens": 4}}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(result)))
            self.end_headers()
            self.wfile.write(result)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Endpoint)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        HELPER["configure"]("hello", tmp_path, base_url=f"http://127.0.0.1:{server.server_port}/v1",
                            model="configured-model", key_env="QUICKSTART_TEST_KEY")
        monkeypatch.setenv("QUICKSTART_TEST_KEY", "test-credential")
        argv = HELPER["command"]("hello", "run", tmp_path)
        result = subprocess.run(argv, capture_output=True, text=True, check=True, timeout=30)
        assert json.loads(result.stdout)["status"] == "succeeded"
        assert requests[0][0] == "/v1/chat/completions"
        assert requests[0][1] == "Bearer test-credential"
        assert requests[0][2]["model"] == "configured-model"
        assert (tmp_path / "runs.sqlite").exists()
        assert "test-credential" not in (tmp_path / "deployment.yaml").read_text()
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


async def test_document_setup_is_searchable_in_the_same_workspace(tmp_path):
    HELPER["configure"]("document-chat", tmp_path)
    tools = make_tools(tmp_path, Scope("document-chat"))
    result = await tools.resolve("documents.search").invoke({"query": "learning budget"})
    assert "learning" in json.dumps(result).lower()


def test_store_auth_refund_policy_and_restart_receipts(tmp_path):
    factory = runpy.run_path(str(ROOT / "examples/customer-support/store.py"))["create_app"]
    database = tmp_path / "orders.sqlite"
    headers = {"Authorization": "Bearer store-token", "Idempotency-Key": "refund-1"}
    data = {"order_id": "ORDER-1001", "amount": 49.0}
    with TestClient(factory(database, "store-token")) as client:
        assert client.get("/lookup", params={"order_id": "ORDER-1001"}).status_code == 401
        assert client.post("/refund", json={**data, "amount": 50}, headers=headers).status_code == 409
        first = client.post("/refund", json=data, headers=headers)
        assert first.status_code == 200
        assert client.post("/refund", json=data, headers=headers).json() == first.json()
        assert client.post("/refund", json={**data, "amount": 48}, headers=headers).status_code == 409
        assert client.post("/refund", json=data, headers={**headers, "Idempotency-Key": "another"}).status_code == 409
    with TestClient(factory(database, "store-token")) as client:
        assert client.post("/refund", json=data, headers=headers).json() == first.json()
        assert client.get("/lookup", params={"order_id": "ORDER-1001"}, headers=headers).json()["refunded"]


def test_repository_starter_has_committed_task_and_failing_checks(tmp_path):
    create = runpy.run_path(str(ROOT / "examples/repository-agent/create_sample.py"))["create"]
    checkout = tmp_path / "repository"
    create(checkout)
    result = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
                            cwd=checkout, capture_output=True, text=True)
    assert result.returncode == 1 and "Ran 4 tests" in result.stderr
    assert "FAILED (failures=1, errors=1)" in result.stderr
    status = subprocess.check_output(["git", "-c", "safe.directory=" + str(checkout.resolve()),
                                      "-C", str(checkout), "status", "--porcelain"], text=True)
    assert status == ""


def test_industry_starter_replays_decisions_instead_of_trusting_claims(tmp_path):
    # Use a separate interpreter to keep a user's IndustryBench import independent.
    source = ROOT / "examples/industry-assistant/starter"
    code = '''
from industrybench.registry import CASES
from industrybench.session import Session
from industrybench.evaluation import evaluate
for case in CASES:
    s = Session(case['id'])
    expected = ('manual_review' if case['conflicting_records'] else
                'request_documents' if not case['documents_complete'] else
                'approve' if case['resident'] and case['income'] <= 25000 else 'deny')
    calls = [dict(tool='application.read', arguments={}, idempotency_key='1'),
             dict(tool='application.decide', arguments={'decision':expected, 'reason':'Applied policy'}, idempotency_key='2'),
             dict(tool='application.read', arguments={}, idempotency_key='3')]
    payload = dict(case_id=case['id'], calls=calls, final_state={'decision':'fabricated'})
    assert evaluate([payload], 'government', [case['id']])['summary']['task_success_rate'] == 1
    payload['calls'] = calls[:2]
    assert evaluate([payload], 'government', [case['id']])['summary']['task_success_rate'] == 0
    payload['calls'] = []
    assert evaluate([payload], 'government', [case['id']])['summary']['task_success_rate'] == 0
'''
    subprocess.run([sys.executable, "-c", code], env={**os.environ, "PYTHONPATH": str(source)}, check=True)
    subprocess.run([sys.executable, "-m", "evosprig.cli", "industry", "prepare", "--limit", "8",
                    "--out", str(tmp_path / "agent")],
                   env={**os.environ, "INDUSTRYBENCH_ROOT": str(source)}, check=True,
                   capture_output=True, text=True)
    assert (tmp_path / "agent/suite.yaml").is_file()
