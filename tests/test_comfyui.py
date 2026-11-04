from copy import deepcopy

import pytest

from evosprig.config import make_tools
from evosprig.core.journal import Scope
from evosprig.core.runtime import Runtime
from evosprig.core.spec import AgentSpec
from evosprig.core.version import compile_snapshot
from evosprig.integrations.comfyui import ComfyWorkflow, WorkflowError
from evosprig.plugins.comfy_tools import ComfyNodeConfig, comfy_node_tool, import_comfy_spec


@pytest.fixture
def info():
    return {
        "Loader": {"input": {"required": {"model": [["first.safetensors", "second.safetensors"]]}}, "output": ["MODEL"]},
        "Lora": {"input": {"required": {"model": ["MODEL"], "strength": ["FLOAT", {"min": 0, "max": 2}]}}, "output": ["MODEL"]},
        "Render": {"input": {"required": {"model": ["MODEL"], "seed": ["INT", {"min": 0}], "steps": ["INT", {"min": 1, "max": 50}]}}, "output": ["IMAGE"]},
        "Save": {"input": {"required": {"images": ["IMAGE"], "prefix": ["STRING"]}}, "output": [], "output_node": True},
    }


@pytest.fixture
def ui():
    return {"version": 0.4, "extra": {"extension": ["keep"]}, "groups": [{"title": "Shot"}], "nodes": [
        {"id": 1, "type": "Loader", "widgets_values": ["first.safetensors"], "outputs": [{"type": "MODEL"}]},
        {"id": 2, "type": "Lora", "mode": 4, "widgets_values": [0.65], "inputs": [{"name": "model", "type": "MODEL", "link": 1}], "outputs": [{"type": "MODEL"}]},
        {"id": 3, "type": "SetNode", "widgets_values": ["model"], "inputs": [{"name": "MODEL", "link": 2}]},
        {"id": 4, "type": "GetNode", "widgets_values": ["model"]},
        {"id": 5, "type": "Render", "widgets_values": [42, "randomize", 12], "inputs": [{"name": "model", "link": 3}], "outputs": [{"type": "IMAGE"}]},
        {"id": 6, "type": "Save", "widgets_values": ["film"], "inputs": [{"name": "images", "link": 4}]},
        {"id": 7, "type": "Note", "widgets_values": ["keep this note"]},
    ], "links": [[1, 1, 0, 2, 0, "MODEL"], [2, 2, 0, 3, 0, "MODEL"], [3, 4, 0, 5, 0, "MODEL"], [4, 5, 0, 6, 0, "IMAGE"]]}


def test_roundtrip_preserves_layout_notes_disabled_nodes_and_extensions(ui, info):
    original = deepcopy(ui)
    workflow = ComfyWorkflow(ui, info)
    prompt = workflow.compile()
    assert set(prompt) == {"1", "5", "6"}
    assert prompt["5"]["inputs"] == {"model": ["1", 0], "seed": 42, "steps": 12}
    assert workflow.export() == original == ui
    workflow.set_enabled("2", True).set_input("2", "strength", 0.8).set_input("5", "steps", 14)
    assert workflow.compile()["5"]["inputs"]["model"] == ["2", 0]
    exported = workflow.export()
    assert exported["nodes"][1]["widgets_values"] == [0.8]
    assert exported["nodes"][4]["widgets_values"] == [42, "randomize", 14]
    assert exported["extra"] == original["extra"]
    assert ComfyWorkflow(exported, info).compile() == workflow.compile()


def test_missing_schema_does_not_guess_widget_order(ui):
    with pytest.raises(WorkflowError, match="object_info"):
        ComfyWorkflow(ui).compile()


def test_hidden_extension_widgets_keep_their_saved_value_without_server_fields():
    info = {"Slider": {"input": {"required": {"value": ["FLOAT"]},
                                     "hidden": {"output_type": [["float", "int"]], "unique_id": "UNIQUE_ID"}},
                         "output": ["*"]}}
    ui = {"nodes": [{"id": 1, "type": "Slider", "widgets_values": [3.7, "int"]}], "links": []}
    assert ComfyWorkflow(ui, info).compile()["1"]["inputs"] == {"value": 3.7, "output_type": "int"}


async def test_v3_combo_upload_and_format_metadata_are_not_tensor_ports():
    info = {
        "Audio": {"input": {"required": {"audio": ["COMBO", {"options": [], "audio_upload": True}]}}, "output": ["AUDIO"]},
        "Options": {"input": {"required": {"format": [["H3"], {"formats": {"H3": {"target_rate": 24, "frames": [17, 5]}}}],
                                             "tags": ["COMBO", {"options": ["slow", "wide"], "multiselect": True}]}}, "output": []},
    }
    ui = {"nodes": [{"id": 1, "type": "Audio", "widgets_values": ["voice.wav", None]},
                    {"id": 2, "type": "Options", "widgets_values": ["H3", ["slow", "wide"]]}], "links": []}
    workflow = ComfyWorkflow(ui, info)
    assert workflow.compile()["1"]["inputs"] == {"audio": "voice.wav"}
    assert workflow.compile()["2"]["inputs"] == {"format": "H3", "tags": ["slow", "wide"]}
    audio = comfy_node_tool(ComfyNodeConfig(name="audio", node_id="1", class_type="Audio", info=info["Audio"]))
    assert (await audio.invoke({"audio": "new-upload.wav"}))["prompt"]["1"]["inputs"]["audio"] == "new-upload.wav"
    options = comfy_node_tool(ComfyNodeConfig(name="options", node_id="2", class_type="Options", info=info["Options"]))
    assert (await options.invoke({"format": "H3", "tags": ["wide"]}))["prompt"]["2"]["inputs"]["tags"] == ["wide"]


async def test_codec_specific_saved_parameters_survive_import_and_native_execution(tmp_path):
    info = {"Encode": {"input": {"required": {"format": [["video/h264", "video/vp9"], {"formats": {
        "video/h264": [["crf", "INT", {"min": 0, "max": 100}], ["trim_to_audio", "BOOLEAN"]],
        "video/vp9": [["crf", "INT", {"min": 0, "max": 63}]],
    }}]}}, "output": []}}
    ui = {"nodes": [{"id": 1, "type": "Encode", "widgets_values": {
        "format": "video/h264", "crf": 80, "trim_to_audio": False, "videopreview": {"old_file": "unused.mp4"}
    }}], "links": []}
    workflow = ComfyWorkflow(ui, info)
    assert workflow.compile()["1"]["inputs"] == {"format": "video/h264", "crf": 80, "trim_to_audio": False}
    workflow.set_input("1", "crf", 19)
    imported = import_comfy_spec(workflow)
    spec = AgentSpec.model_validate(imported["spec"])
    tools = make_tools(tmp_path, Scope(spec.id), bindings=imported["bindings"]["tools"])
    result = await Runtime({}, tools).run(compile_snapshot(spec, {}), {})
    assert result.status == "succeeded", result.error
    assert result.output["comfy_1"]["1"]["inputs"]["crf"] == 19


async def test_vhs_video_reference_can_be_created_after_schema_snapshot(tmp_path):
    info = {"VHS_LoadVideo": {"name": "VHS_LoadVideo", "input": {"required": {"video": [[]]}}, "output": ["IMAGE"]}}
    ui = {"nodes": [{"id": 1, "type": "VHS_LoadVideo", "widgets_values": ["old.mp4"]}], "links": []}
    workflow = ComfyWorkflow(ui, info)
    workflow.set_input("1", "video", "new-tail.mp4")
    imported = import_comfy_spec(workflow)
    spec = AgentSpec.model_validate(imported["spec"])
    tools = make_tools(tmp_path, Scope(spec.id), bindings=imported["bindings"]["tools"])
    result = await Runtime({}, tools).run(compile_snapshot(spec, {}), {})
    assert result.status == "succeeded", result.error
    assert result.output["comfy_1"]["1"]["inputs"]["video"] == "new-tail.mp4"


async def test_recipe_describes_saved_controls_without_rendering(ui, info, tmp_path):
    import json
    import os
    import subprocess
    import sys

    from evosprig.exporters.python import export_python
    from evosprig.plugins.comfy_tools import ComfyRecipeConfig, comfy_recipe_tool
    from evosprig.sdk import Builder

    config = ComfyRecipeConfig(name="film.settings", kind="comfy_recipe_info", workflow=ui,
                              object_info=info, outputs=["6"], parameters={
                                  "steps": {"node_id": "5", "input_name": "steps", "schema": {"maximum": 16}},
                                  "adapter": {"node_id": "2", "kind": "enabled"}})
    result = await comfy_recipe_tool(config).invoke({})
    assert result["defaults"] == {"steps": 12, "adapter": False}
    assert result["controls"]["properties"]["steps"]["allOf"][1]["maximum"] == 16
    result["defaults"]["steps"] = 99
    assert (await comfy_recipe_tool(config).invoke({}))["defaults"]["steps"] == 12
    spec = (Builder("settings", {"type": "object"}, {"type": "object"})
            .tool("settings", "film.settings").node("read", "tool", tool="settings", inputs={}, output_schema={"type": "object"})
            .output(settings={"ref": "nodes.read.output"}).build_spec())
    target = tmp_path / "export"
    export_python(compile_snapshot(spec, {}), target, tool_bindings={"film.settings": config.model_dump(mode="json")})
    completed = subprocess.run([sys.executable, "app.py", "--input", "{}"], cwd=target,
                               env={**os.environ, "PYTHONPATH": str(target / "src")}, capture_output=True, text=True, check=True)
    assert json.loads(completed.stdout)["output"]["settings"]["defaults"]["steps"] == 12


def test_unknown_weights_bounds_and_connected_edits_rejected(ui, info):
    from jsonschema import ValidationError

    workflow = ComfyWorkflow(ui, info)
    with pytest.raises(ValidationError):
        workflow.set_input("1", "model", "missing.safetensors")
    with pytest.raises(ValidationError):
        workflow.set_input("5", "steps", 0)
    with pytest.raises(WorkflowError, match="connected"):
        workflow.set_input("5", "model", ["1", 0])


@pytest.mark.parametrize("change,match", [
    (lambda doc: doc["nodes"][3].update(widgets_values=["missing"]), "expected one SetNode"),
    (lambda doc: doc["nodes"][0].update(mode=2), "muted"),
    (lambda doc: doc["links"].pop(0), "missing link"),
    (lambda doc: doc["nodes"].append(deepcopy(doc["nodes"][0])), "duplicate node"),
])
def test_invalid_connections_are_actionable(ui, info, change, match):
    change(ui)
    with pytest.raises(WorkflowError, match=match):
        ComfyWorkflow(ui, info).compile()


def test_api_prompt_roundtrip_and_reachable_outputs(ui, info):
    prompt = ComfyWorkflow(ui, info).compile()
    prompt["unrelated"] = {"class_type": "Loader", "inputs": {"model": "second.safetensors"}}
    workflow = ComfyWorkflow({"prompt": prompt, "client_id": "sample"}, info)
    assert workflow.export()["client_id"] == "sample"
    assert set(workflow.compile(["6"])) == {"1", "5", "6"}
    prompt["1"]["inputs"]["model"] = ["5", 0]
    with pytest.raises(WorkflowError, match="cycle"):
        ComfyWorkflow(prompt, info).compile()


def test_api_export_creates_an_editable_canvas_with_seed_and_links(ui, info):
    prompt = ComfyWorkflow(ui, info).compile()
    canvas = ComfyWorkflow(prompt, info).export_ui()
    restored = ComfyWorkflow(canvas, info)
    assert len(canvas["nodes"]) == 3 and len(canvas["links"]) == 2
    render = next(node for node in canvas["nodes"] if node["type"] == "Render")
    assert render["widgets_values"] == [42, "fixed", 12]
    restored.set_input(str(render["id"]), "steps", 15)
    result = restored.compile()
    assert result[str(render["id"])]["inputs"]["steps"] == 15
    assert next(node for node in result.values() if node["class_type"] == "Loader")["inputs"]["model"] == "first.safetensors"
    assert ComfyWorkflow(ui, info).export_ui() == ui


def test_api_export_handles_force_input_literals_dynamic_widgets_and_uploads():
    info = {
        "Image": {"input": {"required": {"image": [[], {"image_upload": True}]}}, "output": ["IMAGE"]},
        "Scale": {"input": {"required": {"image": ["IMAGE"], "amount": ["FLOAT", {"forceInput": True}]}}, "output": ["IMAGE"]},
        "Save": {"input": {"required": {"images": ["IMAGE"], "format": [["mp4"], {
            "formats": {"mp4": [["crf", "INT", {"default": 19}]]}}]}}, "output": []},
    }
    prompt = {"image": {"class_type": "Image", "inputs": {"image": "new.png"}},
              "scale": {"class_type": "Scale", "inputs": {"image": ["image", 0], "amount": 1.5}},
              "save": {"class_type": "Save", "inputs": {"images": ["scale", 0], "format": "mp4", "crf": 17}}}
    canvas = ComfyWorkflow(prompt, info).export_ui()
    assert len(canvas["nodes"]) == 4
    result = ComfyWorkflow(canvas, info).compile()
    assert result["1"]["inputs"]["image"] == "new.png"
    assert result["2"]["inputs"] == {"image": ["1", 0], "amount": 1.5}
    assert result["3"]["inputs"]["crf"] == 17


def test_source_port_types_checked(ui, info):
    workflow = ComfyWorkflow(ui, info)
    workflow.links["4"] = ("1", 0, "6", 0, "IMAGE")
    with pytest.raises(WorkflowError, match="expects IMAGE, got MODEL"):
        workflow.compile()


async def test_numeric_union_inputs_accept_typed_tool_handles():
    info = {"Number": {"input": {"required": {"value": ["FLOAT"]}}, "output": ["FLOAT"]},
            "Expression": {"input": {"required": {"a": ["FLOAT,INT,BOOLEAN"]}}, "output": ["INT"]}}
    prompt = {"1": {"class_type": "Number", "inputs": {"value": 12}},
              "2": {"class_type": "Expression", "inputs": {"a": ["1", 0]}}}
    assert ComfyWorkflow(prompt, info).compile() == prompt
    source = comfy_node_tool(ComfyNodeConfig(name="number", node_id="1", class_type="Number", info=info["Number"]))
    expression = comfy_node_tool(ComfyNodeConfig(name="expression", node_id="2", class_type="Expression", info=info["Expression"]))
    handle = (await source.invoke({"value": 12}))["output_0"]
    assert (await expression.invoke({"a": handle}))["prompt"]["2"]["inputs"]["a"] == ["1", 0]


async def test_imported_nodes_execute_with_native_runtime(ui, info, tmp_path):
    imported = import_comfy_spec(ComfyWorkflow(ui, info))
    spec = AgentSpec.model_validate(imported["spec"])
    tools = make_tools(tmp_path, Scope(spec.id), bindings=imported["bindings"]["tools"])
    result = await Runtime({}, tools).run(compile_snapshot(spec, {}), {})
    assert result.status == "succeeded", result.error
    last = imported["node_map"]["6"]
    assert result.output[last]["5"]["inputs"]["steps"] == 12
    assert result.output[last]["6"]["inputs"]["images"] == ["5", 0]


async def test_import_budget_covers_both_nodes_and_tool_operations(tmp_path):
    info = {"Number": {"input": {"required": {"value": ["INT"]}}, "output": ["INT"]},
            "Pass": {"input": {"required": {"value": ["INT", {"forceInput": True}]}}, "output": ["INT"]}}
    prompt = {"0": {"class_type": "Number", "inputs": {"value": 42}}}
    prompt.update({str(i): {"class_type": "Pass", "inputs": {"value": [str(i - 1), 0]}} for i in range(1, 24)})
    imported = import_comfy_spec(ComfyWorkflow(prompt, info))
    spec = AgentSpec.model_validate(imported["spec"])
    registry = make_tools(tmp_path, Scope(spec.id), bindings=imported["bindings"]["tools"])
    result = await Runtime({}, registry).run(compile_snapshot(spec, {}), {})
    assert result.status == "succeeded", result.error
    assert result.output[imported["node_map"]["23"]] == prompt


async def test_node_handles_reject_conflicting_definitions(info):
    from evosprig.core.protocols import ToolFeedbackError

    descriptor = {"input": {"required": {"left": ["MODEL"], "right": ["MODEL"]}}, "output": ["MODEL"]}
    tool = comfy_node_tool(ComfyNodeConfig(name="pair", node_id="pair", class_type="Pair", info=descriptor))
    handle = {"node_id": "source", "slot": 0, "type": "MODEL", "prompt": {"source": {"class_type": "Loader", "inputs": {"model": "first.safetensors"}}}}
    other = deepcopy(handle)
    other["prompt"]["source"]["inputs"]["model"] = "second.safetensors"
    with pytest.raises(ToolFeedbackError, match="conflicting"):
        await tool.invoke({"left": handle, "right": other})


def test_rewire_export_preserves_extension_data_and_resolves_new_links(ui, info):
    workflow = ComfyWorkflow(ui, info).set_enabled("2", True)
    workflow.connect("5", "model", "1", 0)
    assert workflow.compile()["5"]["inputs"]["model"] == ["1", 0]
    restored = ComfyWorkflow(workflow.export(), info)
    assert restored.compile() == workflow.compile()
    assert restored.export()["extra"] == ui["extra"]
    with pytest.raises(WorkflowError, match="expects IMAGE"):
        restored.connect("6", "images", "1", 0)


def test_v3_dynamic_options_and_reference_arrays_preserve_widget_alignment():
    info = {"Patch": {"input": {"required": {
        "selection": ["COMFY_DYNAMICCOMBO_V3", {"options": [
            {"key": "fast", "inputs": {"required": {"tau": ["FLOAT", {"default": 1.3}]}}},
            {"key": "precise", "inputs": {"required": {"ratio": ["FLOAT", {"default": 10}], "iterations": ["INT", {"default": 3}]}}},
        ]}], "verbose": ["BOOLEAN", {"default": False}],
    }, "optional": {"references": ["COMFY_AUTOGROW_V3", {"template": {"prefix": "image_", "min": 0, "max": 3, "input": {"required": {"image": ["IMAGE"]}}}}]}}, "output": ["MODEL"]}}
    ui = {"nodes": [{"id": 1, "type": "Patch", "widgets_values": ["fast", 1.3, True]}], "links": []}
    workflow = ComfyWorkflow(ui, info)
    assert workflow.compile()["1"]["inputs"] == {"selection": "fast", "selection.tau": 1.3, "verbose": True}
    workflow.set_input("1", "selection", "precise")
    assert workflow.export()["nodes"][0]["widgets_values"] == ["precise", 10, 3, True]
    assert workflow.compile()["1"]["inputs"]["selection.iterations"] == 3
    inputs = workflow.describe()[0]["inputs"]
    assert "references.image_2" in inputs


def test_bypassed_reference_loaders_leave_optional_inputs_unbound():
    info = {
        "Image": {"input": {"required": {"file": [["frame.png"]]}}, "output": ["IMAGE"]},
        "Render": {"input": {"optional": {"reference": ["IMAGE"]}}, "output": ["IMAGE"]},
    }
    document = {"nodes": [
        {"id": 1, "type": "Image", "mode": 4, "widgets_values": ["missing.png"], "outputs": [{"type": "IMAGE"}]},
        {"id": 2, "type": "Render", "inputs": [{"name": "reference", "link": 1}]},
        {"id": 3, "type": "UnknownUnusedExtension", "widgets_values": []},
    ], "links": [[1, 1, 0, 2, 0, "IMAGE"]]}
    workflow = ComfyWorkflow(document, info)
    assert workflow.compile(["2"]) == {"2": {"class_type": "Render", "inputs": {}, "_meta": {"title": "Render"}}}
    info["Render"]["input"] = {"required": {"reference": ["IMAGE"]}}
    with pytest.raises(WorkflowError, match="provide reference"):
        ComfyWorkflow(document, info).compile(["2"])


async def test_recipe_audio_video_slots_are_independent_and_reset_between_takes():
    from evosprig.plugins.comfy_tools import ComfyRecipeConfig, comfy_recipe_tool

    info = {
        "Audio": {"input": {"required": {"audio": [["None"], {"audio_upload": True}]}}, "output": ["AUDIO"]},
        "Video": {"input": {"required": {"video": [["None"], {"video_upload": True}]}}, "output": ["VIDEO"]},
        "Render": {"input": {"optional": {"audio": ["AUDIO"], "video": ["VIDEO"]}}, "output": []},
    }
    ui = {"nodes": [
        {"id": 1, "type": "Audio", "mode": 4, "widgets_values": ["None"], "outputs": [{"type": "AUDIO"}]},
        {"id": 2, "type": "Video", "mode": 4, "widgets_values": ["None"], "outputs": [{"type": "VIDEO"}]},
        {"id": 3, "type": "Render", "inputs": [{"name": "audio", "link": 1}, {"name": "video", "link": 2}]},
    ], "links": [[1, 1, 0, 3, 0, "AUDIO"], [2, 2, 0, 3, 1, "VIDEO"]]}
    config = ComfyRecipeConfig(name="render", workflow=ui, object_info=info, outputs=["3"],
                              audio_slots=[{"node_id": "1", "input_name": "audio"}],
                              video_slots=[{"node_id": "2", "input_name": "video"}])
    tool = comfy_recipe_tool(config)
    first = await tool.invoke({"reference_audio": ["voice.wav"], "reference_videos": ["tail.mp4"]})
    assert first["prompt"]["1"]["inputs"]["audio"] == "voice.wav"
    assert first["prompt"]["2"]["inputs"]["video"] == "tail.mp4"
    second = await tool.invoke({"reference_audio": [], "reference_videos": []})
    assert second["prompt"]["3"]["inputs"] == {}
    assert set(second["prompt"]) == {"3"}


async def test_recipe_controls_keep_defaults_and_isolate_each_shot(ui, info):
    from jsonschema import ValidationError

    from evosprig.plugins.comfy_tools import ComfyRecipeConfig, comfy_recipe_tool

    config = ComfyRecipeConfig(name="film.recipe", workflow=ui, object_info=info, outputs=["6"], parameters={
        "action": {"node_id": "2", "kind": "enabled"},
        "strength": {"node_id": "2", "input_name": "strength", "schema": {"maximum": 1}},
        "seed": {"node_id": "5", "input_name": "seed"},
    })
    tool = comfy_recipe_tool(config)
    first = await tool.invoke({"controls": {"action": True, "strength": 0.7, "seed": 99}})
    assert first["prompt"]["2"]["inputs"]["strength"] == 0.7
    assert first["prompt"]["5"]["inputs"]["steps"] == 12
    second = await tool.invoke({})
    assert "2" not in second["prompt"]
    assert second["prompt"]["5"]["inputs"]["seed"] == 42
    assert config.workflow == ui
    with pytest.raises(ValidationError):
        await tool.invoke({"controls": {"strength": 1.2}})
    with pytest.raises(ValidationError):
        await tool.invoke({"controls": {"unlisted_node": "change"}})


async def test_recipe_checks_connected_controls_before_any_render(ui, info):
    from evosprig.plugins.comfy_tools import ComfyRecipeConfig, comfy_recipe_tool

    info["Slider"] = {"input": {"required": {"value": ["FLOAT"]}}, "output": ["FLOAT"]}
    ui["nodes"].append({"id": 8, "type": "Slider", "widgets_values": [0.65],
                        "outputs": [{"type": "FLOAT"}]})
    ui["nodes"][1]["inputs"].append({"name": "strength", "link": 5, "type": "FLOAT"})
    ui["links"].append([5, 8, 0, 2, 1, "FLOAT"])
    config = ComfyRecipeConfig(name="film.recipe", workflow=ui, object_info=info, outputs=["6"], parameters={
        "strength": {"node_id": "2", "input_name": "strength"},
        "adapter": {"node_id": "2", "kind": "enabled"},
    })
    with pytest.raises(ValueError, match="connected input"):
        comfy_recipe_tool(config)
    config.parameters["strength"] = config.parameters["strength"].model_copy(
        update={"node_id": "8", "input_name": "value"})
    result = await comfy_recipe_tool(config).invoke({"controls": {"adapter": True, "strength": 0.8}})
    assert result["prompt"]["8"]["inputs"]["value"] == 0.8
    assert result["prompt"]["2"]["inputs"]["strength"] == ["8", 0]


@pytest.mark.parametrize("controls", [{"adapter": False, "action": True}, {"action": True, "adapter": False}])
async def test_individual_switch_overrides_group_preset_in_any_json_order(ui, info, controls):
    from evosprig.plugins.comfy_tools import ComfyRecipeConfig, comfy_recipe_tool

    tool = comfy_recipe_tool(ComfyRecipeConfig(name="film.recipe", workflow=ui, object_info=info, outputs=["6"], parameters={
        "action": {"node_id": "2", "also_nodes": ["5"], "kind": "enabled"},
        "adapter": {"node_id": "2", "kind": "enabled"},
    }))
    result = await tool.invoke({"controls": controls})
    assert "2" not in result["prompt"] and "5" in result["prompt"]


async def test_recipe_new_uploaded_images_and_unused_reference_slots():
    from evosprig.plugins.comfy_tools import ComfyRecipeConfig, comfy_recipe_tool

    info = {
        "Image": {"input": {"required": {"image": [["old.png"], {"image_upload": True}]}}, "output": ["IMAGE"]},
        "Render": {"input": {"optional": {"first": ["IMAGE"], "second": ["IMAGE"]}}, "output": ["IMAGE"]},
    }
    ui = {"nodes": [
        {"id": 1, "type": "Image", "widgets_values": ["old.png"], "outputs": [{"type": "IMAGE"}]},
        {"id": 2, "type": "Image", "widgets_values": ["old.png"], "outputs": [{"type": "IMAGE"}]},
        {"id": 3, "type": "Render", "inputs": [{"name": "first", "link": 1}, {"name": "second", "link": 2}]},
    ], "links": [[1, 1, 0, 3, 0, "IMAGE"], [2, 2, 0, 3, 1, "IMAGE"]]}
    tool = comfy_recipe_tool(ComfyRecipeConfig(name="film.references", workflow=ui, object_info=info,
                                             outputs=["3"], reference_slots=[{"node_id": "1"}, {"node_id": "2"}]))
    result = await tool.invoke({"reference_images": ["generated.png"]})
    assert set(result["prompt"]) == {"1", "3"}
    assert result["prompt"]["1"]["inputs"]["image"] == "generated.png"
    assert result["prompt"]["3"]["inputs"] == {"first": ["1", 0]}
    assert len((await tool.invoke({"reference_images": ["a.png", "b.png"]}))["prompt"]) == 3


async def test_studio_import_run_edit_export_and_scoped_bindings(ui, info, tmp_path):
    import asyncio

    import httpx

    from evosprig.server.app import create_app

    app = create_app(tmp_path)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://localhost") as client:
        response = await client.post("/api/comfy/import", json={"workflow": ui, "object_info": info, "project_id": "comfy-demo"})
        assert response.status_code == 201, response.text
        document = response.json()
        prepared = await client.post("/api/projects/comfy-demo/runs", json={"input": {}, "revision": 1})
        assert prepared.status_code == 202, prepared.text
        for _ in range(100):
            result = (await client.get('/api/runs/' + prepared.json()['run_id'])).json()
            if result["status"] == "succeeded":
                break
            await asyncio.sleep(0.01)
        assert result["status"] == "succeeded", result
        render = next(node for node in document["spec"]["graph"]["nodes"].values() if "steps" in node["inputs"])
        render["inputs"]["steps"] = {"value": 14}
        saved = await client.put("/api/projects/comfy-demo", json={"spec": document["spec"], "resources": {}, "layout": document["layout"], "revision": 1})
        assert saved.status_code == 200
        exported = (await client.get("/api/projects/comfy-demo/comfy/export")).json()
        assert exported["nodes"][4]["widgets_values"] == [42, "randomize", 14]
        assert exported["nodes"][1]["mode"] == 4
        assert exported["extra"] == ui["extra"]
        assert (await client.post("/api/projects/comfy-demo/export")).status_code == 200


async def test_recipe_canvas_keeps_all_nodes_and_persists_valid_edits_per_project(tmp_path, ui, info):
    import asyncio
    import json

    import httpx
    import yaml

    from evosprig.plugins.comfy_tools import ComfyRecipeConfig
    from evosprig.sdk import Builder
    from evosprig.server.app import create_app

    config = ComfyRecipeConfig(name="film.recipe", workflow=ui, object_info=info, outputs=["6"],
                              parameters={"steps": {"node_id": "5", "input_name": "steps"}})
    profile = tmp_path / "profile.yaml"
    profile.write_text(yaml.safe_dump({"models": {}, "tools": {
        "film.recipe": config.model_dump(mode="json"),
        "film.settings": {**config.model_dump(mode="json"), "name": "film.settings", "kind": "comfy_recipe_info"},
    }}))
    app = create_app(tmp_path / "workspace", profile=profile)
    for name in ["first", "second"]:
        b = Builder(name, {}, {}).tool("recipe", "film.recipe").tool("settings", "film.settings")
        b.node("settings", "tool", tool="settings", inputs={}, output_schema={})
        b.node("prepare", "tool", tool="recipe", inputs={"controls": {"value": {}}}, output_schema={})
        b.edge("settings", "prepare").output(prompt={"ref": "nodes.prepare.output.prompt"}, defaults={"ref": "nodes.settings.output.defaults"})
        app.state.projects.create(b.build_spec(), resources={})
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://localhost") as client:
            assert (await client.get("/api/projects/first/recipes")).json() == [{"name": "film.recipe", "node_count": 7}]
            before = (await client.get("/api/projects/first/recipes/film.recipe")).json()
            assert len(before["nodes"]) == 7
            patch = {"revision": 1, "workflow_hash": before["workflow_hash"], "changes": {"5": {"inputs": {"steps": 14}}, "2": {"enabled": True}}}
            invalid = {**patch, "changes": {"5": {"inputs": {"steps": 500}}}}
            assert (await client.post("/api/projects/first/recipes/film.recipe", json=invalid)).status_code == 422
            saved = await client.post("/api/projects/first/recipes/film.recipe", json=patch)
            assert saved.status_code == 200, saved.text
            assert saved.json()["project"]["revision"] == 2
            assert (await client.post("/api/projects/first/recipes/film.recipe", json=patch)).status_code == 409
            after = (await client.get("/api/projects/first/recipes/film.recipe")).json()
            assert after["workflow"]["extra"] == ui["extra"]
            assert after["workflow"]["nodes"][-1] == ui["nodes"][-1]
            assert after["nodes"][1]["mode"] == 0
            assert (await client.get("/api/projects/second/recipes/film.recipe")).json()["workflow"] == ui
            run = await client.post("/api/projects/first/runs", json={"input": {}, "revision": 2})
            identifier = run.json()["run_id"]
            for _ in range(200):
                record = (await client.get("/api/runs/" + identifier)).json()
                if record["status"] not in {"queued", "running", "waiting_external"}:
                    break
                await asyncio.sleep(.01)
            assert record["status"] == "succeeded", record
            assert record["output"]["prompt"]["5"]["inputs"]["steps"] == 14
            assert record["output"]["defaults"]["steps"] == 14
            cursor = record["events"][2]["sequence"]
            incremental = (await client.get(f"/api/runs/{identifier}?after={cursor}")).json()
            assert incremental["events"] == [e for e in record["events"] if e["sequence"] > cursor]
            assert json.loads(json.dumps(ui)) == config.workflow
