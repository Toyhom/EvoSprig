import pytest

from evosprig.core.protocols import ModelResponse, ProviderError, Usage
from evosprig.evaluation.budget import BudgetMeter, ExperimentBudget
from evosprig.evaluation.scoring import ScoringEngine
from evosprig.evaluation.suite import Metric, Sample
from evosprig.plugins.mock import MockProvider


async def test_repaired_judgment_preserves_score_contract_and_charges_every_call():
    model = MockProvider([
        ModelResponse(text='{"score":true,"feedback":"bad"}', usage=Usage(20, 10)),
        ModelResponse(text='{"score":0.4,"feedback":"Missing one step"}', usage=Usage(25, 12)),
    ])
    meter = BudgetMeter(ExperimentBudget())
    result = await ScoringEngine({"main": model}, meter).assess(
        Metric(kind="llm_judge", output_path="", judge_max_output_tokens=2000),
        Sample(id="task", input={"question": "Explain the process"}),
        {"status": "succeeded", "output": "Step 1", "events": []}, {},
    )
    assert result["score"] == 0.4
    assert [r["valid"] for r in result["judge_receipts"]] == [False, True]
    assert meter.snapshot()["model_calls"] == 2
    assert meter.snapshot()["input_tokens"] == 45
    assert all(r.max_output_tokens == 2000 for r in model.requests)
    assert model.requests[0].messages[:2] == model.requests[1].messages[:2]


@pytest.mark.parametrize("code,expected_calls", [("output_limit", 2), ("authentication", 1)])
async def test_judge_repair_limit_is_bounded_and_does_not_retry_authentication(code, expected_calls):
    class Failing(MockProvider):
        async def complete(self, request):
            self.requests.append(request)
            raise ProviderError(code, "provider failure")
    model = Failing()
    meter = BudgetMeter(ExperimentBudget())
    with pytest.raises(ProviderError):
        await ScoringEngine({"main": model}, meter).assess(
            Metric(kind="llm_judge", output_path="", judge_max_retries=1),
            Sample(id="task", input={}),
            {"status": "succeeded", "output": "answer", "events": []}, {},
        )
    assert len(model.requests) == expected_calls
    assert meter.snapshot()["model_calls"] == expected_calls
    assert meter.snapshot()["reserved_tokens"] > 0
