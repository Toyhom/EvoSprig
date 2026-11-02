import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from evosprig.core.journal import LeaseConflict, LeaseLost, MemoryJournal, Scope
from evosprig.core.version import compile_agent
from evosprig.plugins.sqlite_journal import SQLiteJournal


@pytest.fixture(params=["memory", "sqlite"])
def journal(request, tmp_path):
    return MemoryJournal() if request.param == "memory" else SQLiteJournal(tmp_path / "runs.sqlite")


@pytest.fixture
def advance_clock(monkeypatch):
    now = [time.time()]
    monkeypatch.setattr(time, "time", lambda: now[0])

    def advance(seconds):
        now[0] += seconds

    return advance


def create(journal, spec, example_root):
    version = compile_agent(spec, example_root)
    return journal.create("run", version, {"question": "hello"}, Scope(spec.id), {})


def test_atomic_lease_and_fencing(journal, spec, example_root, advance_clock):
    record = create(journal, spec, example_root)
    first = journal.claim("run", "worker-a", 0.04)
    with pytest.raises(LeaseConflict):
        journal.claim("run", "worker-b", 30)
    journal.operation(first, "operation", {"tool": "write"})
    advance_clock(0.05)
    second = journal.claim("run", "worker-b", 30)
    assert second.generation == first.generation + 1
    with pytest.raises(LeaseLost):
        journal.save(first, record["checkpoint"], "succeeded", [])
    with pytest.raises(LeaseLost):
        journal.operation(first, "operation", update={"status": "succeeded"})
    journal.save(
        second, record["checkpoint"], "succeeded", [{"type": "run.succeeded"}], release=True
    )
    assert journal.get("run")["status"] == "succeeded"
    with pytest.raises(LeaseConflict):
        journal.claim("run", "worker-c", 30)


def test_scope_idempotent_creation_and_snapshots(journal, spec, example_root):
    first = create(journal, spec, example_root)
    assert create(journal, spec, example_root) == first
    with pytest.raises(KeyError):
        journal.get("run", Scope(spec.id, "someone-else"))
    with pytest.raises(ValueError):
        journal.create(
            "run", compile_agent(spec, example_root), {"question": "changed"}, Scope(spec.id), {}
        )
    first["checkpoint"]["output"] = {"mutated": True}
    assert journal.get("run")["checkpoint"]["output"] is None


def test_events_have_one_atomic_sequence(journal, spec, example_root):
    record = create(journal, spec, example_root)
    lease = journal.claim("run", "worker", 30)

    def save(index):
        return journal.save(
            lease, record["checkpoint"], "running", [{"type": "test", "data": {"index": index}}]
        )

    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(save, range(12)))
    events = journal.events("run")
    assert [event["sequence"] for event in events] == list(range(1, 13))
    assert len({event["event_id"] for event in events}) == 12
    assert len(journal.events("run", 8)) == 4


def test_manual_wait_cancellation_and_due_work(journal, spec, example_root):
    record = create(journal, spec, example_root)
    assert journal.due() == ["run"]
    lease = journal.claim("run", "worker", 30)
    assert not journal.due()
    checkpoint = record["checkpoint"]
    checkpoint["waiting"] = [{"path": "graph/approval", "kind": "human"}]
    journal.save(lease, checkpoint, "waiting_input", [], release=True)
    assert not journal.due()
    with pytest.raises(ValueError):
        journal.respond("run", "wrong", {})
    journal.respond("run", "graph/approval", {"approved": True})
    assert journal.due() == ["run"]
    journal.cancel("run", Scope(spec.id))
    assert journal.get("run")["cancel_requested"]
    assert journal.due() == ["run"]


def test_sqlite_reopens_fixed_snapshot_and_operation(spec, example_root, tmp_path, advance_clock):
    path = tmp_path / "runs.sqlite"
    first = SQLiteJournal(path)
    create(first, spec, example_root)
    lease = first.claim("run", "worker", 0.04)
    first.operation(lease, "op", {"plugin": "service", "arguments": {"x": 1}})
    first.operation(lease, "op", update={"status": "succeeded", "output": {"value": 42}})
    second = SQLiteJournal(path)
    advance_clock(0.05)
    reclaimed = second.claim("run", "restart", 30)
    assert second.operation(reclaimed, "op")["output"] == {"value": 42}
    assert second.get("run")["input"] == {"question": "hello"}
