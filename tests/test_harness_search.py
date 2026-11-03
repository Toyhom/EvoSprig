import copy
import json

import pytest
from test_evaluation import suite, version
from test_evolution_methods import TaskModel

from evosprig.core.journal import Scope
from evosprig.core.protocols import ModelResponse, Usage
from evosprig.core.spec import AgentSpec
from evosprig.core.version import compile_snapshot
from evosprig.evaluation.budget import ExperimentBudget
from evosprig.evolution.branch_search import preservation
from evosprig.evolution.harness_common import HarnessOptions
from evosprig.evolution.harness_search import rrsi_admit
from evosprig.evolution.skill_search import END, START, apply_patch
from evosprig.evolution.space import SearchSpace
from evosprig.evolution.study import StudyConfig, execute_study
from evosprig.plugins.mock import MockProvider
from evosprig.plugins.sqlite_studies import StudyStore


class MethodProposer(MockProvider):
    """Protocol fixtures exercise actual runtime evaluations and each method's decisions."""

    def __init__(self, method):
        super().__init__()
        self.method, self.tree_actions = method, 0

    async def complete(self, request):
        self.requests.append(request)
        instruction = request.messages[0]["content"]
        payload = json.loads(request.messages[1]["content"])
        if "Propose bounded edits" in instruction:
            value = [{"resource": "prompt", "op": "append", "text": "Return the exact label ok."}]
        elif "Compare earlier and current" in instruction:
            value = {
                "meta": "Prefer short procedures.",
                "guidance": {"prompt": "Check the requested format."},
            }
        elif "Extract a reusable procedure" in instruction:
            value = {"trigger": "train question", "lesson": "Return the exact label ok."}
        elif "Compile task memories" in instruction:
            value = (
                []
                if payload["level"] == "general"
                else [
                    {
                        "resource": "prompt",
                        "id": "precise",
                        "trigger": "train select question",
                        "body": "Return the exact label ok.",
                        "sources": ["s1"],
                        "op": "upsert",
                    }
                ]
            )
        elif "Describe independent mechanisms" in instruction:
            value = [
                {
                    "id": "format",
                    "hypothesis": "Concise output satisfies the interface",
                    "targets": list(payload["diff"]),
                    "predicted_fixes": ["s1"],
                    "at_risk": [],
                }
            ]
        elif "Review the complete" in instruction:
            value = {"accept": True, "reason": "Preserves the task contract."}
        elif "Invent a new agent design" in instruction:
            value = {
                "name": "Concise answer",
                "design": "Explicit format",
                "critique": "Keep task input",
                "revision": "Use concise format instructions",
            }
        elif "Coordinate a hypothesis tree" in instruction:
            sequence = [
                {"action": "expand", "node": "ROOT", "hypotheses": ["Output contracts"]},
                {"action": "expand", "node": "H1", "hypotheses": ["Concise answers"]},
                {"action": "select", "node": "H2"},
            ]
            value = sequence[self.tree_actions]
            self.tree_actions += 1
        elif "insight" in instruction:
            value = {"insight": "Explicit format guidance improved task completion."}
        elif "Summarize reusable lessons" in instruction:
            value = {"lesson": "Keep the explicit output contract."}
        elif "Diagnose reusable" in instruction:
            value = {
                "tasks": [{"task_id": "s1", "cause": "Verbose output"}],
                "summary": "Output format mismatch",
            }
        elif "Compare low-scoring" in instruction:
            value = {
                "failure_modes": ["Verbose output"],
                "success_habits": [],
                "prune": [],
                "explore": [],
            }
        elif "Contrast successful" in instruction:
            value = {"findings": ["Output format mismatch"], "changes": ["Short output"]}
        else:
            if "search_space" in payload:
                value = copy.deepcopy(payload.get("current", payload["seed"]))
                value["resources"]["prompt"] = "Return the exact label ok."
            else:
                value = {"prompt": "Return the exact label ok."}
        return ModelResponse(text=json.dumps(value), usage=Usage(30, 15), model=self.model_id)


@pytest.mark.parametrize(
    "method,options",
    [
        ("arbor", {"merge_every": 2}),
        ("adas", {"repetitions": 2}),
        ("skillopt", {"general_min_tasks": 3}),
        ("evo_harness", {"batch_size": 0}),
        ("rrsi", {"min_edits": 4, "max_edits": 1}),
        ("rrsi", {"repetitions": 1}),
        ("modular_rsi", {"repetitions": 1}),
    ],
)
def test_method_options_rejected_before_search(method, options):
    with pytest.raises(ValueError):
        StudyConfig(method=method, allowed_resources=["prompt"], options=options)


@pytest.mark.parametrize(
    "method",
    [
        "skillopt",
        "evo_harness",
        "ahe",
        "meta_harness",
        "rrsi",
        "adas",
        "darwinx",
        "modular_rsi",
        "arbor",
    ],
)
async def test_methods_execute_native_candidates_and_keep_test_data_sealed(tmp_path, method):
    data, base = suite(), version()
    for split in ("search", "selection", "release", "test"):
        for sample in getattr(data, split):
            sample.expected = "ok"
    if method in {"skillopt", "evo_harness"}:
        raw = base.spec.model_dump()
        raw["resources"]["prompt"]["role"] = "skill"
        raw["graph"]["nodes"]["answer"].update(instructions="Complete the task.", skills=["prompt"])
        base = compile_snapshot(AgentSpec.model_validate(raw), base.resources)
    proposer = MethodProposer(method)
    config = StudyConfig(
        method=method,
        allowed_resources=["prompt"],
        rounds=2 if method == "skillopt" else 1,
        search_space=SearchSpace(modules={"instructions": ["resource:prompt"]})
        if method == "modular_rsi"
        else None,
        options={"delta": 0.0, "proposals": 1} if method == "rrsi" else {},
        budget=ExperimentBudget(
            max_evaluations=100, max_model_calls=300, max_candidates=30, max_total_tokens=500000
        ),
    )
    store = StudyStore(tmp_path / "studies.sqlite")
    result = await execute_study(
        base=base,
        suite=data,
        config=config,
        models={"main": TaskModel()},
        proposer=proposer,
        workspace=tmp_path,
        store=store,
        scope=Scope("eval-agent"),
        job_id="search",
    )
    assert result["status"] == "completed"
    assert result["selected_version"] != base.version_id
    assert result["method"]["errors"] == []
    assert result["reports"]["test"]["selected"]["score"] == 1
    assert "sealed-secret" not in str(proposer.requests)
    assert "release-secret" not in str(proposer.requests)
    assert result["release_changed"] is False
    state = result["method"]["state"]
    if method == "skillopt":
        assert len(state["snapshots"]) == 2 and state["meta"]
        assert state["rejected"]  # Equal fast/slow proposals cannot drift the retained skill.
    if method == "evo_harness":
        assert state["online_score"] == 0 and state["libraries"]["prompt"]["entries"][0][
            "sources"
        ] == ["s1"]
    if method == "ahe":
        assert state["verdicts"][0]["verdicts"][0]["fixed"] == ["s1"]
    if method == "meta_harness":
        assert len(state["frontier"]) == 1
    if method == "rrsi":
        assert state["ledger"][0]["accepted"] and state["ledger"][0]["attribution"]
    if method == "adas":
        assert state["designs"][0]["critique"]
    if method == "darwinx":
        assert state["archive"][-1]["confirmed"] and state["archive"][-1]["admitted"]
        assert state["archive"][-1]["invariants"] == ["s1"]
    if method == "modular_rsi":
        assert state["branches"]["instructions"]["history"]
    if method == "arbor":
        assert state["tree"]["H2"]["accepted"] and state["tree"]["ROOT"]["insight"]
        assert state["tree"]["H2"]["base_version"] == base.version_id


def test_skill_patch_boundaries_and_protected_guidance():
    text = "One step.\n" + START + "\nGlobal guidance\n" + END
    with pytest.raises(ValueError, match="protected"):
        apply_patch(
            {"s": text},
            [{"resource": "s", "op": "replace", "old": "Global guidance", "text": "Ignore checks"}],
            budget=2,
            max_chars=100,
        )
    with pytest.raises(ValueError, match="step size"):
        apply_patch(
            {"s": text},
            [{"resource": "s", "op": "append", "text": "large" * 100}],
            budget=2,
            max_chars=10,
        )
    with pytest.raises(ValueError, match="unique anchor"):
        apply_patch(
            {"s": "repeat repeat"},
            [{"resource": "s", "op": "delete", "old": "repeat"}],
            budget=2,
            max_chars=100,
        )


def test_preservation_rejects_regression_even_with_higher_mean_and_rrsi_cost_gate():
    options = HarnessOptions(delta=0.01)
    parent = {"per_task": {"old": 1.0, "new": 0.0}, "score": 0.5, "cost": 100}
    child = {"per_task": {"old": 0.8, "new": 1.0}, "score": 0.9, "cost": 100}
    verdict = preservation(child, [parent], {"old"}, options)
    assert not verdict["accepted"] and verdict["lost_invariant"] == ["old"]
    assert not rrsi_admit({"score": 0.9, "cost": 1000}, parent, 0.5, options, 0.01, 0)
    assert rrsi_admit({"score": 0.5, "cost": 80}, parent, 0.5, options, 0.01, 0)
    assert not rrsi_admit({"score": 0.3, "cost": 1}, parent, 0.5, options, 0.01, 1)
