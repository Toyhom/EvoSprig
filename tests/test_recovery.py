import sqlite3
import subprocess
import sys
import time

import pytest

from evosprig.core.protocols import ExternalStatus, ExternalTool, Tool, ToolRegistry
from evosprig.core.runtime import Runtime
from evosprig.core.spec import save_spec
from evosprig.core.version import compile_agent
from evosprig.plugins.sqlite_journal import SQLiteJournal
from evosprig.sdk import Builder

NUMBER = {
    "type": "object",
    "properties": {"value": {"type": "integer"}},
    "required": ["value"],
    "additionalProperties": False,
}
EMPTY = {"type": "object", "additionalProperties": False}


def tool_spec(plugin="test.counter"):
    return (
        Builder("recovery", EMPTY, NUMBER, spec_version="0.2")
        .tool("action", plugin)
        .node("action", "tool", tool="action", output_schema=NUMBER)
        .output(value={"ref": "nodes.action.output.value"})
        .execution(allow_side_effects=True)
        .build_spec()
    )


def registry(tool):
    tools = ToolRegistry()
    tools.register(tool)
    return tools


async def test_hard_worker_exit_after_tool_result_reuses_durable_receipt(tmp_path, monkeypatch):
    """Real subprocess termination between tool receipt and node completion (T03)."""
    spec = tool_spec()
    save_spec(spec, tmp_path / "agent.yaml")
    script = """import asyncio,os,sqlite3
from pathlib import Path
from evosprig.core.protocols import Tool,ToolRegistry
from evosprig.core.spec import load_spec
from evosprig.core.version import compile_agent
from evosprig.core.runtime import Runtime
from evosprig.plugins.sqlite_journal import SQLiteJournal
root=Path(__file__).parent
spec=load_spec(root/'agent.yaml')
def write_once(*,idempotency_key):
    with sqlite3.connect(root/'remote.sqlite') as db:
        db.execute('CREATE TABLE IF NOT EXISTS receipts (id TEXT PRIMARY KEY)')
        db.execute('INSERT OR IGNORE INTO receipts VALUES (?)',(idempotency_key,))
        return {'value':db.execute('SELECT COUNT(*) FROM receipts').fetchone()[0]}
tools=ToolRegistry()
tools.register(Tool('test.counter','counter',{'type':'object','additionalProperties':False},spec.output_schema,write_once,side_effect='write',idempotent=True))
def crash(event):
    if event['type']=='tool.result': os._exit(70)
asyncio.run(Runtime({},tools,journal=SQLiteJournal(root/'runs.sqlite'),allow_writes=True,lease_seconds=30).run(compile_agent(spec),{},run_id='crashed',on_event=crash))
"""
    script_path = tmp_path / "crash_worker.py"
    script_path.write_text(script)
    process = subprocess.run(
        [sys.executable, str(script_path)], cwd=tmp_path, capture_output=True, text=True, timeout=20
    )
    assert process.returncode == 70, process.stderr

    async def must_not_execute(**kwargs):
        pytest.fail("persisted result must be reused")

    tool = Tool(
        "test.counter",
        "counter",
        EMPTY,
        NUMBER,
        must_not_execute,
        side_effect="write",
        idempotent=True,
    )
    store = SQLiteJournal(tmp_path / "runs.sqlite")
    # Advance the journal clock after a real crash; shared-filesystem latency must
    # not require an unrealistically short lease in the subprocess.
    expired = store.get("crashed")["lease_until"] + 1
    monkeypatch.setattr(time, "time", lambda: expired)
    result = await Runtime({}, registry(tool), journal=store, allow_writes=True).resume("crashed")
    assert result.status == "succeeded", result.error
    assert result.output == {"value": 1}
    with sqlite3.connect(tmp_path / "remote.sqlite") as db:
        assert db.execute("SELECT COUNT(*) FROM receipts").fetchone()[0] == 1


async def test_unknown_non_idempotent_write_is_not_replayed(tmp_path, monkeypatch):
    now = [time.time()]
    monkeypatch.setattr(time, "time", lambda: now[0])

    class Crash(BaseException):
        pass

    writes = []

    async def unsafe_write():
        writes.append("effect")
        raise Crash()

    store = SQLiteJournal(tmp_path / "runs.sqlite")
    tools = registry(
        Tool("test.counter", "counter", EMPTY, NUMBER, unsafe_write, side_effect="write")
    )
    runtime = Runtime({}, tools, journal=store, allow_writes=True)
    with pytest.raises(Crash):
        await runtime.run(compile_agent(tool_spec()), {}, run_id="unknown")
    now[0] += 31
    result = await Runtime({}, tools, journal=SQLiteJournal(store.path), allow_writes=True).resume(
        "unknown"
    )
    assert result.status == "waiting_input"
    assert len(writes) == 1
    assert result.waiting[0]["kind"] == "operation_unknown"
    store.respond("unknown", result.waiting[0]["path"], {"value": 1})
    result = await runtime.resume("unknown")
    assert result.status == "succeeded" and result.output == {"value": 1}
    assert len(writes) == 1


async def test_external_job_survives_restart_and_uses_original_job_id(tmp_path):
    submissions, polls = [], []
    complete = False

    async def submit(*, idempotency_key):
        submissions.append(idempotency_key)
        return "video-job-17"

    async def poll(job_id):
        polls.append(job_id)
        return ExternalStatus("succeeded", {"value": 17}) if complete else ExternalStatus("pending")

    tool = ExternalTool("test.counter", "external job", EMPTY, NUMBER, submit, poll)
    store = SQLiteJournal(tmp_path / "runs.sqlite")
    first = await Runtime({}, registry(tool), journal=store, allow_writes=True).run(
        compile_agent(tool_spec()), {}, run_id="external"
    )
    assert first.status == "waiting_external"
    assert first.waiting[0]["job_id"] == "video-job-17"
    complete = True
    second = await Runtime(
        {}, registry(tool), journal=SQLiteJournal(store.path), allow_writes=True
    ).resume("external")
    assert second.status == "succeeded" and second.output == {"value": 17}
    assert len(submissions) == 1 and polls == ["video-job-17", "video-job-17"]


async def test_cancel_pending_external_job_propagates_and_records_result(tmp_path):
    canceled = []

    async def submit(*, idempotency_key):
        return "job"

    async def poll(job_id):
        return ExternalStatus("pending")

    async def cancel(job_id):
        canceled.append(job_id)
        return ExternalStatus("canceled")

    tool = ExternalTool("test.counter", "external", EMPTY, NUMBER, submit, poll, cancel)
    runtime = Runtime(
        {}, registry(tool), journal=SQLiteJournal(tmp_path / "runs.sqlite"), allow_writes=True
    )
    result = await runtime.run(compile_agent(tool_spec()), {}, run_id="cancel")
    assert result.status == "waiting_external"
    result = await runtime.cancel_run("cancel")
    assert result.status == "canceled"
    assert canceled == ["job"]
    assert any(
        event["type"] == "external.cancel" and event["data"]["state"] == "canceled"
        for event in result.events
    )


async def test_write_permission_requires_runtime_spec_and_durable_store(tmp_path):
    calls = []

    async def write():
        calls.append(1)
        return {"value": 1}

    tools = registry(Tool("test.counter", "write", EMPTY, NUMBER, write, side_effect="write"))
    version = compile_agent(tool_spec())
    for runtime in [
        Runtime({}, tools, allow_writes=True),
        Runtime({}, tools, journal=SQLiteJournal(tmp_path / "runs.sqlite")),
    ]:
        result = await runtime.run(version, {})
        assert result.status == "failed"
    assert calls == []


async def test_uncertain_submit_retries_same_key_and_poll_failure_keeps_job(tmp_path):
    attempts, polls = [], []

    async def submit(*, idempotency_key):
        attempts.append(idempotency_key)
        if len(attempts) == 1:
            raise TimeoutError()
        return "existing-job"

    async def poll(job_id):
        polls.append(job_id)
        if len(polls) == 1:
            raise TimeoutError()
        return ExternalStatus("succeeded", {"value": 9})

    tool = ExternalTool("test.counter", "remote", EMPTY, NUMBER, submit, poll)
    runtime = Runtime(
        {}, registry(tool), journal=SQLiteJournal(tmp_path / "runs.sqlite"), allow_writes=True
    )
    first = await runtime.run(compile_agent(tool_spec()), {}, run_id="transient")
    assert first.status == "waiting_external"
    assert first.waiting[0]["state"] == "submission_unknown"
    second = await runtime.resume("transient")
    assert second.status == "waiting_external" and second.waiting[0]["job_id"] == "existing-job"
    final = await runtime.resume("transient")
    assert final.status == "succeeded"
    assert len(attempts) == 2 and len(set(attempts)) == 1
    assert polls == ["existing-job", "existing-job"]
