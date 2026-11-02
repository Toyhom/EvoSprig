import json

import httpx

from evosprig.core.protocols import ToolRegistry
from evosprig.core.runtime import Runtime
from evosprig.core.version import compile_agent
from evosprig.plugins.external_http import ExternalHTTPConfig, external_http_tool
from evosprig.plugins.sqlite_journal import SQLiteJournal
from evosprig.sdk import Builder


async def test_http_job_resume_keeps_id_and_submits_once(tmp_path):
    state = {"submits": 0, "ready": False, "key": None}

    def handler(request):
        if request.method == "POST":
            state["submits"] += 1
            state["key"] = request.headers["idempotency-key"]
            assert json.loads(request.content) == {"value": "story"}
            return httpx.Response(200, json={"job_id": "job-123"})
        assert request.url.path == "/jobs/job-123"
        return httpx.Response(
            200,
            json={
                "status": "succeeded" if state["ready"] else "pending",
                "output": {"text": "movie"},
            },
        )

    config = ExternalHTTPConfig(
        name="media.render",
        description="render",
        endpoint="http://localhost/jobs",
        input_schema={"type": "object"},
        output_schema={"type": "object"},
    )
    registry = ToolRegistry()
    registry.register(external_http_tool(config, transport=httpx.MockTransport(handler)))
    spec = (
        Builder("film", {}, {}, spec_version="0.2")
        .tool("render", "media.render")
        .node(
            "render",
            "tool",
            tool="render",
            inputs={"value": {"value": "story"}},
            output_schema={"type": "object"},
        )
        .output(text={"ref": "nodes.render.output.text"})
        .execution(allow_side_effects=True)
        .build_spec()
    )
    journal = SQLiteJournal(tmp_path / "runs.sqlite")
    first = await Runtime({}, registry, journal=journal, allow_writes=True).run(
        compile_agent(spec), {}
    )
    assert first.status == "waiting_external"
    assert first.waiting[0]["job_id"] == "job-123"
    state["ready"] = True
    final = await Runtime(
        {}, registry, journal=SQLiteJournal(tmp_path / "runs.sqlite"), allow_writes=True
    ).resume(first.run_id)
    assert final.status == "succeeded"
    assert final.output == {"text": "movie"}
    assert state["submits"] == 1
    assert len(state["key"]) == 64
