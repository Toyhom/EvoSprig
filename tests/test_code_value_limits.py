import pytest

from evosprig.config import make_tools
from evosprig.core.journal import Scope
from evosprig.core.protocols import ToolFeedbackError
from evosprig.core.runtime import Runtime
from evosprig.core.version import compile_snapshot
from evosprig.plugins.python_tool import execute
from evosprig.sdk import Builder


@pytest.mark.asyncio
async def test_code_aggregates_large_shot_records_and_enforces_node_limit(tmp_path):
    builder = (Builder("timeline", {"type": "object"}, {"type": "object"}, spec_version="0.3")
               .tool("python", "code.python")
               .resource("timeline", "timeline.py", role="code")
               .node("clips", "code", tool="python", code="timeline",
                     inputs={"shots": {"ref": "input.shots"}}, output_schema={"type": "array"})
               .output(clips={"ref": "nodes.clips.output"}))
    spec = builder.build_spec()
    resources = {"timeline": 'def run(inputs):\n    return [shot["clip"] for shot in inputs["shots"]]'}
    data = {"shots": [{"clip": str(i), "review": "x" * 6000} for i in range(16)]}
    runtime = Runtime({}, make_tools(tmp_path, Scope("timeline")))
    result = await runtime.run(compile_snapshot(spec, resources), data)
    assert result.status == "succeeded"
    assert result.output["clips"] == [str(i) for i in range(16)]
    spec.graph.nodes["clips"].code_max_value_chars = 65536
    result = await runtime.run(compile_snapshot(spec, resources), data)
    assert result.status == "failed"
    assert "code_max_value_chars (65536)" in result.error["message"]


@pytest.mark.parametrize("code", [
    'def run(inputs):\n    return "x" * 2000',
    'def run(inputs):\n    return "x".replace("", "a" * 1000)',
    'def run(inputs):\n    return ("x" * 600).join(["a", "b", "c"])',
])
def test_code_limits_expansion_before_allocation(code):
    with pytest.raises(ToolFeedbackError):
        execute(code, {}, max_value_chars=1024)


def test_empty_replacement_counts_insertions():
    assert execute('def run(inputs):\n    return "".replace("", "ok")', {}) == "ok"
