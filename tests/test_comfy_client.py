import json

import httpx
import pytest

from evosprig.core.journal import Scope
from evosprig.core.protocols import ExecutionError
from evosprig.integrations.comfy_client import ComfyClient
from evosprig.plugins.comfy_tools import ComfyJobConfig, comfy_job_tool


async def test_client_completion_race_and_shared_server_controls():
    history_reads, writes = 0, []

    def handler(request):
        nonlocal history_reads
        if request.url.path == "/history/job1":
            history_reads += 1
            return httpx.Response(200, json={} if history_reads == 1 else {"job1": {"status": {"completed": True}, "outputs": {"1": {"images": ["frame.png"]}}}})
        if request.url.path == "/queue":
            return httpx.Response(200, json={"queue_running": [], "queue_pending": []})
        writes.append(request.url.path)
        return httpx.Response(200, json={})

    client = ComfyClient(transport=httpx.MockTransport(handler))
    assert (await client.status("job1"))["status"] == "succeeded"
    with pytest.raises(ValueError, match="dedicated"):
        await client.free_models()
    assert writes == []
    with pytest.raises(ValueError, match="prompt ID"):
        await client.status("../other")


async def test_no_duplicate_render_after_lost_submission_response(tmp_path):
    submissions, queued = [], []

    def handler(request):
        if request.url.path == "/prompt":
            body = json.loads(request.content)
            submissions.append(body)
            queued.append([1, "job1", body["prompt"], body["extra_data"]])
            raise httpx.ReadTimeout("response lost", request=request)
        if request.url.path == "/queue":
            return httpx.Response(200, json={"queue_running": queued, "queue_pending": []})
        return httpx.Response(200, json={})

    config = ComfyJobConfig(name="comfy.render")
    tool = comfy_job_tool(config, tmp_path / "jobs.sqlite", Scope("film"), transport=httpx.MockTransport(handler))
    prompt = {"1": {"class_type": "Save", "inputs": {}}}
    with pytest.raises(httpx.ReadTimeout):
        await tool.submit(prompt=prompt, idempotency_key="op1")
    restored = comfy_job_tool(config, tmp_path / "jobs.sqlite", Scope("film"), transport=httpx.MockTransport(handler))
    assert await restored.submit(prompt=prompt, idempotency_key="op1") == "job1"
    assert await restored.submit(prompt=prompt, idempotency_key="op1") == "job1"
    assert len(submissions) == 1
    assert (await restored.poll("job1")).status == "pending"
    with pytest.raises(ExecutionError, match="different inputs"):
        await restored.submit(prompt={"2": {"class_type": "Save", "inputs": {}}}, idempotency_key="op1")


async def test_unresolved_submission_never_renders_again(tmp_path):
    count = 0

    def handler(request):
        nonlocal count
        if request.url.path == "/prompt":
            count += 1
            raise httpx.ReadTimeout("lost", request=request)
        return httpx.Response(200, json={})

    tool = comfy_job_tool(ComfyJobConfig(name="comfy.render"), tmp_path / "jobs.sqlite", Scope("film"), transport=httpx.MockTransport(handler))
    prompt = {"1": {"class_type": "Save", "inputs": {}}}
    with pytest.raises(httpx.ReadTimeout):
        await tool.submit(prompt=prompt, idempotency_key="op1")
    with pytest.raises(ExecutionError, match="unresolved"):
        await tool.submit(prompt=prompt, idempotency_key="op1")
    assert count == 1


async def test_unload_rejects_queued_work_and_cancels_only_requested_id():
    calls = []

    def handler(request):
        calls.append((request.method, request.url.path, json.loads(request.content) if request.content else None))
        return httpx.Response(200, json={"queue_running": [], "queue_pending": [[1, "job1"]]})

    client = ComfyClient(dedicated=True, transport=httpx.MockTransport(handler))
    with pytest.raises(ValueError, match="pending work"):
        await client.free_models()
    await client.cancel("job1")
    assert calls[-1] == ("POST", "/queue", {"delete": ["job1"]})
    assert not any(path == "/free" for _, path, _ in calls)


async def test_rejected_prompt_keeps_node_feedback_after_restart(tmp_path):
    from evosprig.integrations.comfy_client import ComfyValidationError

    requests = []

    def handler(request):
        requests.append(request.url.path)
        return httpx.Response(400, json={
            "error": {"type": "prompt_outputs_failed_validation", "message": "Prompt outputs failed validation"},
            "node_errors": {"12": {"class_type": "LoadImage", "errors": [
                {"message": "Invalid image file", "details": "character.png"}]}},
        })

    config = ComfyJobConfig(name="comfy.render")
    prompt = {"12": {"class_type": "LoadImage", "inputs": {"image": "character.png"}}}
    for _ in range(2):
        tool = comfy_job_tool(config, tmp_path / "jobs.sqlite", Scope("film"), transport=httpx.MockTransport(handler))
        with pytest.raises(ComfyValidationError, match=r"Node 12 \(LoadImage\): Invalid image file: character.png"):
            await tool.submit(prompt=prompt, idempotency_key="op1")
    assert requests == ["/prompt"]


async def test_partly_accepted_graph_keeps_its_render_id(tmp_path):
    submissions = []

    def handler(request):
        submissions.append(request.url.path)
        return httpx.Response(200, json={"prompt_id": "accepted1", "node_errors": {
            "bad-preview": {"errors": [{"message": "Preview branch failed validation"}]}}})

    config = ComfyJobConfig(name="comfy.render")
    prompt = {"1": {"class_type": "Save", "inputs": {}}}
    for _ in range(2):
        tool = comfy_job_tool(config, tmp_path / "jobs.sqlite", Scope("film"), transport=httpx.MockTransport(handler))
        assert await tool.submit(prompt=prompt, idempotency_key="op1") == "accepted1"
    assert submissions == ["/prompt"]


async def test_native_render_failure_records_node_details(tmp_path):
    from evosprig.core.protocols import ToolRegistry
    from evosprig.core.runtime import Runtime
    from evosprig.core.version import compile_agent
    from evosprig.plugins.sqlite_journal import SQLiteJournal
    from evosprig.sdk import Builder

    def handler(request):
        if request.url.path == "/prompt":
            return httpx.Response(200, json={"prompt_id": "job1"})
        return httpx.Response(200, json={"job1": {"status": {"status_str": "error", "messages": [
            ["execution_error", {"node_id": "vae", "exception_message": "decoder could not load its library"}]]}}})

    registry = ToolRegistry()
    registry.register(comfy_job_tool(ComfyJobConfig(name="comfy.render"), tmp_path / "jobs.sqlite",
                                    Scope("film"), transport=httpx.MockTransport(handler)))
    spec = (Builder("film", {}, {}, spec_version="0.2").tool("render", "comfy.render")
            .node("render", "tool", tool="render", output_schema={},
                  inputs={"prompt": {"value": {"vae": {"class_type": "Decode", "inputs": {}}}}})
            .output(result={"ref": "nodes.render.output"}).execution(allow_side_effects=True).build_spec())
    result = await Runtime({}, registry, journal=SQLiteJournal(tmp_path / "runs.sqlite"),
                           allow_writes=True).run(compile_agent(spec), {})
    assert result.status == "failed"
    event = next(e for e in result.events if e["type"] == "external.failed")
    assert event["node_id"] == "graph/render"
    assert event["data"]["job_id"] == "job1"
    assert "decoder could not load its library" in event["data"]["message"]
