from dataclasses import replace

import pytest

from evosprig.core.journal import Scope
from evosprig.core.memory import MemoryScope
from evosprig.plugins.documents import DocumentRetriever
from evosprig.plugins.episodic_memory import EpisodicMemory
from evosprig.plugins.retrieval import retrieve_many
from evosprig.plugins.sqlite_memory import SQLiteMemory


def test_summary_sources_restore_order_updates_and_deletion(tmp_path):
    scope = MemoryScope(Scope("personal", "alice"))
    memory = SQLiteMemory(tmp_path / "memory.sqlite")
    episodic = EpisodicMemory(memory)
    first = episodic.remember(
        scope, "Cannot eat peanuts", source="user", importance=1, idempotency_key="one"
    )
    assert (
        episodic.remember(
            scope, "Cannot eat peanuts", source="user", importance=1, idempotency_key="one"
        )["id"]
        == first["id"]
    )
    summary = episodic.summarize(scope, "Peanut allergy", [first["id"]])
    other = replace(scope, identity=Scope("personal", "bob"))
    with pytest.raises(KeyError):
        episodic.summarize(other, "leak", [first["id"]])
    restored = SQLiteMemory(tmp_path / "restored.sqlite")
    assert restored.restore(scope, [summary, first])["restored"] == 2
    memory.update(scope, first["id"], "Avoid all nuts", revision=1)
    assert summary["id"] not in {r["id"] for r in memory.export(scope)}
    restored.delete(scope, first["id"])
    assert restored.restore(scope, [summary, first])["restored"] == 0
    assert restored.export(scope) == []


def test_recall_respects_links_scope_and_importance(tmp_path):
    scope = MemoryScope(Scope("personal", "alice"))
    memory = SQLiteMemory(tmp_path / "memory.sqlite")
    episodic = EpisodicMemory(memory)
    important = episodic.remember(scope, "peanut allergy", source="user", importance=1)
    linked = episodic.remember(scope, "dinner booking", source="user", links=[important["id"]])
    memory.write(scope, "dinner menu", source="user")
    hits = episodic.recall(scope, "booking", limit=1)
    assert [hit["id"] for hit in hits] == [linked["id"], important["id"]]
    memory.delete(scope, important["id"])
    assert len(episodic.recall(scope, "booking", limit=1)) == 1


def test_multi_query_fusion_returns_distinct_citations(tmp_path):
    memory = SQLiteMemory(tmp_path / "memory.sqlite")
    scope = MemoryScope(Scope("research", "alice"), namespace="documents")
    retriever = DocumentRetriever(memory)
    retriever.ingest(
        scope,
        title="Delivery",
        text="Delivery requires three business days.",
        source="policy:delivery",
    )
    retriever.ingest(
        scope,
        title="Refunds",
        text="Refunds require the original receipt.",
        source="policy:refunds",
    )
    hits = retrieve_many(retriever, scope, ["delivery", "refunds", "delivery"], limit=3)
    assert len(hits) == 2
    assert {h["source"] for h in hits} == {"policy:delivery", "policy:refunds"}
    assert all(h["citation"] for h in hits)
