import asyncio
import json
import os
import subprocess
import sys

import httpx

from evosprig.core.spec import save_spec
from evosprig.core.version import compile_agent
from evosprig.exporters.python import export_python
from evosprig.sdk import Builder
from evosprig.server.app import create_app


def approval_spec():
    schema = {
        "type": "object",
        "properties": {"text": {"type": "string"}},
        "required": ["text"],
        "additionalProperties": False,
    }
    return (
        Builder("approval", schema, schema, spec_version="0.2")
        .node("approval", "human", inputs={"draft": {"ref": "input.text"}}, output_schema=schema)
        .output(text={"ref": "nodes.approval.output.text"})
        .build_spec()
    )


async def wait_for(client, run_id, expected):
    for _ in range(150):
        record = (await client.get(f"/api/runs/{run_id}")).json()
        if record["status"] == expected:
            return record
        await asyncio.sleep(0.02)
    raise AssertionError(record)


async def test_api_restart_uses_frozen_version_and_validated_human_input(tmp_path):
    spec = approval_spec()
    app = create_app(tmp_path)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://localhost"
        ) as client:
            assert (
                await client.post("/api/projects", json={"spec": spec.model_dump()})
            ).status_code == 201
            started = (
                await client.post(
                    "/api/projects/approval/runs", json={"input": {"text": "draft"}, "revision": 1}
                )
            ).json()
            run_id = started["run_id"]
            waiting = await wait_for(client, run_id, "waiting_input")
            assert waiting["waiting"][0]["input"] == {"draft": "draft"}
            edited = spec.model_dump()
            edited["graph"]["output"] = {"text": {"value": "new project revision"}}
            assert (
                await client.put(
                    "/api/projects/approval", json={"spec": edited, "layout": {}, "revision": 1}
                )
            ).status_code == 200
    restarted = create_app(tmp_path)
    async with restarted.router.lifespan_context(restarted):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=restarted), base_url="http://localhost"
        ) as client:
            bad = await client.post(
                f"/api/runs/{run_id}/input",
                json={"path": "graph/approval", "response": {"text": 1}},
            )
            assert bad.status_code == 422
            assert (await client.get(f"/api/runs/{run_id}")).json()["status"] == "waiting_input"
            good = await client.post(
                f"/api/runs/{run_id}/input",
                json={"path": "graph/approval", "response": {"text": "reviewed"}},
            )
            assert good.status_code == 202
            final = await wait_for(client, run_id, "succeeded")
            assert final["output"] == {"text": "reviewed"}
            assert final["agent_version"] == started["agent_version"]
            history = (await client.get("/api/projects/approval/runs")).json()
            assert history[0]["run_id"] == run_id


def test_cli_and_export_resume_without_original_control_plane(tmp_path):
    spec = approval_spec()
    path = tmp_path / "agent.yaml"
    save_spec(spec, path)
    workspace = tmp_path / "workspace"
    first = subprocess.run(
        [
            sys.executable,
            "-m",
            "evosprig.cli",
            "run",
            str(path),
            "--input",
            '{"text":"draft"}',
            "--mock",
            "--workspace",
            str(workspace),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    waiting = json.loads(first.stdout)
    assert waiting["status"] == "waiting_input"
    resumed = subprocess.run(
        [
            sys.executable,
            "-m",
            "evosprig.cli",
            "resume",
            waiting["run_id"],
            "--workspace",
            str(workspace),
            "--path",
            "graph/approval",
            "--response",
            '{"text":"approved"}',
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert json.loads(resumed.stdout)["output"] == {"text": "approved"}
    exported = tmp_path / "export"
    export_python(compile_agent(spec), exported)
    environment = {**os.environ, "PYTHONPATH": str(exported / "src")}
    created = subprocess.run(
        [sys.executable, "app.py", "--mock", "--input", '{"text":"export draft"}'],
        cwd=exported,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )
    record = json.loads(created.stdout)
    completed = subprocess.run(
        [
            sys.executable,
            "app.py",
            "--resume",
            record["run_id"],
            "--path",
            "graph/approval",
            "--response",
            '{"text":"portable"}',
        ],
        cwd=exported,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )
    assert json.loads(completed.stdout)["output"] == {"text": "portable"}
