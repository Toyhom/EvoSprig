import shutil
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

import pytest
from jsonschema import ValidationError

from evosprig.core.journal import Scope
from evosprig.core.memory import MemoryConflict, MemoryScope
from evosprig.plugins.builtin_tools import builtin_registry
from evosprig.plugins.documents import DocumentRetriever
from evosprig.plugins.memory_tools import register_memory_tools
from evosprig.plugins.sqlite_memory import SQLiteMemory


@pytest.fixture
def memory(tmp_path):
    return SQLiteMemory(tmp_path / "memory.sqlite")


@pytest.fixture
def scope():
    return MemoryScope(Scope("research", "alice", "team"))


def test_identity_role_namespace_before_search_export_update_delete(memory, scope):
    record = memory.write(scope, "secret project launch", source="user:alice")
    outsiders = [
        replace(scope, identity=Scope("research", "bob", "team")),
        replace(scope, identity=Scope("research", "alice", "other")),
        replace(scope, identity=Scope("other", "alice", "team")),
        replace(scope, role="reviewer"),
        replace(scope, namespace="evaluation"),
    ]
    for other in outsiders:
        assert memory.search(other, "secret") == []
        assert memory.export(other) == []
        for action in [
            lambda: memory.get(other, record["id"]),
            lambda: memory.delete(other, record["id"]),
            lambda: memory.update(other, record["id"], "overwritten", revision=1),
        ]:
            with pytest.raises(KeyError):
                action()
        assert memory.namespace_delete(other) == 0
    assert memory.get(scope, record["id"])["content"] == "secret project launch"


def test_deduplication_revision_conflicts_and_expiration(memory, scope):
    record = memory.write(scope, "喜欢中文回答", source="user:alice")
    assert memory.write(scope, "喜欢中文回答", source="user:alice")["id"] == record["id"]
    assert memory.search(scope, "中文")[0]["id"] == record["id"]

    def update(content):
        try:
            return memory.update(scope, record["id"], content, revision=1)["revision"]
        except MemoryConflict:
            return "conflict"

    with ThreadPoolExecutor(2) as pool:
        assert sorted(map(str, pool.map(update, ["first", "second"]))) == ["2", "conflict"]
    expired = memory.write(scope, "expired fact", source="test", valid_until=time.time() - 10)
    assert memory.search(scope, "expired") == []
    with pytest.raises(KeyError):
        memory.get(scope, expired["id"])


def test_backup_restore_keeps_deletions_even_after_raw_database_rollback(memory, scope, tmp_path):
    record = memory.write(scope, "erase me", source="user", idempotency_key="write-1")
    exported = memory.export(scope)
    backup = tmp_path / "before.sqlite"
    shutil.copyfile(memory.path, backup)
    memory.delete(scope, record["id"])
    assert memory.restore(scope, exported) == {"restored": 0, "skipped": 1}
    shutil.copyfile(backup, memory.path)
    restored = SQLiteMemory(memory.path)
    assert restored.export(scope) == []
    assert restored.search(scope, "erase") == []
    with pytest.raises(KeyError):
        restored.get(scope, record["id"])
    with pytest.raises(MemoryConflict):
        restored.write(scope, "erase me", source="user", idempotency_key="write-1")


def test_namespace_reset_and_foreign_restore(memory, scope):
    record = memory.write(scope, "candidate experience", source="evaluation")
    assert memory.namespace_delete(scope) == 1
    assert memory.restore(scope, [record])["restored"] == 0
    other = replace(scope, namespace="candidate-2")
    with pytest.raises(ValueError, match="different memory scope"):
        memory.restore(other, [record])
    fresh = memory.write(scope, "new experience", source="evaluation")
    assert memory.get(scope, fresh["id"])["content"] == "new experience"


def test_document_citations_resolve_exact_source_offsets(memory, scope):
    documents = replace(scope, namespace="documents")
    retriever = DocumentRetriever(memory)
    text = "  Shared systems require durable checkpoints.\n" + "A loop is bounded. " * 30
    ingested = retriever.ingest(
        documents, title="Runtime guide", text=text, source="docs:runtime", chunk_size=200
    )
    assert (
        retriever.ingest(
            documents, title="Runtime guide", text=text, source="docs:runtime", chunk_size=200
        )
        == ingested
    )
    hits = retriever.search(documents, "durable checkpoints")
    assert hits and hits[0]["text"] == text[hits[0]["start"] : hits[0]["end"]]
    assert hits[0]["source"] == "docs:runtime"
    assert (
        retriever.search(replace(documents, identity=Scope("research", "bob", "team")), "durable")
        == []
    )


async def test_model_tool_cannot_select_other_scope(memory, scope):
    memory.write(scope, "private knowledge", source="user")
    registry = register_memory_tools(builtin_registry(), memory, scope.identity)
    search = registry.resolve("memory.search")
    assert (await search.invoke({"query": "knowledge"}))["records"]
    with pytest.raises(ValidationError):
        await search.invoke({"query": "knowledge", "user": "bob"})
    write = registry.resolve("memory.write")
    first = await write.invoke(
        {"content": "saved fact", "source": "conversation:1"}, operation_id="operation-1"
    )
    second = await write.invoke(
        {"content": "saved fact", "source": "conversation:1"}, operation_id="operation-1"
    )
    assert first == second
