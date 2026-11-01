import json
import runpy

import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from evosprig.core.spec import AgentSpec
from evosprig.core.version import compile_agent
from evosprig.server.canvas import from_canvas, to_canvas


def test_builder_canvas_and_yaml_roundtrip(spec, example_root):
    built = runpy.run_path(str(example_root / "build_agent.py"))["spec"]
    assert built.spec_hash == spec.spec_hash
    canvas = to_canvas(built)
    canvas["nodes"][0]["position"] = {"x": 901, "y": -100}
    restored, layout = from_canvas(built, canvas)
    assert restored.spec_hash == built.spec_hash
    assert layout["measure"]["x"] == 901


def test_schema_matches_model(spec, example_root):
    frozen = json.loads((example_root.parents[1] / "spec/agent-spec-0.1.schema.json").read_text())
    assert frozen == AgentSpec.model_json_schema()
    Draft202012Validator(frozen).validate(spec.model_dump())


@pytest.mark.parametrize(
    "mutation",
    [
        lambda data: data.update(spec_version="9"),
        lambda data: data.update(memory={}),
        lambda data: data["graph"]["nodes"]["assistant"].update(type="loop"),
        lambda data: data["graph"]["nodes"]["assistant"].update(model="missing"),
        lambda data: data["graph"].update(edges=[]),
        lambda data: data["graph"]["edges"].append({"source": "assistant", "target": "measure"}),
        lambda data: data["graph"]["nodes"]["measure"]["inputs"].update(
            text={"ref": "nodes.assistant.output.text"}
        ),
        lambda data: data["graph"]["output"].update(answer={"ref": "nodes.missing.output.text"}),
        lambda data: data.update(input_schema={"$ref": "https://example.com/schema"}),
        lambda data: data.update(input_schema={"type": "not-a-json-type"}),
        lambda data: data["execution"].update(max_model_calls=-1),
    ],
)
def test_invalid_contracts_rejected(spec, mutation):
    data = spec.model_dump()
    mutation(data)
    with pytest.raises((ValidationError, ValueError)):
        AgentSpec.model_validate(data)


def test_version_freezes_resources_and_spec(spec, example_root, tmp_path):
    root = tmp_path
    (root / "prompts").mkdir()
    path = root / "prompts/assistant.md"
    path.write_text("Original prompt")
    first = compile_agent(spec, root)
    path.write_text("Revised prompt")
    second = compile_agent(spec, root)
    assert first.version_id != second.version_id
    assert first.resources["instructions"] == "Original prompt"
    copy = first.spec
    copy.id = "edited"
    assert first.spec.id == "hello"


@pytest.mark.parametrize(
    "path",
    ["../private.md", "/etc/passwd", ".env", "project-private/plan.md", "prompts/../../secret"],
)
def test_resource_containment(spec, tmp_path, path):
    spec.resources["instructions"].path = path
    with pytest.raises(ValueError):
        compile_agent(spec, tmp_path)


def test_resource_symlink_and_credentials(spec, tmp_path):
    (tmp_path / "prompts").mkdir()
    link = tmp_path / "prompts/assistant.md"
    link.symlink_to("/etc/hostname")
    with pytest.raises(ValueError, match="symlink"):
        compile_agent(spec, tmp_path)
    link.unlink()
    link.write_text("sk-" + "x" * 24)
    with pytest.raises(ValueError, match="credential"):
        compile_agent(spec, tmp_path)
