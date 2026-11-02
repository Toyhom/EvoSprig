import math
from dataclasses import replace

import pytest

from evosprig.core.journal import Scope
from evosprig.core.memory import MemoryConflict, MemoryScope
from evosprig.plugins.semantic_memory import HybridMemory
from evosprig.plugins.sqlite_memory import SQLiteMemory
from evosprig.plugins.structured_memory import StructuredMemory


def memory_scope(tmp_path):
    return SQLiteMemory(tmp_path / "memory.sqlite"), MemoryScope(Scope("assistant", "alice"))


def test_bm25_rare_terms_and_type_time_filter(tmp_path):
    memory, scope = memory_scope(tmp_path)
    memory.write(scope, "project roadmap " * 30, source="notes")
    rare = memory.write(
        scope, "project quasar launch", source="user", valid_from=100, valid_until=200
    )
    memory.write(scope, "project roadmap", source="user", content_type="context")
    hits = memory.search(scope, "project quasar", at=150, content_type="fact")
    assert hits[0]["id"] == rare["id"]
    assert all(x["content_type"] == "fact" for x in hits)
    assert rare["id"] not in {r["id"] for r in memory.search(scope, "quasar", at=250)}


class Embedder:
    model_id = "fixture-semantic"

    def __init__(self):
        self.texts = []

    def embed(self, texts):
        self.texts.extend(texts)
        return [[1, 0] if any(t in text for t in ["bicycle", "bike"]) else [0, 1] for text in texts]


def test_semantic_synonyms_scope_cache_updates_and_deletion(tmp_path):
    memory, scope = memory_scope(tmp_path)
    bike = memory.write(scope, "commutes by bicycle", source="user")
    memory.write(scope, "likes coffee", source="user")
    foreign = replace(scope, identity=Scope("assistant", "bob"))
    memory.write(foreign, "secret bicycle record", source="user")
    embedder = Embedder()
    hybrid = HybridMemory(memory, embedder, cache_size=1)
    assert memory.search(scope, "bike") == []
    assert hybrid.search(scope, "bike")[0]["id"] == bike["id"]
    assert "secret bicycle record" not in embedder.texts
    memory.update(scope, bike["id"], "commutes by train", revision=1)
    assert hybrid.search(scope, "train")[0]["content"] == "commutes by train"
    memory.delete(scope, bike["id"])
    assert bike["id"] not in {r["id"] for r in hybrid.search(scope, "bike")}
    assert len(hybrid.cache) <= 1


@pytest.mark.parametrize("bad", [[[0, 0]], [[math.nan, 1]], [[1], [1]], []])
def test_invalid_embedding_receipt_is_rejected(tmp_path, bad):
    memory, scope = memory_scope(tmp_path)
    memory.write(scope, "data", source="user")

    class Bad:
        model_id = "bad"

        def embed(self, texts):
            return bad

    with pytest.raises(ValueError):
        HybridMemory(memory, Bad()).search(scope, "data")


def test_context_cas_budget_and_tombstones(tmp_path):
    memory, scope = memory_scope(tmp_path)
    blocks = StructuredMemory(memory)
    record = blocks.set_context(scope, "profile", "short answers", source="user", max_chars=20)
    with pytest.raises(MemoryConflict):
        blocks.set_context(scope, "profile", "different", source="user")
    updated = blocks.set_context(scope, "profile", "English answers", source="user", revision=1)
    assert updated["revision"] == 2
    assert blocks.context(scope, max_chars=5)["omitted"] == 1
    backup = memory.export(scope)
    memory.delete(scope, record["id"])
    memory.restore(scope, backup)
    assert blocks.context(scope)["blocks"] == []
    with pytest.raises(ValueError):
        blocks.set_context(scope, "profile", "too long", source="user", max_chars=3)


def test_temporal_replacement_traversal_and_isolation(tmp_path):
    memory, scope = memory_scope(tmp_path)
    graph = StructuredMemory(memory)
    first = graph.set_relation(scope, "Alice", "works_on", "Orion", source="user", valid_from=100)
    second = graph.set_relation(scope, "Alice", "works_on", "Atlas", source="user", valid_from=200)
    assert graph.relations(scope, "Alice", at=150)[0]["id"] == first["id"]
    assert graph.relations(scope, "Alice", at=200)[0]["id"] == second["id"]
    graph.set_relation(scope, "Atlas", "uses", "Python", source="docs", valid_from=200)
    assert len(graph.relations(scope, "Alice", at=250, hops=2)) == 2
    with pytest.raises(MemoryConflict):
        graph.set_relation(scope, "Alice", "works_on", "past", source="user", valid_from=150)
    assert graph.relations(replace(scope, namespace="other"), "Alice") == []
    memory.namespace_delete(scope)
    assert graph.relations(scope, "Alice", at=150) == []


def test_embedding_http_adapter_reorders_and_sanitizes_errors(monkeypatch):
    import httpx

    from evosprig.core.protocols import ProviderError
    from evosprig.plugins.embeddings import EmbeddingConnection, OpenAIEmbeddings

    monkeypatch.setenv("EMBEDDING_TEST_KEY", "fixture-token")
    config = EmbeddingConnection(
        base_url="https://models.example.com/v1", model="test", api_key_env="EMBEDDING_TEST_KEY"
    )

    def handler(request):
        assert request.url.path == "/v1/embeddings"
        return httpx.Response(
            200,
            json={"data": [{"index": 1, "embedding": [0, 2]}, {"index": 0, "embedding": [3, 0]}]},
        )

    assert OpenAIEmbeddings(config, transport=httpx.MockTransport(handler)).embed(
        ["one", "two"]
    ) == [[1, 0], [0, 1]]
    adapter = OpenAIEmbeddings(
        config,
        transport=httpx.MockTransport(
            lambda r: httpx.Response(401, text="private upstream response")
        ),
    )
    with pytest.raises(ProviderError) as error:
        adapter.embed(["one"])
    assert "private upstream response" not in str(error.value)
    assert "fixture-token" not in str(error.value)
