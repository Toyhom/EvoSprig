import json

from evosprig.core.protocols import ModelResponse
from evosprig.core.version import compile_agent
from evosprig.evaluation.budget import BudgetMeter, ExperimentBudget
from evosprig.evaluation.runner import Evaluator
from evosprig.evaluation.suite import Metric, Sample
from evosprig.plugins.mock import MockProvider
from evosprig.sdk import Builder


async def test_judge_receives_actual_question_and_resolved_human_response(tmp_path):
    builder = Builder("coach", {}, {}, spec_version="0.3").model("main", "main")
    builder.node("question", "transform", inputs={"text": {"value": "What is 2 + 1?"}}, output_schema={})
    builder.node("learner", "human", inputs={"question": {"ref": "nodes.question.output.text"}},
                 output_schema={"type": "object", "required": ["answer"]})
    builder.node("feedback", "model", model="main", instructions="Assess the answer.", output_schema={})
    builder.edge("question", "learner").edge("learner", "feedback")
    builder.output(text={"ref": "nodes.feedback.output.text"})
    version = compile_agent(builder.build_spec())
    judge = MockProvider([ModelResponse(text='{"score":0,"feedback":"Wrong answer praised"}')])
    sample = Sample(id="a", input={}, responses={"graph/learner": {"answer": "7"}})
    report = await Evaluator(
        tmp_path, {"main": MockProvider([ModelResponse(text="Correct!")])},
        BudgetMeter(ExperimentBudget()), judge_models={"judge": judge},
    ).evaluate(version, [sample], Metric(kind="llm_judge", output_path=""),
               suite_id="coach", split="release")
    interaction = {"node": "graph/learner", "input": {"question": "What is 2 + 1?"},
                   "response": {"answer": "7"}}
    assert report["samples"][0]["observations"]["interactions"] == [interaction]
    payload = json.loads(judge.requests[0].messages[1]["content"])
    assert payload["interactions"] == [interaction]
    assert payload["observed"] == {"text": "Correct!"}
    assert "instructions" not in payload
