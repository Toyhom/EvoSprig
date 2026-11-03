import copy
import json
import os
import subprocess
import sys

import pytest

from evosprig.config import make_tools
from evosprig.core.journal import Scope
from evosprig.core.protocols import ModelResponse, ToolFeedbackError, Usage
from evosprig.core.runtime import Runtime
from evosprig.core.version import compile_snapshot
from evosprig.evolution.space import SearchSpace
from evosprig.plugins.mock import MockProvider
from evosprig.plugins.python_tool import execute
from evosprig.plugins.sqlite_versions import VersionStore
from evosprig.sdk import Builder


async def test_search_selects_code_and_topology_then_runs_standalone(tmp_path):
    from test_harness_search import MethodProposer

    from evosprig.evaluation.suite import EvalSuite
    from evosprig.evolution.study import StudyConfig, execute_study
    from evosprig.exporters.python import export_python
    from evosprig.plugins.sqlite_studies import StudyStore

    class CodeProposer(MethodProposer):
        async def complete(self, request):
            if "Propose a complete application candidate" not in request.messages[0]["content"]:
                return await super().complete(request)
            self.requests.append(request)
            candidate = json.loads(request.messages[1]["content"])["seed"]
            candidate["resources"]["calculation"] = (
                'def run(inputs):\n    return {"total": sum(inputs["values"])}\n'
            )
            graph = candidate["fields"]["/graph"]
            graph["nodes"]["format"] = {
                "type": "transform",
                "inputs": {"answer": {"ref": "nodes.calculate.output.total"}},
                "output_schema": {"type": "object"},
            }
            graph["edges"].append({"source": "calculate", "target": "format"})
            graph["output"] = {"answer": {"ref": "nodes.format.output.answer"}}
            return ModelResponse(text=json.dumps(candidate), usage=Usage(30, 100))

    data = EvalSuite.model_validate(
        {
            "id": "totals",
            **{
                split: [{"id": split, "input": {"values": values}, "expected": sum(values)}]
                for split, values in {
                    "search": [2, 3, 7],
                    "selection": [10, -3],
                    "release": [20, 4],
                    "test": [109, -6, 1],
                }.items()
            },
        }
    )
    base, scope = program(), Scope("compute")
    store = StudyStore(tmp_path / "studies.sqlite")
    proposer = CodeProposer("adas")
    result = await execute_study(
        base=base,
        suite=data,
        config=StudyConfig(
            method="adas",
            allowed_resources=["calculation"],
            rounds=1,
            search_space=SearchSpace.model_validate({"fields": {"/graph": {"kind": "graph"}}}),
        ),
        models={},
        proposer=proposer,
        workspace=tmp_path,
        store=store,
        scope=scope,
        job_id="code-search",
    )
    assert result["status"] == "completed" and not result["method"]["errors"]
    assert result["reports"]["test"]["baseline"]["score"] == 0
    assert result["reports"]["test"]["selected"]["score"] == 1
    assert "109" not in str(proposer.requests)
    selected = store.get(scope, result["selected_version"])
    assert set(VersionStore.diff(base, selected)) == {"agent.json", "calculation"}
    destination = tmp_path / "export"
    export_python(selected, destination)
    completed = subprocess.run(
        [sys.executable, "app.py", "--input", '{"values":[31,-4,2]}'],
        cwd=destination,
        env={**os.environ, "PYTHONPATH": str(destination / "src")},
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert json.loads(completed.stdout)["output"] == {"answer": 29}


def program():
    spec = (
        Builder("compute", {"type": "object"}, {"type": "object"}, spec_version="0.3")
        .resource("calculation", "skills/calculate.py", role="code")
        .tool("python", "code.python")
        .node(
            "calculate",
            "code",
            tool="python",
            code="calculation",
            inputs={"values": {"ref": "input.values"}},
            output_schema={"type": "object"},
        )
        .output(answer={"ref": "nodes.calculate.output.total"})
        .build_spec()
    )
    return compile_snapshot(
        spec, {"calculation": 'def run(inputs):\n    return {"total": len(inputs["values"])}\n'}
    )


async def test_code_snapshot_changes_actual_execution_export_and_diff(tmp_path):
    base = program()
    space = SearchSpace()
    candidate = space.seed(base, ["calculation"])
    candidate["resources"]["calculation"] = (
        'def run(inputs):\n    return {"total": sum(inputs["values"])}\n'
    )
    evolved = space.compile(base, ["calculation"], candidate)
    scope = Scope("compute")
    runtime = Runtime({}, make_tools(tmp_path, scope))
    before = await runtime.run(base, {"values": [2, 3, 7]}, scope=scope)
    after = await runtime.run(evolved, {"values": [2, 3, 7]}, scope=scope)
    assert before.output == {"answer": 3} and after.output == {"answer": 12}
    store = VersionStore(tmp_path / "versions.sqlite")
    record = store.snapshot_candidate(scope, base, evolved, method="adas", job_id="study")
    assert "sum" in record["diff"]["calculation"]
    restored = store.get(scope, evolved.version_id)
    assert (await runtime.run(restored, {"values": [10, -3]}, scope=scope)).output == {"answer": 7}


@pytest.mark.parametrize(
    "code",
    [
        "def run(inputs):\n    import os\n    return os.environ",
        "def run(inputs):\n    return inputs.__class__",
        'def run(inputs):\n    return open("/etc/passwd").read()',
        "def run(inputs):\n    while True:\n        pass",
        'def run(inputs):\n    return "x" * 1000000000000',
        "def run(inputs):\n    return 2 ** 1000000000",
    ],
)
def test_candidate_python_has_no_host_capabilities_and_is_bounded(code):
    with pytest.raises(ToolFeedbackError):
        execute(code, {})


def test_python_dictionary_construction_keeps_json_keys():
    assert execute('def run(inputs):\n    return dict([["voice", inputs["asset"]]])',
                   {"asset": {"id": "clip"}}) == {"voice": {"id": "clip"}}
    with pytest.raises(ToolFeedbackError, match="dictionary keys"):
        execute('def run(inputs):\n    return dict([[1, "voice"]])', {})


async def test_harness_memory_and_model_route_affect_runtime(tmp_path):
    from evosprig.core.memory import MemoryScope
    from evosprig.plugins.sqlite_memory import SQLiteMemory

    b = (
        Builder("routing", {"type": "object"}, {"type": "object"}, spec_version="0.3")
        .model("small", "small")
        .model("large", "large")
        .tool("recall", "memory.search")
        .node(
            "agent",
            "agent",
            model="small",
            tools=["recall"],
            inputs={"question": {"ref": "input.question"}},
            harness={"memory": {"tool": "recall", "query_input": "question", "limit": 1}},
            output_schema={"type": "object"},
        )
        .output(answer={"ref": "nodes.agent.output.text"})
    )
    base = compile_snapshot(b.build_spec(), {})
    scope = Scope("routing")
    SQLiteMemory(tmp_path / "memory.sqlite").write(
        MemoryScope(scope), "Project budget is 42", source="user"
    )
    space = SearchSpace.model_validate(
        {
            "fields": {
                "/graph/nodes/agent/model": {"choices": ["small", "large"]},
                "/graph/nodes/agent/harness/memory/limit": {
                    "kind": "integer",
                    "minimum": 1,
                    "maximum": 10,
                },
            }
        }
    )
    seed = space.seed(base, [])
    seed["fields"]["/graph/nodes/agent/model"] = "large"
    seed["fields"]["/graph/nodes/agent/harness/memory/limit"] = 2
    evolved = space.compile(base, [], seed)
    small, large = MockProvider(), MockProvider([ModelResponse(text="42", usage=Usage(10, 2))])
    result = await Runtime({"small": small, "large": large}, make_tools(tmp_path, scope)).run(
        evolved, {"question": "budget"}, scope=scope
    )
    assert result.output == {"answer": "42"} and not small.requests
    assert "Project budget is 42" in str(large.requests)
    assert "agent.json" in VersionStore.diff(base, evolved)
    bad = copy.deepcopy(seed)
    bad["fields"]["/graph/nodes/agent/harness/memory/limit"] = 99
    with pytest.raises(ValueError, match="bounds"):
        space.compile(base, [], bad)


def test_graph_search_enforces_topology_and_node_authority():
    base = program()
    space = SearchSpace.model_validate({"fields": {"/graph": {"kind": "graph"}}})
    candidate = space.seed(base, ["calculation"])
    graph = candidate["fields"]["/graph"]
    graph["nodes"]["extra"] = {
        "type": "transform",
        "inputs": {"total": {"ref": "nodes.calculate.output.total"}},
        "output_schema": {"type": "object"},
    }
    graph["edges"].append({"source": "calculate", "target": "extra"})
    graph["output"] = {"answer": {"ref": "nodes.extra.output.total"}}
    assert "extra" in space.compile(base, ["calculation"], candidate).spec.graph.nodes
    graph["nodes"]["extra"] = {
        "type": "tool",
        "tool": "python",
        "inputs": {},
        "output_schema": {"type": "object"},
    }
    with pytest.raises(ValueError, match="authority"):
        space.compile(base, ["calculation"], candidate)
    with pytest.raises(ValueError, match="deployment"):
        SearchSpace.model_validate(
            {"fields": {"/execution/allow_side_effects": {"choices": [True]}}}
        )


async def test_structured_output_repair_is_configured_per_agent(tmp_path):
    base = (
        Builder("repair", {"type": "object"}, {"type": "object"}, spec_version="0.3")
        .model("main", "main", ["text", "structured_output"])
        .node(
            "answer",
            "agent",
            model="main",
            response_format="json",
            inputs={},
            harness={"output_errors": "feedback", "max_output_retries": 1},
            output_schema={"type": "object", "required": ["answer"]},
        )
        .output(answer={"ref": "nodes.answer.output.answer"})
        .build_spec()
    )
    model = MockProvider(
        [
            ModelResponse(text="broken", usage=Usage(10, 2)),
            ModelResponse(text='{"answer":"fixed"}', usage=Usage(10, 2)),
        ]
    )
    result = await Runtime({"main": model}).run(compile_snapshot(base, {}), {})
    assert result.output == {"answer": "fixed"} and len(model.requests) == 2
