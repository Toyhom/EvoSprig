import json

import pytest

from evosprig.core.protocols import ModelResponse, Usage
from evosprig.evaluation.authoring import suite_from_inputs
from evosprig.evaluation.budget import BudgetMeter, ExperimentBudget
from evosprig.evaluation.scoring import ScoringEngine
from evosprig.evaluation.suite import EvalSuite, Metric, Sample
from evosprig.plugins.mock import MockProvider


def result():
    return {
        "status": "succeeded",
        "output": {"answer": "A useful answer"},
        "events": [{"type": "tool.result", "data": {"tool": "search"}}],
    }


async def test_input_only_judge_is_blind_and_uses_shared_budget():
    sample = Sample(id="a", input={"question": "Summarize our launch risks."})
    model = MockProvider(
        [
            ModelResponse(
                text=json.dumps(
                    {"score": 0.75, "feedback": "Two risks covered", "confidence": 0.8}
                ),
                usage=Usage(50, 20),
            )
            for _ in range(2)
        ]
    )
    meter = BudgetMeter(ExperimentBudget(max_model_calls=2))
    grade = await ScoringEngine({"judge": model}, meter).assess(
        Metric(kind="llm_judge", output_path="", repeats=2), sample, result(), {}
    )
    assert grade["score"] == 0.75 and len(grade["judge_receipts"]) == 2
    assert meter.snapshot()["model_calls"] == 2
    assert meter.snapshot()["input_tokens"] == 100
    assert "version_id" not in str(model.requests)
    assert "independent task evaluator" in model.requests[0].messages[0]["content"]
    assert "untrusted" in model.requests[0].messages[0]["content"]


async def test_malformed_judgment_cannot_become_a_passing_score():
    sample = Sample(id="a", input={})
    engine = ScoringEngine(
        {"judge": MockProvider([ModelResponse(text='{"score":true,"feedback":"pass"}')])},
        BudgetMeter(ExperimentBudget()),
    )
    with pytest.raises(ValueError):
        await engine.assess(Metric(kind="llm_judge"), sample, result(), {})


async def test_composition_supports_node_and_environment_assertions_and_required_failures():
    metric = Metric(
        kind="composite",
        components=[
            Metric(
                kind="json_schema",
                target="node",
                node="graph/build",
                output_path="",
                schema={"type": "object", "required": ["files"]},
            ),
            Metric(kind="exact", target="environment", output_path="tests_passed", required=True),
        ],
    )
    engine = ScoringEngine({}, BudgetMeter(ExperimentBudget()))
    sample = Sample(id="a", input={}, expected=True)
    observations = {"nodes": {"graph/build": {"files": []}}, "environment": {"tests_passed": False}}
    failed = await engine.assess(metric, sample, result(), observations)
    assert failed["score"] == 0 and failed["required_failures"] == [1]
    observations["environment"]["tests_passed"] = True
    assert (await engine.assess(metric, sample, result(), observations))["score"] == 1
    # Persist/reload schema aliases through ordinary model_dump, as StudyStore does.
    assert Metric.model_validate(metric.model_dump()).model_dump() == metric.model_dump()


async def test_user_scorer_receives_real_observations():
    calls = []

    async def scorer(payload):
        calls.append(payload)
        return {"score": 0.9, "feedback": "Passed business checks"}

    engine = ScoringEngine({}, BudgetMeter(ExperimentBudget()), scorers={"business": scorer})
    grade = await engine.assess(
        Metric(kind="external", scorer="business"),
        Sample(id="a", input={}),
        result(),
        {"environment": {"order_count": 7}},
    )
    assert grade["score"] == 0.9
    assert calls[0]["observations"]["environment"]["order_count"] == 7


def test_input_authoring_disjointness_and_auto_judge():
    inputs = [{"question": f"Business task {i}"} for i in range(10)]
    suite = suite_from_inputs(inputs)
    assert suite.metric.kind == "llm_judge"
    assert suite.suite_id == suite_from_inputs(inputs).suite_id
    assert len(suite.release) >= 2
    assert "Business task" not in str(suite.optimization_view().get("release", {}))
    with pytest.raises(ValueError, match="disjoint"):
        suite_from_inputs([{}] * 4)
    raw = suite.model_dump()
    raw.pop("metric")
    for split in ("search", "selection", "release", "test"):
        for sample in raw[split]:
            sample.pop("expected", None)
    assert EvalSuite.model_validate(raw).metric.kind == "llm_judge"


def test_legacy_suite_and_split_content_ids_are_preserved():
    from evosprig.core.spec import digest

    raw = {
        "id": "legacy",
        "description": "",
        "metric": {"kind": "exact", "output_path": "answer", "normalize_text": False},
    }
    for split in ("search", "selection", "release", "test"):
        raw[split] = [
            {
                "id": split,
                "input": {"question": split},
                "expected": split,
                "tags": [],
                "required_tools": [],
            }
        ]
    suite = EvalSuite.model_validate(raw)
    assert suite.suite_id == digest(raw)
    assert suite.split_id("release") == digest(
        {"suite": digest(raw), "split": "release", "samples": raw["release"]}
    )


def test_mock_deployment_never_builds_a_live_judge(monkeypatch):
    from evosprig.evaluation.deployment import evaluation_dependencies

    config = {
        "judges": {
            "critic": {
                "base_url": "https://models.example.com/v1",
                "model": "critic",
                "api_key_env": "NO_SUCH_KEY",
            }
        }
    }
    dependencies = evaluation_dependencies(config, mock=True)
    assert isinstance(dependencies["judge_models"]["critic"], MockProvider)


async def test_binary_task_payload_is_omitted_only_from_textual_judge():
    from evosprig.evaluation.evidence import model_evidence

    raw = {"image_base64": "binary-image-bytes" * 20000, "question": "Read the printed total"}
    sample = Sample(id="receipt", input=raw)
    model = MockProvider([ModelResponse(text='{"score":0.8,"feedback":"Total matches OCR"}')])
    engine = ScoringEngine({"judge": model}, BudgetMeter(ExperimentBudget()))
    await engine.assess(
        Metric(kind="llm_judge"), sample, result(), {"tools": [{"output": {"ocr": "Total 12.50"}}]}
    )
    sent = json.loads(model.requests[0].messages[-1]["content"])
    assert sent["task"]["image_base64"]["characters"] == len(raw["image_base64"])
    assert "binary-image-bytes" not in model.requests[0].messages[-1]["content"]
    assert sample.input == raw and isinstance(raw["image_base64"], str)
    assert model_evidence({"files": {"notes.txt": "keep this text"}}) == {
        "files": {"notes.txt": "keep this text"}
    }


def test_node_metrics_can_select_distinct_reference_fields():
    sample = Sample(id="order", input={}, expected={"answer": "A useful answer", "total": 42})
    assert Metric(reference_path="answer").score(sample, result())[0] == 1
    assert Metric(reference_path="total").score(sample, result())[0] == 0


def test_same_version_score_variability_is_not_evolution_gain():
    from evosprig.evaluation.comparison import comparison_record, markdown_comparison

    before = {
        "report_id": "first",
        "suite_id": "suite",
        "split": "release",
        "version_id": "same",
        "score": 0.7,
        "samples": [
            {
                "sample_id": "task",
                "input": {},
                "score": 0.7,
                "run": {"status": "succeeded", "output": "A"},
            }
        ],
    }
    after = {**before, "report_id": "second", "score": 0.9}
    record = comparison_record(before, after, method="opro", task_model="test")
    assert record["gain"] == 0 and not record["candidate_changed"]
    assert markdown_comparison(record).startswith("# Application result")
    assert "### Before" not in markdown_comparison(record)
    reused = comparison_record(before, before, method="opro", task_model="test")
    assert reused["validation_reused"]
    assert markdown_comparison(reused).count("### Result") == 1
