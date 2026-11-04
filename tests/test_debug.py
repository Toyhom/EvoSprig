import asyncio

import httpx
import pytest

from evosprig.core.debug import plan_debug
from evosprig.core.runtime import Runtime
from evosprig.core.version import compile_snapshot
from evosprig.plugins.builtin_tools import builtin_registry
from evosprig.sdk.builder import Builder
from evosprig.server.app import create_app


@pytest.fixture
def pipeline():
    builder = Builder("debug-demo", {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}, {"type": "object"}, spec_version="0.3")
    builder.node("first", "transform", inputs={"text": {"ref": "input.text"}}, output_schema={"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]})
    builder.node("second", "transform", inputs={"content": {"ref": "nodes.first.output.text"}}, output_schema={"type": "object", "properties": {"content": {"type": "string"}}, "required": ["content"]})
    builder.node("third", "transform", inputs={"result": {"ref": "nodes.second.output.content"}}, output_schema={"type": "object"})
    builder.edge("first", "second").edge("second", "third").output(result={"ref": "nodes.third.output"})
    return builder.build_spec()


async def test_selected_fragment_runs_without_repeating_upstream(pipeline):
    plan = plan_debug(pipeline, ["second", "third"])
    assert plan.boundary[0]["reference"] == "nodes.first.output.text"
    assert "first" not in plan.spec.graph.nodes
    result = await Runtime({}, builtin_registry()).run(compile_snapshot(plan.spec, {}), {"project": {"text": "original"}, "upstream": {"first": {"text": "cached"}}})
    assert result.status == "succeeded"
    assert result.output == {"second": {"content": "cached"}, "third": {"result": "cached"}}
    assert not any(event["node_id"] == "graph/first" for event in result.events)


async def test_debug_only_requests_project_fields_used_by_selection(pipeline):
    plan = plan_debug(pipeline, ["second"])
    assert plan.spec.input_schema["properties"]["project"]["required"] == []
    result = await Runtime({}, builtin_registry()).run(compile_snapshot(plan.spec, {}),
                                                      {"project": {}, "upstream": {"first": {"text": "saved frame"}}})
    assert result.status == "succeeded", result.error
    first = plan_debug(pipeline, ["first"])
    assert first.spec.input_schema["properties"]["project"]["required"] == ["text"]


async def test_nonadjacent_selection_orders_live_dependencies_and_reuses_omitted_outputs(pipeline):
    raw = pipeline.model_dump()
    raw["graph"]["nodes"]["third"]["inputs"]["fresh"] = {"ref": "nodes.first.output.text"}
    spec = type(pipeline).model_validate(raw)
    plan = plan_debug(spec, ["third", "first"])
    assert any(e.source == "first" and e.target == "third" for e in plan.spec.graph.edges)
    result = await Runtime({}, builtin_registry()).run(compile_snapshot(plan.spec, {}),
        {"project": {"text": "new source"}, "upstream": {"second": {"content": "saved draft"}}})
    assert result.status == "succeeded", result.error
    assert result.output["third"] == {"fresh": "new source", "result": "saved draft"}
    assert not any(event["node_id"] == "graph/second" for event in result.events)


def test_invalid_selection_and_unneeded_services(pipeline):
    for selection in [[], ["absent"], ["first", "first"]]:
        with pytest.raises(ValueError):
            plan_debug(pipeline, selection)
    raw = pipeline.model_dump()
    raw["models"] = {"unused": {"binding": "unused"}}
    raw["tools"] = {"unused": {"plugin": "private-service"}}
    plan = plan_debug(type(pipeline).model_validate(raw), ["first"])
    assert plan.spec.models == plan.spec.tools == {}


async def test_debug_api_cached_outputs_revision_and_missing_input(tmp_path, pipeline):
    app = create_app(tmp_path)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://localhost") as client:
        assert (await client.post("/api/projects", json={"spec": pipeline.model_dump()})).status_code == 201
        payload = {"revision": 1, "nodes": ["second"]}
        description = (await client.post("/api/projects/debug-demo/debug/plan", json=payload)).json()
        assert description["boundary"][0]["source"] == "first"
        missing = await client.post("/api/projects/debug-demo/debug/runs", json={**payload, "input": {"text": "hello"}})
        assert missing.status_code == 422
        assert missing.json()["detail"]["field"] == "upstream"
        start = (await client.post("/api/projects/debug-demo/runs", json={"revision": 1, "input": {"text": "cached value"}})).json()
        for _ in range(100):
            record = (await client.get('/api/runs/' + start['run_id'])).json()
            if record["status"] == "succeeded":
                break
            await asyncio.sleep(0.01)
        assert record["status"] == "succeeded"
        detail = (await client.get(f"/api/runs/{start['run_id']}/nodes/graph/second")).json()
        assert detail["inputs"] == {"content": "cached value"}
        assert detail["output"] == {"content": "cached value"}
        assert detail["path"] == [] and detail["source_prefix"] == "graph"
        assert (await client.get(f"/api/runs/{start['run_id']}/nodes/graph/missing")).status_code == 404
        payload["source_run_id"] = start["run_id"]
        description = (await client.post("/api/projects/debug-demo/debug/plan", json=payload)).json()
        assert description["upstream"] == {"first": {"text": "cached value"}}
        response = await client.post("/api/projects/debug-demo/debug/runs", json={**payload, "input": {"text": "new value"}})
        assert response.status_code == 202, response.text
        for _ in range(100):
            record = (await client.get('/api/runs/' + response.json()['run_id'])).json()
            if record["status"] == "succeeded":
                break
            await asyncio.sleep(0.01)
        assert record["output"] == {"second": {"content": "cached value"}}
        assert not any(e["node_id"] == "graph/first" for e in record["events"])
        debug_id = record["run_id"]
        # Editing a prompt and debugging again preserves both the original inputs
        # and boundary values, instead of wrapping them in another project object.
        repeated = {**payload, "source_run_id": debug_id}
        replay = (await client.post("/api/projects/debug-demo/debug/plan", json=repeated)).json()
        assert replay["previous_input"] == {"text": "new value"}
        assert replay["upstream"] == {"first": {"text": "cached value"}}
        following = (await client.post("/api/projects/debug-demo/debug/plan",
                                       json={**repeated, "nodes": ["third"]})).json()
        assert following["upstream"] == {"second": {"content": "cached value"}}
        assert (await client.post("/api/projects/debug-demo/debug/plan", json={**payload, "revision": 9})).status_code == 409


async def test_debug_cannot_read_another_principals_run(tmp_path, pipeline):
    from evosprig.server.auth import Principal

    app = create_app(tmp_path, principals={"one": Principal("one"), "two": Principal("two")})
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://localhost") as client:
        run_id = None
        for token in ("one", "two"):
            client.headers["Authorization"] = "Bearer " + token
            assert (await client.post("/api/projects", json={"spec": pipeline.model_dump()})).status_code == 201
            if token == "one":
                run_id = (await client.post("/api/projects/debug-demo/runs", json={"revision": 1, "input": {"text": "private"}})).json()["run_id"]
        response = await client.post("/api/projects/debug-demo/debug/plan", json={"revision": 1, "nodes": ["second"], "source_run_id": run_id})
        assert response.status_code == 404
        assert (await client.get(f"/api/runs/{run_id}/nodes/graph/first")).status_code == 404


async def test_failed_nested_step_keeps_its_inputs_and_exact_debug_address(tmp_path):
    inner = {"entry": "check", "nodes": {"check": {
        "type": "transform", "inputs": {"text": {"ref": "input.item"}},
        "output_schema": {"type": "object", "properties": {"text": {"const": "accepted"}}},
    }}, "edges": [], "output": {"text": {"ref": "nodes.check.output.text"}}}
    spec = (Builder("inspect-steps", {"type": "object"}, {"type": "object"}, spec_version="0.3")
            .node("shots", "map", items={"value": ["accepted", "private wrong value"]}, body=inner,
                  carry={"value": {}}, output_schema={"type": "object"})
            .output(shots={"ref": "nodes.shots.output"}).build_spec())
    app = create_app(tmp_path)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://localhost") as client:
        assert (await client.post("/api/projects", json={"spec": spec.model_dump()})).status_code == 201
        run_id = (await client.post("/api/projects/inspect-steps/runs", json={"revision": 1, "input": {}})).json()["run_id"]
        for _ in range(200):
            record = (await client.get("/api/runs/" + run_id)).json()
            if record["status"] == "failed":
                break
            await asyncio.sleep(0.01)
        assert record["status"] == "failed"
        address = "graph/shots/item-1/check"
        assert record["error"]["node_id"] == address
        failures = [event for event in record["events"] if event["type"] == "node.failed"]
        assert [event["node_id"] for event in failures] == [address]
        assert "private wrong value" not in str(failures)
        detail = (await client.get(f"/api/runs/{run_id}/nodes/{address}")).json()
        assert detail["status"] == "failed" and detail["inputs"] == {"text": "private wrong value"}
        assert detail["path"] == ["shots", "body"] and detail["source_prefix"] == "graph/shots/item-1"
        prepared = (await client.post("/api/projects/inspect-steps/debug/plan", json={
            "revision": 1, "nodes": [detail["name"]], "path": detail["path"],
            "source_run_id": run_id, "source_prefix": detail["source_prefix"],
        })).json()
        assert prepared["previous_input"]["item"] == "private wrong value"
        assert prepared["previous_input"]["previous"] == {"text": "accepted"}


async def test_saved_nested_contexts_recover_carry_and_retake_inputs(tmp_path):
    from evosprig.core.debug import saved_debug_context
    from evosprig.plugins.sqlite_journal import SQLiteJournal

    loop_body = {"entry": "add", "nodes": {
        "add": {"type": "tool", "tool": "add", "inputs": {
            "a": {"ref": "input.value"}, "b": {"value": 1}}, "output_schema": {"type": "object"}}},
        "edges": [], "output": {"value": {"ref": "nodes.add.output.value"}}}
    body = {"entry": "first", "nodes": {
        "first": {"type": "tool", "tool": "add", "inputs": {
            "a": {"ref": "input.item"}, "b": {"ref": "input.previous.value"}}, "output_schema": {"type": "object"}},
        "takes": {"type": "loop", "inputs": {"value": {"ref": "nodes.first.output.value"}},
                  "body": loop_body, "max_iterations": 2, "output_schema": {"type": "object"}}},
        "edges": [{"source": "first", "target": "takes"}],
        "output": {"value": {"ref": "nodes.takes.output.value"}}}
    spec = (Builder("nested-debug", {"type": "object"}, {"type": "object"}, spec_version="0.3")
            .tool("add", "builtin.add").map("shots", items={"ref": "input.values"}, body=body,
                 inputs={}, output_schema={"type": "object"}, carry={"value": {"value": 0}})
            .output(results={"ref": "nodes.shots.output.items"}).execution(max_steps=200).build_spec())
    journal = SQLiteJournal(tmp_path / "nested.sqlite")
    result = await Runtime({}, builtin_registry(), journal=journal).run(compile_snapshot(spec, {}), {"values": [3, 7]})
    assert result.status == "succeeded", result.error
    record = journal.get(result.run_id)
    prefix, choices, inputs = saved_debug_context(spec, ["shots", "body"], record["checkpoint"], record["input"])
    assert prefix == "graph/shots/item-1"
    assert choices == ["graph/shots/item-0", "graph/shots/item-1"]
    assert inputs == {"item": 7, "index": 1, "context": {}, "previous": {"value": 5}}
    prefix, choices, inputs = saved_debug_context(spec, ["shots", "body", "takes", "body"],
                                                  record["checkpoint"], record["input"])
    assert inputs == {"value": 13}
    assert prefix == "graph/shots/item-1/takes/iteration-1"
    assert len(choices) == 4
    plan = plan_debug(spec, ["add"], ["shots", "body", "takes", "body"])
    isolated = await Runtime({}, builtin_registry()).run(compile_snapshot(plan.spec, {}), {"project": inputs, "upstream": {}})
    assert isolated.output["add"] == {"value": 14}
    assert isolated.usage["steps"] == 3
    with pytest.raises(ValueError, match="choose a saved"):
        saved_debug_context(spec, ["shots", "body"], record["checkpoint"], record["input"], "graph/shots/item-99")
