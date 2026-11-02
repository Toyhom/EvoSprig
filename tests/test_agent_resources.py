import json

import pytest
from test_evaluation import suite
from test_evolution_methods import TaskModel

from evosprig.core.journal import Scope
from evosprig.core.protocols import ModelResponse, Usage
from evosprig.core.runtime import Runtime
from evosprig.core.spec import AgentSpec, Node
from evosprig.core.version import compile_snapshot
from evosprig.evaluation.budget import ExperimentBudget
from evosprig.evolution.gate import ReleaseGate
from evosprig.evolution.study import StudyConfig, execute_study
from evosprig.plugins.mock import MockProvider
from evosprig.plugins.openai_compatible import Connection, OpenAICompatibleProvider
from evosprig.plugins.sqlite_studies import StudyStore
from evosprig.sdk import Builder


def agent():
    return (
        Builder("skill-agent", {}, {}, spec_version="0.3")
        .model("main", "main")
        .resource("prompt", "prompts/main.md")
        .skill("procedure", "skills/procedure.md")
        .node(
            "answer",
            "agent",
            model="main",
            instructions={"resource": "prompt"},
            skills=["procedure"],
            temperature=0.4,
            top_p=0.9,
            output_schema={},
        )
        .output(answer={"ref": "nodes.answer.output.text"})
        .build_spec()
    )


async def test_attached_skill_and_sampling_reach_provider_and_frozen_version():
    spec = agent()
    model = MockProvider([ModelResponse(text="done")])
    version = compile_snapshot(spec, {"prompt": "Do the task.", "procedure": "Check the inputs."})
    result = await Runtime({"main": model}).run(version, {})
    assert result.status == "succeeded"
    request = model.requests[0]
    assert (
        request.messages[0]["content"] == "Do the task.\n\n## Skill: procedure\nCheck the inputs."
    )
    adapter = OpenAICompatibleProvider(
        Connection(base_url="https://example.com", model="test", api_key_env="TEST_KEY")
    )
    assert adapter._payload(request)["temperature"] == 0.4
    assert adapter._payload(request)["top_p"] == 0.9
    assert AgentSpec.model_validate_json(version.spec_json).graph.nodes["answer"].skills == [
        "procedure"
    ]
    changed = compile_snapshot(spec, {"prompt": "Do the task.", "procedure": "Check dates too."})
    assert changed.version_id != version.version_id


async def test_selected_skill_is_optimized_without_rewriting_prompt_or_graph(tmp_path):
    spec = agent()
    base = compile_snapshot(spec, {"prompt": "Do the task.", "procedure": "Explain the answer."})
    data = suite()
    for split in ("search", "selection", "release", "test"):
        for sample in getattr(data, split):
            sample.expected = "ok"
    proposer = MockProvider(
        [
            ModelResponse(
                text=json.dumps({"procedure": "Return the exact label ok."}), usage=Usage(20, 10)
            )
        ]
    )
    store = StudyStore(tmp_path / "studies.sqlite")
    scope = Scope(spec.id)
    store.put(scope, base)
    result = await execute_study(
        base=base,
        suite=data,
        config=StudyConfig(
            method="opro",
            allowed_resources=["procedure"],
            rounds=1,
            gate=ReleaseGate(min_samples=1),
            budget=ExperimentBudget(max_evaluations=12, max_model_calls=20),
        ),
        models={"main": TaskModel()},
        proposer=proposer,
        workspace=tmp_path,
        store=store,
        scope=scope,
        job_id="skill-search",
    )
    selected = store.get(scope, result["selected_version"])
    assert selected.resources["procedure"] == "Return the exact label ok."
    assert selected.resources["prompt"] == base.resources["prompt"]
    assert selected.spec_json == base.spec_json
    assert result["reports"]["test"]["selected"]["score"] == 1
    assert store.release(scope)["version_id"] is None
    assert "sealed-secret" not in str(proposer.requests)


def test_skill_references_and_model_parameters_are_validated_without_legacy_hash_changes():
    spec = agent()
    raw = spec.model_dump()
    raw["resources"]["procedure"]["role"] = "prompt"
    with pytest.raises(ValueError, match="skill resources"):
        AgentSpec.model_validate(raw)
    for patch in (
        {"skills": ["procedure", "procedure"]},
        {"temperature": float("nan")},
        {"top_p": 0},
    ):
        with pytest.raises(ValueError):
            Node.model_validate({**spec.graph.nodes["answer"].model_dump(), **patch})
    with pytest.raises(ValueError, match="model or agent"):
        Node(type="transform", output_schema={}, skills=["procedure"])
    legacy = (
        Builder("legacy", {}, {})
        .model("main", "main")
        .node("answer", "model", model="main", output_schema={})
        .build_spec()
    )
    canonical = json.loads(legacy.canonical())
    assert not {"skills", "temperature", "top_p"} & canonical["graph"]["nodes"]["answer"].keys()
    assert AgentSpec.model_validate_json(legacy.canonical()).spec_hash == legacy.spec_hash


def test_builder_does_not_silently_replace_a_skill_with_a_prompt():
    builder = Builder("resources", {}, {}).skill("review", "skills/review.md")
    with pytest.raises(ValueError, match="duplicate resource"):
        builder.resource("review", "prompts/review.md")


def test_used_resources_includes_nested_skills_and_excludes_unattached_files():
    raw = agent().model_dump()
    body = raw["graph"]
    raw["graph"] = {
        "entry": "team",
        "nodes": {"team": {"type": "loop", "body": body, "output_schema": {}}},
        "edges": [],
        "output": {},
    }
    raw["resources"]["unused"] = {"path": "skills/unused.md", "role": "skill"}
    spec = AgentSpec.model_validate(raw)
    assert spec.used_resources() == {"prompt", "procedure"}
