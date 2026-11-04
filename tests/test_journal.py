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


def test_legacy_migration_preserves_pending_run_and_fences_owner(spec, example_root, tmp_path, advance_clock):
    import json
    import sqlite3

    from evosprig.core.journal import new_run

    path = tmp_path / 'legacy.sqlite'
    record = new_run('run', compile_agent(spec, example_root), {'question': 'hello'}, Scope(spec.id), {})
    record.update(owner='old', generation=7, lease_until=time.time()+30, status='running')
    record['checkpoint']['output'] = {'image': 'data:image/png;base64,' + 'A' * 2_000_000}
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE runtime_runs (id TEXT PRIMARY KEY, body TEXT NOT NULL)')
        db.execute('INSERT INTO runtime_runs VALUES (?,?)', ('run', json.dumps(record)))
    journal = SQLiteJournal(path)
    assert journal.get('run') == record
    assert SQLiteJournal(path).get('run') == record
    with pytest.raises(LeaseConflict):
        journal.claim('run', 'next')
    advance_clock(31)
    lease = journal.claim('run', 'next')
    assert lease.generation == 8
    journal.save(lease, record['checkpoint'], 'succeeded', [{'type': 'run.succeeded'}], release=True)
    assert journal.get('run')['checkpoint'] == record['checkpoint']
    assert journal.summaries(Scope(spec.id))[0]['status'] == 'succeeded'


def test_controls_do_not_read_or_rewrite_large_checkpoint(spec, example_root, tmp_path, monkeypatch):
    import sqlite3

    journal = SQLiteJournal(tmp_path / 'large.sqlite')
    record = create(journal, spec, example_root)
    lease = journal.claim('run', 'worker')
    record['checkpoint']['output'] = {'image': 'data:image/png;base64,' + 'A' * 8_000_000}
    journal.save(lease, record['checkpoint'], 'running', [])
    with sqlite3.connect(journal.path) as db:
        before = db.execute('SELECT body FROM runtime_checkpoints').fetchone()[0]
    monkeypatch.setattr(journal, '_read', lambda *a: pytest.fail('control path read the snapshot'))
    for _ in range(5):
        journal.heartbeat(lease)
        journal.operation(lease, 'job', {'tool': 'render'})
        assert journal.control('run')['owner'] == 'worker'
        assert journal.due() == []
    journal.cancel('run', Scope(spec.id))
    assert journal.control('run')['cancel_requested']
    with sqlite3.connect(journal.path) as db:
        assert db.execute('SELECT body FROM runtime_checkpoints').fetchone()[0] == before


def test_expired_lease_is_rejected_after_checkpoint_serialization(spec, example_root, tmp_path, monkeypatch, advance_clock):
    import evosprig.plugins.sqlite_journal as module

    journal = SQLiteJournal(tmp_path / 'race.sqlite')
    record = create(journal, spec, example_root)
    lease = journal.claim('run', 'old')
    encode = module.canonical_json
    def slow_encode(value):
        if value is record['checkpoint']:
            advance_clock(31)
            journal.claim('run', 'new')
        return encode(value)
    monkeypatch.setattr(module, 'canonical_json', slow_encode)
    with pytest.raises(LeaseLost):
        journal.save(lease, record['checkpoint'], 'succeeded', [{'type': 'run.succeeded'}])
    assert journal.control('run')['owner'] == 'new'
    assert journal.events('run') == []
