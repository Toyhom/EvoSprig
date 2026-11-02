import json

import pytest
from test_evaluation import suite, version

from evosprig.core.journal import Scope
from evosprig.core.protocols import ModelResponse, Usage
from evosprig.evaluation.budget import BudgetMeter, ExperimentBudget
from evosprig.evaluation.runner import Evaluator
from evosprig.evolution import gepa, opro
from evosprig.evolution.context import EvolutionContext
from evosprig.plugins.mock import MockProvider
from evosprig.plugins.sqlite_versions import VersionStore


class TaskModel(MockProvider):
    async def complete(self, request):
        self.requests.append(request)
        return ModelResponse(
            text="ok" if "exact label" in request.messages[0]["content"] else "long wrong response",
            usage=Usage(10, 2),
            model=self.model_id,
        )


class Proposer(MockProvider):
    async def complete(self, request):
        self.requests.append(request)
        content = (
            json.dumps({"prompt": "Return the exact label ok."})
            if request.json_output
            else "```\nReturn the exact label ok.\n```"
        )
        return ModelResponse(text=content, usage=Usage(30, 12), model=self.model_id)


@pytest.mark.parametrize("method", ["opro", "gepa"])
async def test_two_distinct_methods_use_runtime_candidates_and_protected_splits(tmp_path, method):
    data = suite()
    for split in ["search", "selection", "release", "test"]:
        for sample in getattr(data, split):
            sample.expected = "ok"
    meter = BudgetMeter(ExperimentBudget(max_candidates=2, max_evaluations=20))
    proposer, model = Proposer(), TaskModel()
    store = VersionStore(tmp_path / "versions.sqlite")
    context = EvolutionContext(
        base=version(),
        allowed=["prompt"],
        view=data.optimization_view(),
        metric=data.metric,
        evaluator=Evaluator(tmp_path, {"main": model}, meter),
        meter=meter,
        proposer=proposer,
        store=store,
        scope=Scope("eval-agent"),
        job_id="job",
        method=method,
    )
    if method == "opro":
        result = await opro.optimize(context, rounds=1)
        assert result["history"][0]["search_score"] == 0
        assert result["history"][1]["search_score"] == 1
    else:
        result = await gepa.optimize(context, max_metric_calls=6)
        assert result["implementation"] == "official-gepa-0.1.4"
        assert len(result["state"]["candidates"]) >= 2
        assert result["state"]["parents"]
    assert result["selected"]["prompt"] == "Return the exact label ok."
    assert result["selected_score"] == 1
    assert len(context.candidates) == 1
    assert proposer.requests
    assert "sealed-secret" not in str(proposer.requests)
    assert "release-secret" not in str(proposer.requests)
    assert store.release(Scope("eval-agent"))["revision"] == 0
    assert meter.snapshot()["model_calls"] == len(model.requests) + len(proposer.requests)


async def test_invalid_opro_edit_keeps_seed_and_release(tmp_path):
    proposer = MockProvider([ModelResponse(text='{"scorer":"always pass"}', usage=Usage(5, 5))])
    data, meter, store = (
        suite(),
        BudgetMeter(ExperimentBudget()),
        VersionStore(tmp_path / "versions.sqlite"),
    )
    context = EvolutionContext(
        base=version(),
        allowed=["prompt"],
        view=data.optimization_view(),
        metric=data.metric,
        evaluator=Evaluator(tmp_path, {"main": TaskModel()}, meter),
        meter=meter,
        proposer=proposer,
        store=store,
        scope=Scope("eval-agent"),
        job_id="job",
        method="opro",
    )
    result = await opro.optimize(context, rounds=1)
    assert result["selected"] == context.seed
    assert result["errors"][0]["type"] == "ValueError"
    assert context.candidates == {}
    assert store.release(context.scope)["revision"] == 0
