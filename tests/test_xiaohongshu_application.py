"""A writing loop keeps facts and hard checks even when the reviewer approves."""

import json
from pathlib import Path

from evosprig.core.protocols import ModelResponse, ToolRegistry
from evosprig.core.runtime import Runtime
from evosprig.core.spec import load_spec
from evosprig.core.version import compile_agent
from evosprig.plugins.mock import MockProvider
from evosprig.plugins.python_tool import python_tool

ROOT = Path(__file__).parents[1] / "examples/xiaohongshu-studio"
BRIEF = {"reader_need": "预约修书", "angle": "保留旧书", "facts": ["39元", "需预约"],
         "qualifications": ["12人"], "example_id": "event", "structure": "实际用途、时间和预约"}
GOOD = {"title": "旧书周六带来修", "body": "周六14点，39元含材料。限12人，需预约。", "tags": ["旧书", "周末"]}
APPROVE = {"accepted": True, "reader_feedback": [], "factual_issues": [], "edits": []}


async def run(posts, reviews):
    responses = [ModelResponse(text=json.dumps(BRIEF))]
    for post, review in zip(posts, reviews):
        responses.extend([ModelResponse(text=json.dumps(post)), ModelResponse(text=json.dumps(review))])
    model = MockProvider(responses)
    registry = ToolRegistry()
    registry.register(python_tool())
    v = compile_agent(load_spec(ROOT / "agent.yaml"), ROOT)
    result = await Runtime({"main": model}, registry).run(v, {
        "source": "周六14点修书，39元含材料，限12人，需预约。",
        "required_terms": ["39元", "需预约"], "links": ["https://example.org/book?day=sat"],
    })
    assert result.status == "succeeded", result.error
    return result.output, model


async def test_missing_condition_forces_revision_despite_approving_model():
    bad = dict(GOOD, body="周六修书，39元含材料。")
    out, model = await run([bad, GOOD], [APPROVE, APPROVE])
    assert out["ready"] and out["rounds"] == 2
    assert out["text"].count("https://example.org/book?day=sat") == 1
    assert "需预约" in out["text"] and len(model.requests) == 5
    retry = json.loads(model.requests[3].messages[1]["content"])
    assert retry["previous"] == bad
    assert any("需预约" in issue for issue in retry["feedback"])
    assert len(out["changes"]) == 2


async def test_exhausted_revisions_return_copy_with_unresolved_status():
    bad = dict(GOOD, title="很长的标题" * 9)
    out, model = await run([bad] * 3, [APPROVE] * 3)
    assert not out["ready"] and out["rounds"] == 3
    assert len(model.requests) == 7
    assert any("标题超长" in issue for issue in out["feedback"])


async def test_fact_review_can_reject_a_formally_valid_post():
    invented = dict(GOOD, body=GOOD["body"] + "保证修好。")
    reject = dict(APPROVE, accepted=False, factual_issues=["素材没有保证修好的承诺，请删除。"])
    out, model = await run([invented, GOOD], [reject, APPROVE])
    assert out["ready"] and "保证" not in out["text"]
    retry = json.loads(model.requests[3].messages[1]["content"])
    assert "保证修好" in retry["feedback"][0]


async def test_first_acceptable_draft_stops_without_extra_rewrites():
    out, model = await run([GOOD], [APPROVE])
    assert out["ready"] and out["rounds"] == 1 and len(model.requests) == 3
    assert out["text"].endswith("#旧书 #周末")
