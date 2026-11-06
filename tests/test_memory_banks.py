import io
import json
import os
import subprocess
import sys
import zipfile
from dataclasses import replace

import httpx
import pytest
import yaml
from jsonschema import ValidationError

from evosprig.config import make_models, make_tools
from evosprig.core.journal import Scope
from evosprig.core.memory import MemoryScope
from evosprig.core.runtime import Runtime
from evosprig.core.version import compile_snapshot
from evosprig.exporters.importer import inspect_archive
from evosprig.exporters.python import export_python
from evosprig.plugins.embeddings import OpenAIEmbeddings
from evosprig.plugins.memory_banks import MemoryBanks, MemoryBanksConfig
from evosprig.plugins.mock import MockProvider
from evosprig.plugins.sqlite_memory import SQLiteMemory
from evosprig.sdk import Builder
from evosprig.server.app import create_app
from evosprig.server.auth import Principal


def agent_spec():
    b = Builder("memory-agent", {"type": "object"}, {"type": "object"}, spec_version="0.3")
    b.default_model("main", requires=["text", "tool_calling"])
    b.memory_tool("recall", bank="writer")
    b.node("writer", "agent", instructions="Use relevant preferences.", inputs={"query": {"ref": "input.query"}},
           output_schema={"type": "object"}, tools=["recall"],
           harness={"memory": {"tool": "recall", "query_input": "query", "limit": 3, "max_chars": 4000}})
    b.output(answer={"ref": "nodes.writer.output.text"})
    return b.build_spec()


@pytest.mark.parametrize("mode", ["semantic", "hybrid"])
async def test_configured_vector_recall_cache_invalidation_and_bank_isolation(tmp_path, monkeypatch, mode):
    embedded = []

    def embed(self, texts):
        embedded.extend(texts)
        return [[1., 0.] if any(word in text for word in ("bicycle", "bike")) else [0., 1.] for text in texts]

    monkeypatch.setattr(OpenAIEmbeddings, "embed", embed)
    identity = Scope("memory-agent", "alice", "team")
    store = SQLiteMemory(tmp_path / "memory.sqlite")
    banks = MemoryBanks(store)
    banks.configure(identity, "writer", {"retrieval": mode, "min_similarity": 0.5,
                                         "embeddings": {"base_url": "http://127.0.0.1:8000/v1", "model": "embedding", "api_key_env": "TEST_EMBEDDING_KEY"}})
    banks.configure(identity, "reviewer", {})
    selected = banks.scope(identity, "writer")
    record = store.write(selected, "commutes by bicycle", source="user")
    store.write(selected, "likes tea", source="user")
    for other in [banks.scope(identity, "reviewer"), MemoryScope(identity, namespace="documents"),
                  replace(selected, identity=Scope("memory-agent", "bob", "team"))]:
        store.write(other, "secret bicycle information", source="other")
    tools = make_tools(tmp_path, identity)
    assert (await tools.resolve("memory.writer.search").invoke({"query": "bike"}))["records"][0]["id"] == record["id"]
    assert (await tools.resolve("memory.search").invoke({"query": "bike"}))["records"] == []
    assert "secret bicycle information" not in embedded
    assert store.search(selected, "bike") == []
    # Recreating the registry reuses disk vectors but rechecks source visibility.
    embedded.clear()
    tools = make_tools(tmp_path, identity)
    hits = (await tools.resolve("memory.writer.search").invoke({"query": "bike"}))["records"]
    assert [hit["id"] for hit in hits] == [record["id"]]
    assert embedded == ["bike"]
    store.update(selected, record["id"], "travels by train", revision=1)
    assert (await tools.resolve("memory.writer.search").invoke({"query": "bike"}))["records"] == []
    store.delete(selected, record["id"])
    assert all(r["id"] != record["id"] for r in (await tools.resolve("memory.writer.search").invoke({"query": "train"}))["records"])
    with pytest.raises(ValidationError, match="Additional properties"):
        await tools.resolve("memory.writer.search").invoke({"query": "bike", "bank": "reviewer"})


async def test_bank_write_permissions_idempotency_and_automatic_recall(tmp_path):
    identity = Scope("memory-agent")
    store = SQLiteMemory(tmp_path / "memory.sqlite")
    banks = MemoryBanks(store)
    banks.configure(identity, "writer", {})
    registry = make_tools(tmp_path, identity)
    write = registry.resolve("memory.writer.write")
    arguments = {"content": "Reply in concise Chinese", "source": "user:explicit"}
    first = await write.invoke(arguments, operation_id="save-preference")
    assert first == await write.invoke(arguments, operation_id="save-preference")
    assert store.export(MemoryScope(identity)) == []
    provider = MockProvider()
    result = await Runtime({"main": provider}, registry).run(compile_snapshot(agent_spec(), {}), {"query": "Chinese"})
    assert result.status == "succeeded"
    assert "Reply in concise Chinese" in provider.requests[0].messages[-1]["content"]
    banks.configure(identity, "writer", {"agent_writes": False})
    read_only = make_tools(tmp_path, identity)
    assert (await read_only.resolve("memory.writer.search").invoke({"query": "Chinese"}))["records"]
    with pytest.raises(ValueError, match="not installed"):
        read_only.resolve("memory.writer.write")


async def test_studio_banks_config_search_and_context_are_scoped(tmp_path):
    app = create_app(tmp_path, principals={"alice": Principal("alice", "team"), "bob": Principal("bob", "team")})
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://localhost") as client:
        for token in ["alice", "bob"]:
            client.headers["authorization"] = "Bearer " + token
            assert (await client.post("/api/projects", json={"spec": agent_spec().model_dump()})).status_code == 201
        client.headers["authorization"] = "Bearer alice"
        base = "/api/projects/memory-agent/memory"
        assert (await client.put(base + "/banks/writer", json={})).status_code == 200
        assert (await client.put(base + "/banks/invalid.name", json={})).status_code == 422
        assert (await client.put(base + "/banks/writer", json={"retrieval": "semantic"})).status_code == 422
        record = (await client.post(base + "?bank=writer", json={"content": "Prefer short replies", "source": "user"})).json()
        assert (await client.get(base + "?bank=writer&query=short")).json()[0]["id"] == record["id"]
        assert (await client.get(base)).json() == []
        assert (await client.get(base + "/" + record["id"])).status_code == 404
        context = "/api/projects/memory-agent/context"
        assert (await client.put(context + "/progress?bank=writer", json={"content": "Draft ready", "source": "agent"})).status_code == 200
        assert (await client.get(context)).json()["blocks"] == []
        assert (await client.get(context + "?bank=writer")).json()["blocks"][0]["content"] == "Draft ready"
        archive = await client.post("/api/projects/memory-agent/export?target=http")
        assert archive.status_code == 200
        _, report = inspect_archive(archive.content)
        assert "writer" in report["memory"]["banks"]
        client.headers["authorization"] = "Bearer bob"
        assert (await client.get(base + "/banks")).json()["banks"].keys() == {"default"}
        assert (await client.get(base + "?bank=writer")).status_code == 404
        assert (await client.put(base + "/banks/writer", json={})).status_code == 200
        assert (await client.get(base + "?bank=writer")).json() == []


def test_named_memory_export_runs_with_bundled_runtime_and_roundtrips(tmp_path):
    root = tmp_path / "export"
    config = {"banks": {"writer": {"agent_writes": False}, "unrelated": {}}}
    version = compile_snapshot(agent_spec(), {})
    export_python(version, root, memory_config=config, target="http")
    exported = json.loads((root / "memory-config.json").read_text())
    assert exported["banks"].keys() == {"writer"}
    workspace = tmp_path / "state"
    store = SQLiteMemory(workspace / "memory.sqlite")
    banks = MemoryBanks(store, exported)
    store.write(banks.scope(Scope(version.spec.id), "writer"), "Prefers concise Chinese", source="user")
    environment = {**os.environ, "PYTHONPATH": str(root / "src")}
    result = subprocess.run([sys.executable, "app.py", "--mock", "--workspace", str(workspace), "--input", '{"query":"Chinese"}'],
                            cwd=root, env=environment, capture_output=True, text=True, check=True)
    output = json.loads(result.stdout)
    assert output["status"] == "succeeded"
    assert "Prefers concise Chinese" in output["output"]["answer"]
    service_check = """
import time
from fastapi.testclient import TestClient
from evosprig.server.standalone import create_service
with TestClient(create_service('.', WORKSPACE, token='local-test', mock=True)) as client:
    headers = {'Authorization': 'Bearer local-test'}
    for query in ['Chinese', 'concise']:
        started = client.post('/runs', headers=headers, json={'input': {'query': query}})
        assert started.status_code == 202, started.text
        for _ in range(200):
            result = client.get('/runs/' + started.json()['run_id'], headers=headers).json()
            if result['status'] not in ('queued', 'running'):
                break
            time.sleep(.02)
        assert result['status'] == 'succeeded', result
        assert 'Prefers concise Chinese' in result['output']['answer'], result
""".replace('WORKSPACE', repr(str(workspace)))
    subprocess.run([sys.executable, '-c', service_check], cwd=root, env=environment,
                   capture_output=True, text=True, check=True)
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w") as bundle:
        for path in root.rglob("*"):
            if path.is_file() and '__pycache__' not in path.parts:
                bundle.write(path, path.relative_to(root))
    _, report = inspect_archive(archive.getvalue())
    assert report["memory"]["banks"]["writer"]["agent_writes"] is False
    with pytest.raises(ValueError, match="needs deployment configuration"):
        export_python(version, tmp_path / "missing")


def test_memory_deployment_profile_accepts_provider_and_validates_config(tmp_path):
    profile = tmp_path / "deployment.yaml"
    profile.write_text(yaml.safe_dump({"models": {"main": {"base_url": "http://localhost:8000/v1", "model": "test", "api_key_env": "TEST_KEY"}}, "memory": {"banks": {"writer": {}}}}))
    assert "main" in make_models(agent_spec(), profile)
    with pytest.raises(ValueError):
        MemoryBanksConfig.model_validate({"banks": {"../bad": {}}})
