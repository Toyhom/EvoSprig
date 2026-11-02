import json

import pytest
from test_evaluation import suite, version
from test_evolution_methods import TaskModel

from evosprig.core.journal import Scope
from evosprig.core.protocols import ModelResponse, Usage
from evosprig.evaluation.budget import BudgetMeter, ExperimentBudget
from evosprig.evaluation.runner import Evaluator
from evosprig.evolution.search import apply_delta, evoprompt
from evosprig.evolution.study import StudyConfig, execute_study
from evosprig.plugins.mock import MockProvider
from evosprig.plugins.sqlite_studies import StudyStore


class SearchProposer(MockProvider):
    async def complete(self, request):
        self.requests.append(request)
        payload = json.loads(request.messages[-1]["content"])
        number = len(self.requests)
        if not request.json_output:
            text = "The output includes prose. Return the exact label ok."
        elif "Curate the playbooks" in request.messages[0]["content"]:
            text = json.dumps(
                {
                    "prompt": [
                        {
                            "op": "add",
                            "id": f"lesson-{number}",
                            "text": f"Return the exact label ok. Rule {number}.",
                        }
                    ]
                }
            )
        else:
            operator = payload.get("operator")
            text = json.dumps(
                {
                    "prompt": f"Return the exact label ok. Strategy {number}."
                    if operator != "diversify"
                    else f"Alternate strategy {number}."
                }
            )
        return ModelResponse(text=text, usage=Usage(10, 10), model=self.model_id)


@pytest.mark.parametrize("method", ["self_refine", "ace", "evoprompt_ga", "evoprompt_de"])
async def test_native_methods_end_to_end_with_sealed_validation(tmp_path, method):
    data = suite()
    for split in ("search", "selection", "release", "test"):
        for sample in getattr(data, split):
            sample.expected = "ok"
    proposer = SearchProposer()
    store = StudyStore(tmp_path / "studies.sqlite")
    config = StudyConfig(
        method=method,
        allowed_resources=["prompt"],
        rounds=1,
        budget=ExperimentBudget(max_evaluations=80, max_model_calls=100, max_candidates=20),
    )
    result = await execute_study(
        base=version(),
        suite=data,
        config=config,
        models={"main": TaskModel()},
        proposer=proposer,
        workspace=tmp_path,
        store=store,
        scope=Scope("eval-agent"),
        job_id="test",
    )
    assert result["status"] == "completed"
    assert result["reports"]["test"]["selected"]["score"] == 1
    assert result["reports"]["test"]["baseline"]["score"] == 0
    assert "sealed-secret" not in str(proposer.requests)
    assert "release-secret" not in str(proposer.requests)
    assert result["release_changed"] is False
    assert store.release(Scope("eval-agent"))["revision"] == 0
    state = result["method"]["state"]
    if method.startswith("evoprompt"):
        assert len(state["population"]) == 4
        assert any(
            len(h["parents"]) == (2 if method.endswith("ga") else 4)
            for h in result["method"]["history"]
        )
    elif method == "ace":
        assert state["deltas"][0]["accepted"]
        assert state["playbooks"]["prompt"]
    else:
        assert state["critiques"]


def test_ace_delta_validation_is_atomic():
    original = {"rule": "Preserve citations"}
    assert apply_delta(
        original,
        [
            {"op": "update", "id": "rule", "text": "Preserve exact citations"},
            {"op": "add", "id": "format", "text": "Use JSON"},
        ],
    ) == {"rule": "Preserve exact citations", "format": "Use JSON"}
    assert apply_delta(original, [{"op": "remove", "id": "rule"}]) == {}
    for delta in [
        [{"op": "remove", "id": "missing"}],
        [{"op": "add", "id": "rule", "text": "overwrite"}],
        [{"op": "add", "id": "copy", "text": "Preserve citations"}],
        [{"op": "update", "id": "rule", "text": "ok"}, {"op": "remove", "id": "rule"}],
    ]:
        with pytest.raises(ValueError):
            apply_delta(original, delta)
    assert original == {"rule": "Preserve citations"}


@pytest.mark.parametrize("method", ["ga", "de"])
async def test_population_fill_is_bounded_for_duplicate_proposals(tmp_path, method):
    from evosprig.evolution.context import EvolutionContext
    from evosprig.plugins.sqlite_versions import VersionStore

    class Duplicate(MockProvider):
        async def complete(self, request):
            self.requests.append(request)
            return ModelResponse(
                text=json.dumps({"prompt": version().resources["prompt"]}), usage=Usage(1, 1)
            )

    data = suite()
    meter = BudgetMeter(ExperimentBudget(max_model_calls=50))
    proposer = Duplicate()
    context = EvolutionContext(
        base=version(),
        allowed=["prompt"],
        view=data.optimization_view(),
        metric=data.metric,
        evaluator=Evaluator(tmp_path, {"main": TaskModel()}, meter),
        meter=meter,
        proposer=proposer,
        store=VersionStore(tmp_path / "versions.sqlite"),
        scope=Scope("eval-agent"),
        job_id="duplicate",
        method=method,
    )
    result = await evoprompt(context, variant=method, rounds=2)
    assert result["status"] == "insufficient_diversity"
    assert len(proposer.requests) == 12
    assert len(result["history"]) == 1
