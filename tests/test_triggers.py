from concurrent.futures import ThreadPoolExecutor

import pytest

from evosprig.core.journal import Scope
from evosprig.core.runtime import Runtime
from evosprig.core.version import compile_agent
from evosprig.plugins.sqlite_journal import SQLiteJournal
from evosprig.sdk import Builder


def version(label="first"):
    return compile_agent(Builder("triggered", {"type": "object"}, {"type": "object"}, spec_version="0.3")
                         .node("result", "transform", inputs={"label": {"value": label}},
                               output_schema={"type": "object"})
                         .output(result={"ref": "nodes.result.output"}).build_spec())


def event():
    return {"source": "github:owner/repo", "event_id": "delivery-1", "actor": "maintainer",
            "thread": "issue-7", "payload": {"body": "Fix the empty-input behavior."}}


async def test_redelivery_keeps_completed_run_across_restart_and_deployment_change(tmp_path):
    path = tmp_path / "runs.sqlite"
    first = Runtime({}, journal=SQLiteJournal(path))
    identifier = first.create_event_run(version(), {"task": "original"}, event())
    assert (await first.resume(identifier)).status == "succeeded"
    second = Runtime({}, journal=SQLiteJournal(path), allow_writes=True)
    assert second.create_event_run(version("updated"), {"task": "changed mapping"}, event()) == identifier
    saved = second.journal.get(identifier)
    assert saved["input"] == {"task": "original"}
    assert saved["metadata"]["allow_writes"] is False
    assert saved["version"]["version_id"] == version().version_id
    assert saved["checkpoint"]["output"] == {"result": {"label": "first"}}


def test_concurrent_receivers_create_one_execution_and_reject_changed_event(tmp_path):
    path = tmp_path / "runs.sqlite"
    SQLiteJournal(path)
    agent = version()
    def receive(_):
        runtime = Runtime({}, journal=SQLiteJournal(path))
        return runtime.create_event_run(agent, {}, event())
    with ThreadPoolExecutor(max_workers=4) as executor:
        identifiers = list(executor.map(receive, range(8)))
    assert len(set(identifiers)) == 1
    runtime = Runtime({}, journal=SQLiteJournal(path))
    assert runtime.journal.due() == [identifiers[0]]
    with pytest.raises(ValueError, match="different content"):
        runtime.create_event_run(agent, {}, {**event(), "payload": {"body": "Delete the project."}})
    with pytest.raises(ValueError, match="different content"):
        runtime.create_event_run(agent, {}, {**event(), "actor": "another-user"})


def test_event_identity_includes_source_and_scope(tmp_path):
    runtime = Runtime({}, journal=SQLiteJournal(tmp_path / "runs.sqlite"))
    first = runtime.create_event_run(version(), {}, event())
    another_source = runtime.create_event_run(version(), {}, {**event(), "source": "github:other/repo"})
    another_tenant = runtime.create_event_run(version(), {}, event(), scope=Scope("triggered", tenant="another"))
    assert len({first, another_source, another_tenant}) == 3
    with pytest.raises(ValueError, match="scope"):
        runtime.create_event_run(version(), {}, event(), scope=Scope("other-project"))


async def test_event_survives_receiver_exit_before_worker_starts(tmp_path):
    path = tmp_path / "runs.sqlite"
    identifier = Runtime({}, journal=SQLiteJournal(path)).create_event_run(version(), {}, event())
    restarted = Runtime({}, journal=SQLiteJournal(path))
    assert restarted.journal.due() == [identifier]
    result = await restarted.resume(identifier)
    assert result.status == "succeeded"
    assert restarted.create_event_run(version(), {}, event()) == identifier
    assert restarted.journal.due() == []
