import asyncio

import pytest

from evosprig.core.protocols import Tool, ToolRegistry
from evosprig.core.runtime import Runtime
from evosprig.core.version import compile_agent
from evosprig.plugins.sqlite_journal import SQLiteJournal
from evosprig.sdk import Builder


async def test_pure_computation_restarts_without_changing_write_recovery(tmp_path):
    started, shutdown = asyncio.Event(), asyncio.Event()
    calculations, writes = [], []

    async def calculate(value):
        calculations.append(value)
        if len(calculations) == 1:
            started.set()
            await asyncio.Event().wait()
        return {"value": value * 2}

    def write(value):
        writes.append(value)
        return {"value": value}

    registry = ToolRegistry()
    registry.register(Tool("calculate", "Double a number", {}, {}, calculate, pure=True))
    registry.register(Tool("write", "Save the result", {}, {}, write, side_effect="write"))
    spec = (Builder("pure-recovery", {}, {}, spec_version="0.3").tool("calculate", "calculate").tool("write", "write")
            .node("calculate", "tool", tool="calculate", inputs={"value": {"value": 21}}, output_schema={})
            .node("save", "tool", tool="write", inputs={"value": {"ref": "nodes.calculate.output.value"}}, output_schema={})
            .edge("calculate", "save").output(value={"ref": "nodes.save.output.value"})
            .execution(allow_side_effects=True, pure_checkpoint_interval=16).build_spec())
    path = tmp_path / "runs.sqlite"
    first = Runtime({}, registry, journal=SQLiteJournal(path), allow_writes=True)
    task = asyncio.create_task(first.run(compile_agent(spec), {}, shutdown=shutdown))
    await asyncio.wait_for(started.wait(), 5)
    shutdown.set()
    paused = await asyncio.wait_for(task, 10)
    assert paused.status == "queued"
    assert writes == []
    second = Runtime({}, registry, journal=SQLiteJournal(path), allow_writes=True)
    result = await second.resume(paused.run_id)
    assert result.status == "succeeded", result.error
    assert calculations == [21, 21] and writes == [42]
    assert result.output == {"value": 42}
    operations = second.journal.operations(result.run_id)
    assert len(operations) == 1 and operations[0]["intent"]["alias"] == "write"
    assert any(e["type"] == "tool.result" and e["data"].get("pure") for e in result.events)
    assert (await second.resume(result.run_id)).status == "succeeded"
    assert writes == [42]


def test_external_effects_cannot_be_marked_pure():
    with pytest.raises(ValueError, match="pure tools"):
        Tool("write", "write", {}, {}, lambda: {}, side_effect="write", pure=True)
    with pytest.raises(ValueError, match="pure tools"):
        Tool("job", "job", {}, {}, lambda: {}, idempotent=True, pure=True)


async def test_persisted_cancel_interrupts_a_running_pure_tool(tmp_path):
    started = asyncio.Event()

    async def calculate():
        started.set()
        await asyncio.Event().wait()

    registry = ToolRegistry()
    registry.register(Tool("calculate", "Compute", {}, {}, calculate, pure=True))
    spec = (Builder("pure-cancel", {}, {}).tool("calculate", "calculate")
            .node("calculate", "tool", tool="calculate", output_schema={})
            .output(result={"ref": "nodes.calculate.output"}).build_spec())
    path = tmp_path / "runs.sqlite"
    runtime = Runtime({}, registry, journal=SQLiteJournal(path))
    task = asyncio.create_task(runtime.run(compile_agent(spec), {}, run_id="cancel-pure"))
    await asyncio.wait_for(started.wait(), 5)
    SQLiteJournal(path).cancel("cancel-pure")
    result = await asyncio.wait_for(task, 5)
    assert result.status == "canceled"
    assert runtime.journal.operations(result.run_id) == []


async def test_lease_loss_prevents_following_write(tmp_path):
    import json
    import sqlite3

    from evosprig.core.journal import LeaseLost

    path = tmp_path / "runs.sqlite"
    writes = []

    async def calculate():
        # A second worker supersedes the first while its pure work is in flight.
        with sqlite3.connect(path) as db:
            record = json.loads(db.execute("SELECT body FROM runtime_runs").fetchone()[0])
            record["generation"] += 1
            db.execute("UPDATE runtime_runs SET body=?", (json.dumps(record),))
        return {}

    registry = ToolRegistry()
    registry.register(Tool("calculate", "Compute", {}, {}, calculate, pure=True))
    registry.register(Tool("write", "Write", {}, {}, lambda: writes.append(1), side_effect="write"))
    spec = (Builder("pure-fence", {}, {}, spec_version="0.3").tool("calculate", "calculate").tool("write", "write")
            .node("calculate", "tool", tool="calculate", output_schema={})
            .node("write", "tool", tool="write", output_schema={}).edge("calculate", "write")
            .output(result={"ref": "nodes.write.output"})
            .execution(allow_side_effects=True, pure_checkpoint_interval=16).build_spec())
    runtime = Runtime({}, registry, journal=SQLiteJournal(path), allow_writes=True)
    with pytest.raises(LeaseLost):
        await runtime.run(compile_agent(spec), {})
    assert writes == []
