import random

from test_evaluation import suite, version
from test_evolution_methods import TaskModel
from test_extended_methods import ExtendedProposer

from evosprig.core.journal import Scope
from evosprig.core.version import compile_snapshot
from evosprig.evaluation.budget import ExperimentBudget
from evosprig.evolution.mipro import choose_trial
from evosprig.evolution.study import StudyConfig, execute_study
from evosprig.plugins.sqlite_studies import StudyStore


async def test_joint_search_uses_actual_component_traces_and_keeps_held_out_inputs_private(tmp_path):
    original = version()
    base = compile_snapshot(original.spec, {"prompt": "Return the exact label ok."})
    tasks = suite()
    for split in ("search", "selection", "release", "test"):
        for sample in getattr(tasks, split):
            sample.expected = "ok"
    proposer = ExtendedProposer()
    result = await execute_study(
        base=base, suite=tasks,
        config=StudyConfig(method="mipro", allowed_resources=["prompt"], rounds=2,
            budget=ExperimentBudget(max_evaluations=80, max_model_calls=120, max_candidates=20)),
        models={"main": TaskModel()}, proposer=proposer, workspace=tmp_path,
        store=StudyStore(tmp_path/"studies.sqlite"), scope=Scope(base.spec.id), job_id="joint",
    )
    state = result["method"]["state"]
    assert state["sampler"] == "categorical-tpe"
    assert state["bootstrap_samples"]["prompt"] == [{
        "sample_id": "s1", "node": "graph/answer",
        "input": {"question": "train"}, "output": {"text": "ok"},
    }]
    assert any(trial["demonstrations"]["prompt"] == ["s1"] for trial in state["trials"])
    assert "sealed-secret" not in str(proposer.requests) + str(state)
    assert "release-secret" not in str(proposer.requests) + str(state)
    assert result["reports"]["test"]["selected"]["score"] == 1
    assert result["release_changed"] is False


def test_categorical_search_explores_each_configuration_once_and_stops():
    sizes, history, seen = [3, 3], [], set()
    rng = random.Random(7)
    for _ in range(9):
        choice = choose_trial(sizes, history, seen, rng)
        assert choice not in seen
        seen.add(choice)
        history.append((choice, float(choice[0] == 2)))
    assert choose_trial(sizes, history, seen, rng) is None
    assert len(seen) == 9
