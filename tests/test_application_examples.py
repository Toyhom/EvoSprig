"""Applications execute through the same runtime and bindings as CLI/Studio."""

import copy
import io
import json
import runpy
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest
import yaml

from evosprig.config import make_tools
from evosprig.core.journal import Scope
from evosprig.core.protocols import ModelResponse, ToolCall
from evosprig.core.runtime import Runtime
from evosprig.core.spec import load_spec
from evosprig.core.version import compile_agent
from evosprig.data_cli import add_documents, load_csv
from evosprig.exporters.importer import inspect_archive
from evosprig.exporters.python import export_python
from evosprig.plugins.mock import MockProvider
from evosprig.plugins.sqlite_journal import SQLiteJournal

ROOT = Path(__file__).resolve().parents[1]


def version(name, filename="agent.yaml"):
    root = ROOT / "examples" / name
    return compile_agent(load_spec(root / filename), root)


async def drive_video(runtime, result):
    for _ in range(40):
        if result.status == "succeeded":
            return result
        assert result.status in {"waiting_input", "waiting_external"}, result.error
        for wait in result.waiting:
            if wait["kind"] != "human":
                continue
            inputs = wait["input"]
            if wait["path"].endswith("script_review"):
                response = inputs["plan"]
            elif wait["path"].endswith("frame_review"):
                response = inputs["frame"]
            else:
                response = {
                    "clips": [take["clip"] for take in inputs["takes"]["items"]],
                    "audio": [],
                    "subtitles": "",
                }
            runtime.journal.respond(result.run_id, wait["path"], response)
        runtime = Runtime(
            runtime.models,
            runtime.tools,
            journal=SQLiteJournal(runtime.journal.path),
            allow_writes=True,
        )
        result = await runtime.resume(result.run_id)
    pytest.fail("video workflow did not terminate")


@pytest.mark.parametrize("count", [1, 3, 5])
async def test_video_variable_shots_recovery_and_retake(tmp_path, count):
    fixture = runpy.run_path(str(ROOT / "tests/fixtures/video/media.py"))
    plan = copy.deepcopy(fixture["PLAN"])
    plan["shots"] = [dict(plan["shots"][i % 3], id=f"shot-{i}") for i in range(count)]
    simulator = fixture["MediaSimulator"](tmp_path / "media.sqlite")
    model = MockProvider([ModelResponse(text=json.dumps(plan))])
    runtime = Runtime(
        {"main": model},
        simulator.registry(),
        journal=SQLiteJournal(tmp_path / "runs.sqlite"),
        allow_writes=True,
    )
    result = await drive_video(
        runtime, await runtime.run(version("video-studio"), {"brief": "A living book"})
    )
    takes = result.output["takes"]["items"]
    assert [take["shot"]["id"] for take in takes] == [s["id"] for s in plan["shots"]]
    assert len(simulator.jobs()) == 2 + 2 * count
    assert len(model.requests) == 1
    old_clips = [take["clip"] for take in takes]
    retake = await drive_video(
        runtime,
        await runtime.run(
            version("video-studio", "shot-agent.yaml"),
            {
                "shot": dict(plan["shots"][0], camera="macro push in"),
                "catalog": result.output["catalog"],
                "style": plan["style"],
            },
        ),
    )
    new_clips = [retake.output["clip"], *old_clips[1:]]
    composed = await drive_video(
        runtime,
        await runtime.run(
            version("video-studio", "compose-agent.yaml"),
            {"clips": new_clips, "audio": [], "subtitles": ""},
        ),
    )
    assert composed.output["film"]["uri"].startswith("fixture://compose/")
    assert len(simulator.jobs()) == 5 + 2 * count
    assert runtime.get(result.run_id).output["takes"]["items"][0]["clip"] == old_clips[0]
    assert new_clips[0] != old_clips[0]
    assert new_clips[1:] == old_clips[1:]


@pytest.mark.parametrize("scenario,refunds", [("approved", 1), ("denied", 0), ("answer", 0)])
def test_support_human_decision_controls_transaction(tmp_path, scenario, refunds):
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "tests/fixtures/customer_support/run.py"),
            "--workspace",
            str(tmp_path),
            "--scenario",
            scenario,
        ],
        capture_output=True,
        text=True,
        timeout=60,
        cwd=ROOT,
    )
    assert result.returncode == 0, result.stderr
    report = json.loads((tmp_path / "report.json").read_text())
    assert report["status"] == "succeeded"
    assert report["refunds"] == refunds


class ResearchModel(MockProvider):
    async def complete(self, request):
        self.requests.append(request)
        instructions = request.messages[0]["content"]
        if "focused research tasks" in instructions:
            return ModelResponse(text=json.dumps({"tasks": ["launch beta", "pricing proposal"]}))
        if "assigned task" in instructions:
            if request.messages[-1]["role"] == "user":
                data = json.loads(request.messages[-1]["content"])
                return ModelResponse(
                    tool_calls=(ToolCall("search", "search", {"query": data["task"]}),)
                )
            hits = json.loads(request.messages[-1]["content"])["citations"]
            assert hits
            return ModelResponse(text=hits[0]["text"] + " " + hits[0]["citation"])
        data = json.loads(request.messages[-1]["content"])
        return ModelResponse(text="\n".join(item["text"] for item in data["findings"]))


async def test_research_tasks_use_shared_documents_and_editor(tmp_path):
    v = version("research-team")
    add_documents(ROOT / "examples/research-team/documents", tmp_path, v.spec.id)
    model = ResearchModel()
    runtime = Runtime(
        {"main": model},
        make_tools(tmp_path, Scope(v.spec.id)),
        journal=SQLiteJournal(tmp_path / "runs.sqlite"),
    )
    result = await runtime.run(v, {"question": "What should we address before launch?"})
    assert result.status == "waiting_input", result.error
    draft = result.waiting[0]["input"]["draft"]
    assert "June 15" in draft and "$19" in draft
    assert "[" in draft
    calls = len(model.requests)
    runtime.journal.respond(result.run_id, result.waiting[0]["path"], {"text": draft})
    result = await runtime.resume(result.run_id)
    assert result.status == "succeeded"
    assert len(model.requests) == calls == 6
    assert result.output["text"] == draft


async def test_document_chat_receives_citations_from_shared_ingestion(tmp_path):
    v = version("document-chat")
    add_documents(ROOT / "examples/document-chat/documents", tmp_path, v.spec.id)
    model = MockProvider(
        [
            ModelResponse(tool_calls=(ToolCall("q", "search", {"query": "learning budget"}),)),
            ModelResponse(text="The annual learning budget is $600."),
        ]
    )
    result = await Runtime({"main": model}, make_tools(tmp_path, Scope(v.spec.id))).run(
        v, {"question": "What is the learning budget?"}
    )
    assert result.status == "succeeded"
    hits = json.loads(model.requests[1].messages[-1]["content"])["citations"]
    assert "$600" in hits[0]["text"]
    assert hits[0]["source"] == "documents/team-handbook.md"
    assert hits[0]["citation"].startswith("[")
    # A different project cannot retrieve this project's collection.
    other = make_tools(tmp_path, Scope("different-project"))
    assert (await other.resolve("documents.search", "1").invoke({"query": "learning"}))[
        "citations"
    ] == []


async def test_personal_assistant_can_save_then_recall_in_a_new_runtime(tmp_path):
    v = version("personal-memory")
    first = MockProvider(
        [
            ModelResponse(
                tool_calls=(
                    ToolCall(
                        "save",
                        "remember",
                        {"content": "I prefer vegetarian lunches.", "source": "user:explicit"},
                    ),
                )
            ),
            ModelResponse(text="Saved your lunch preference."),
        ]
    )
    result = await Runtime(
        {"main": first},
        make_tools(tmp_path, Scope(v.spec.id)),
        journal=SQLiteJournal(tmp_path / "memory-runs.sqlite"),
        allow_writes=True,
    ).run(v, {"question": "Remember that I prefer vegetarian lunches."})
    assert result.status == "succeeded"
    second = MockProvider(
        [
            ModelResponse(tool_calls=(ToolCall("read", "search", {"query": "vegetarian"}),)),
            ModelResponse(text="Choose a vegetarian lunch."),
        ]
    )
    result = await Runtime(
        {"main": second},
        make_tools(tmp_path, Scope(v.spec.id)),
        journal=SQLiteJournal(tmp_path / "memory-runs.sqlite"),
        allow_writes=True,
    ).run(v, {"question": "What should I have for lunch?"})
    assert result.status == "succeeded"
    records = json.loads(second.requests[1].messages[-1]["content"])["records"]
    assert records[0]["content"] == "I prefer vegetarian lunches."


async def test_data_analyst_uses_actual_schema_and_corrects_query(tmp_path, monkeypatch):
    v = version("data-analyst")
    database = tmp_path / "orders.sqlite"
    load_csv(ROOT / "examples/data-analyst/data/orders.csv", database, "orders")
    monkeypatch.setenv("EVOSPRIG_SQLITE_PATH", str(database))
    model = MockProvider(
        [
            ModelResponse(tool_calls=(ToolCall("s", "schema", {}),)),
            ModelResponse(
                tool_calls=(ToolCall("bad", "query", {"sql": "SELECT SUM(sales) FROM orders"}),)
            ),
            ModelResponse(
                tool_calls=(ToolCall("q", "query", {"sql": "SELECT SUM(revenue) FROM orders"}),)
            ),
            ModelResponse(text="Total revenue is 4,956."),
        ]
    )
    tools = make_tools(
        tmp_path, Scope(v.spec.id), profile=ROOT / "examples/data-analyst/deployment.example.yaml"
    )
    result = await Runtime({"main": model}, tools).run(v, {"question": "What is total revenue?"})
    assert result.status == "succeeded", result.error
    assert '"revenue"' in model.requests[1].messages[-1]["content"]
    assert "no such column" in model.requests[2].messages[-1]["content"]
    assert json.loads(model.requests[3].messages[-1]["content"])["rows"] == [[4956]]


@pytest.mark.parametrize(
    "example",
    [
        "video-studio",
        "customer-support",
        "research-team",
        "personal-memory",
        "document-chat",
        "data-analyst",
    ],
)
def test_example_exports_and_inert_import_preserve_all_capabilities(tmp_path, example):
    v = version(example)
    profile = ROOT / "examples" / example / "deployment.example.yaml"
    bindings = yaml.safe_load(profile.read_text())["tools"] if profile.exists() else {}
    export_python(v, tmp_path / example, tool_bindings=bindings)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for path in (tmp_path / example).rglob("*"):
            if path.is_file():
                archive.writestr(path.relative_to(tmp_path / example).as_posix(), path.read_bytes())
    imported, report = inspect_archive(buffer.getvalue())
    assert imported.version_id == v.version_id
    assert report["compatible"]


@pytest.mark.parametrize("name", ["career-coach", "study-coach"])
async def test_interactive_apps_resume_without_repeating_completed_model_nodes(tmp_path, name):
    class AppModel(MockProvider):
        async def complete(self, request):
            self.requests.append(request)
            if request.json_output:
                return ModelResponse(
                    text=json.dumps({"questions": ["First?", "Second?", "Third?"]})
                )
            return ModelResponse(text="Completed step")

    model = AppModel()
    scope = Scope(name)
    journal = SQLiteJournal(tmp_path / "runs.sqlite")
    tools = make_tools(tmp_path, scope)
    runtime = Runtime({"main": model}, tools, journal=journal)
    inputs = json.loads((ROOT / "examples" / name / "sample.json").read_text())
    result = await runtime.run(version(name), inputs, scope=scope)
    assert result.status == "waiting_input"
    count = len(model.requests)
    response = (
        {"answer": "My experience"} if name == "career-coach" else {"answers": ["A", "B", "C"]}
    )
    journal.respond(result.run_id, result.waiting[0]["path"], response, scope)
    resumed = Runtime({"main": model}, tools, journal=SQLiteJournal(journal.path))
    result = await resumed.resume(result.run_id, scope=scope)
    assert result.status == "succeeded"
    assert len(model.requests) == count + 1
    assert all("## Skill:" in request.messages[0]["content"] for request in model.requests)
    received = json.loads(model.requests[-1].messages[-1]["content"])
    assert all(received[key] == value for key, value in response.items())


async def test_content_channels_share_skills_and_preserve_requested_order(tmp_path):
    model = MockProvider()
    inputs = json.loads((ROOT / "examples/content-studio/sample.json").read_text())
    result = await Runtime({"main": model}).run(version("content-studio"), inputs)
    assert result.status == "succeeded"
    drafts = [
        request
        for request in model.requests
        if "requested channel" in request.messages[0]["content"]
    ]
    assert len(drafts) == len(inputs["channels"])
    assert all("## Skill: brand_voice" in request.messages[0]["content"] for request in drafts)
    editor_input = json.loads(model.requests[-1].messages[-1]["content"])
    assert [draft["channel"] for draft in editor_input["drafts"]] == inputs["channels"]
