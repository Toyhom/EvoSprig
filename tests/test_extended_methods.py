import json

import pytest
from test_evaluation import suite, version
from test_evolution_methods import TaskModel

from evosprig.core.journal import Scope
from evosprig.core.protocols import ModelResponse, Usage
from evosprig.core.version import compile_snapshot
from evosprig.evaluation.budget import ExperimentBudget
from evosprig.evolution.study import StudyConfig, execute_study
from evosprig.plugins.mock import MockProvider
from evosprig.plugins.sqlite_studies import StudyStore


class ExtendedProposer(MockProvider):
    async def complete(self, request):
        self.requests.append(request)
        if "Extract reusable insights" in request.messages[0]["content"]:
            text = json.dumps(
                {
                    "rules": [
                        {"id": "precise", "text": "Return the exact label ok.", "sources": ["s1"]}
                    ]
                }
            )
        elif request.json_output:
            text = json.dumps(
                {"prompt": f"Return the exact label ok. Strategy {len(self.requests)}."}
            )
        else:
            text = "Return the exact label ok. Preserve the task's answer format."
        return ModelResponse(text=text, usage=Usage(12, 10), model=self.model_id)


@pytest.mark.parametrize(
    "method",
    [
        "ape",
        "protesgi",
        "promptbreeder",
        "reflexion",
        "expel",
        "bootstrap_fewshot",
        "fewshot_search",
        "mipro",
    ],
)
async def test_distinct_methods_use_framework_evaluation_and_protect_held_out_data(
    tmp_path, method
):
    data = suite()
    for split in ("search", "selection", "release", "test"):
        for sample in getattr(data, split):
            sample.expected = "ok"
    base = version()
    if method in {"bootstrap_fewshot", "fewshot_search"}:
        base = compile_snapshot(base.spec, {"prompt": "Return the exact label ok."})
    proposer = ExtendedProposer()
    store = StudyStore(tmp_path / "studies.sqlite")
    result = await execute_study(
        base=base,
        suite=data,
        config=StudyConfig(
            method=method,
            allowed_resources=["prompt"],
            rounds=1,
            budget=ExperimentBudget(
                max_evaluations=100, max_model_calls=200, max_candidates=30, max_total_tokens=500000
            ),
        ),
        models={"main": TaskModel()},
        proposer=proposer,
        workspace=tmp_path,
        store=store,
        scope=Scope("eval-agent"),
        job_id="test",
    )
    assert result["status"] == "completed"
    assert result["reports"]["test"]["selected"]["score"] == 1
    assert "sealed-secret" not in str(proposer.requests)
    assert "release-secret" not in str(proposer.requests)
    assert result["release_changed"] is False
    state = result["method"]["state"]
    if method == "ape":
        assert len(state["pool"]) == 3
    if method == "protesgi":
        assert state["gradients"][0]["sample_ids"] == ["s1"] and state["beam"]
    if method == "promptbreeder":
        assert len(state["population"]) == 4 and state["mutator_history"]
    if method == "reflexion":
        assert state["episodes"][0]["sample_ids"] == ["s1"]
    if method == "expel":
        assert state["rules"]["precise"]["sources"] == ["s1"]
    if method in {"bootstrap_fewshot", "fewshot_search"}:
        assert list(state["demonstrations"]) == ["s1"]
        assert not proposer.requests
