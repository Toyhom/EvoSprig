"""Ordered shots, bounded retakes and restart without repeating paid renders."""

import json
from pathlib import Path

import pytest

from evosprig.core.protocols import ModelResponse, Tool, ToolRegistry
from evosprig.core.runtime import Runtime
from evosprig.core.spec import load_spec
from evosprig.core.version import compile_agent
from evosprig.plugins.mock import MockProvider
from evosprig.plugins.python_tool import python_tool
from evosprig.plugins.sqlite_journal import SQLiteJournal

IMAGE = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aV5kAAAAASUVORK5CYII="


def asset(name, media_type="image/png"):
    return {"id": name, "uri": "https://media.example/" + name, "media_type": media_type}


def test_timeline_tool_fits_speech_without_rewriting_the_story():
    from evosprig.core.json_program import execute

    code = (Path(__file__).parents[1] / "examples/episode-studio/code/schedule_plan.py").read_text()
    shots = [{"id": str(i), "action": "A traveller opens the map.", "narration": "",
              "dialogue": [{"speaker": "traveller", "text": "走" * (41 if i == 0 else 12)}],
              "duration_seconds": 5} for i in range(24)]
    plan = {"title": "The journey", "shots": shots}
    result = execute(code, {"plan": plan, "brief": {"language": "zh-CN", "target_seconds": 180}})
    assert sum(s["duration_seconds"] for s in result["shots"]) == 180
    assert result["shots"][0]["duration_seconds"] >= 9
    assert all(3 <= s["duration_seconds"] <= 15 for s in result["shots"])
    assert [{k: v for k, v in s.items() if k != "duration_seconds"} for s in result["shots"]] == [
        {k: v for k, v in s.items() if k != "duration_seconds"} for s in shots]


@pytest.mark.parametrize("idea", [False, True])
async def test_creative_direction_accepts_text_only_and_preserves_optional_overrides(idea):
    from evosprig.core.debug import plan_debug
    from evosprig.core.version import compile_snapshot

    root = Path(__file__).parents[1] / "examples/episode-studio"
    full = compile_agent(load_spec(root / "agent.yaml"), root)
    fragment = plan_debug(full.spec, ["creative_director", "production_brief"])
    story = "A repair robot finds a greenhouse full of dry plants. Its pump fails. It collects rain in its own shell, waters a seed, and watches the first leaf open."
    direction = {"mode": "idea" if idea else "story", "expanded_story": story if idea else "",
                 "style": "Warm stop-motion animation with copper and green textures", "language": "en", "target_seconds": 45}
    request = {"source_text": "A repair robot saves a greenhouse." if idea else story}
    if idea:
        request.update(style="Ink animation", language="zh-CN", target_seconds=60)
    registry = ToolRegistry()
    registry.register(python_tool())
    provider = MockProvider([ModelResponse(text=json.dumps(direction))])
    result = await Runtime({"main": provider}, registry).run(
        compile_snapshot(fragment.spec, {key: full.resources[key] for key in fragment.spec.resources}),
        {"project": request, "upstream": {}},
    )
    assert result.status == "succeeded", result.error
    brief = result.output["production_brief"]
    assert brief["source_text"] == story
    assert brief["style"] == ("Ink animation" if idea else direction["style"])
    assert brief["language"] == ("zh-CN" if idea else "en")
    assert brief["target_seconds"] == (60 if idea else 45)


class FilmModel(MockProvider):
    capabilities = frozenset({"text", "structured_output", "vision", "tool_calling"})

    def __init__(self, director_cut=False, reference_rejections=0):
        super().__init__()
        self.director_cut = director_cut
        self.reviews = 0
        self.frame_reviews = 0
        self.second_context = None
        self.engineer_calls = 0
        self.reference_reviews = 0
        self.reference_rejections = reference_rejections

    async def complete(self, request):
        self.requests.append(request)
        prompt = request.messages[0]["content"]
        content = request.messages[1]["content"]
        inputs = json.loads(content if isinstance(content, str) else next(p["text"] for p in content if p["type"] == "text"))
        if "You are the creative director" in prompt:
            result = {"mode": "story", "expanded_story": "", "style": "2D animation", "language": "en", "target_seconds": 24}
        elif "You are the source reader" in prompt:
            result = {"characters": [{"id": "visitor", "name": "Visitor", "description": "a visitor",
                                      "source_quote": "A visitor opens a door."}],
                      "dialogue": [], "ending": "A visitor opens a door."}
        elif "producer and screenwriter" in prompt:
            result = {"title": "The door", "logline": "A visitor opens a door.",
                      "characters": [{"id": "visitor", "name": "Visitor", "visual_identity": "blue coat", "voice": "soft"}],
                      "locations": [{"id": "hall", "description": "a wooden door"}],
                      "shots": [{"id": str(i), "location": "hall", "characters": ["visitor"], "action": "reach for the door",
                                 "camera": "medium shot", "dialogue": [{"speaker": "visitor", "text": "Hello"}],
                                 "narration": "", "duration_seconds": 12, "transition": "cut" if i == 0 else "continue", "action_scene": False}
                                for i in range(2)]}
        elif "You are the script editor" in prompt:
            result = inputs["draft"]
        elif "You are the art director" in prompt:
            result = {"style": "2D animation", "assets": [{"id": "visitor", "kind": "character", "prompt": "blue coat"},
                                                           {"id": "hall", "kind": "location", "prompt": "wooden door"}]}
        elif "You are the voice director" in prompt:
            result = {"voices": [{"id": "visitor", "speaker": "Aiden", "text": "Hello",
                                   "direction": "Quiet, curious visitor", "seed": 42}]}
        elif "You are the reference-library editor" in prompt:
            self.reference_reviews += 1
            accepted = self.reference_reviews > self.reference_rejections
            result = {"accepted": accepted, "feedback": "" if accepted else "Remove the extra person and keep an empty room."}
        elif "You are the shot director" in prompt:
            if inputs["context"]["shot"]["id"] == "1":
                self.second_context = inputs["context"]
            result = {"prompt": "reach toward the handle",
                      "transition": "cut" if self.director_cut else inputs["context"]["shot"]["transition"]}
        elif "render engineer and motion director" in prompt:
            self.engineer_calls += 1
            result = {"prompt": inputs["shot"]["id"], "action": False, "steps": 12, "highres_tiling": True}
            if self.engineer_calls == 1:
                result["unknown_sampler"] = "guess"
            if self.engineer_calls != 2:
                result["prompt"] += ' Visitor says "Hello".'
        elif "first-frame editor" in prompt:
            self.frame_reviews += 1
            result = {"accepted": self.frame_reviews != 1, "feedback": "Move the hand to the closed door handle." if self.frame_reviews == 1 else ""}
        else:
            assert any(p["type"] == "image_url" for p in content)
            self.reviews += 1
            # Shot zero needs one retake; shot one reaches its review limit.
            result = {"accepted": self.reviews == 2, "issues": [] if self.reviews == 2 else ["hand moved"],
                      "feedback": "keep the hand on the handle",
                      "continuity": {"character_positions": "left", "lighting": "right", "props": "handle held", "end_action": "reaching"}}
        return ModelResponse(text=json.dumps(result))


@pytest.mark.parametrize("director_cut", [False, True])
@pytest.mark.parametrize("reuse_voice", [False, True])
async def test_episode_retakes_carry_actual_tail_and_resume_without_repeating_renders(tmp_path, director_cut, reuse_voice):
    import runpy

    root = Path(__file__).parents[1] / "examples/episode-studio"
    builder = runpy.run_path(str(root / "build_agent.py"))["build"]
    spec = builder(review_policy="continue" if reuse_voice else "pause").build_spec()
    model = FilmModel(director_cut)
    registry = ToolRegistry()
    registry.register(python_tool())
    renders, images, compositions, recipes = [], [], [], []

    def image(**kwargs):
        images.append(kwargs)
        return asset("image-" + str(len(images)))

    def render(prompt, **kwargs):
        renders.append(prompt)
        return {"clip": asset("clip-" + str(len(renders)), "video/mp4")}

    def inspect(asset, **kwargs):
        frame = {"id": asset["id"] + "-tail", "uri": asset["uri"] + "-tail", "media_type": "image/png"}
        return {"clip": asset, "frames": [frame, frame, frame], "last_frame": frame,
                "tail": {**asset, "id": asset["id"] + "-tail-video"},
                "audio_asset": {**asset, "id": asset["id"] + "-voice", "media_type": "audio/wav"},
                "duration_seconds": 12.25, "width": 1664, "height": 928, "has_audio": True,
                "audio": {"rms_dbfs": -20, "audible_fraction": 0.5}}

    def recipe(controls, **kwargs):
        recipes.append(kwargs)
        return {"prompt": controls}

    def compose(clips, **kwargs):
        compositions.append(clips)
        return asset("film", "video/mp4")

    for name, fn in {
        "media.generate_image": image,
        "media.generate_voice": lambda **kw: asset("visitor-voice", "audio/wav"),
        "media.stage_reference": lambda asset, **kw: {"filename": asset["id"] + ".png"},
        "film.recipe": recipe,
        "film.settings": lambda: {"defaults": {"steps": 12}, "controls": {
            "type": "object", "properties": {"prompt": {"type": "string"}, "action": {"type": "boolean"},
                                               "steps": {"type": "integer", "minimum": 12, "maximum": 16},
                                               "highres_tiling": {"type": "boolean"}}, "additionalProperties": False}},
        "film.render": render,
        "media.ingest_comfy": lambda outputs, **kw: {"assets": [{"node_id": "video", "asset": outputs["clip"]}]},
        "media.inspect_video": inspect,
        "media.vision": lambda **kw: {"images": [IMAGE]},
        "media.frame_vision": lambda **kw: {"images": [IMAGE]},
        "media.compose": compose,
    }.items():
        registry.register(Tool(name, name, {}, {}, fn))
    journal = SQLiteJournal(tmp_path / "runs.sqlite")
    def runtime():
        return Runtime({"main": model, "vision": model}, registry, journal=SQLiteJournal(journal.path), allow_writes=True)

    result = await runtime().run(compile_agent(spec, root),
                                 {"source_text": "A visitor opens a door.", "style": "2D", "language": "en", "target_seconds": 24,
                                  "voices": [{"id": "visitor", "asset": asset("previous-episode-voice", "audio/wav")}] if reuse_voice else []})
    assert result.status == ("succeeded" if reuse_voice else "waiting_input"), result.error
    assert len(renders) == 4 and len(images) == 5
    assert all(image["prompt"].startswith("Visual style: 2D animation\n\n") for image in images[2:])
    assert "plain background" in images[0]["prompt"]
    assert "No people" in images[1]["prompt"]
    assert model.reference_reviews == 2
    assert images[2]["options"]["seed"] != images[3]["options"]["seed"]
    assert model.frame_reviews == 3
    assert renders[0]["seed"] != renders[1]["seed"]
    assert renders[0]["highres_tiling"] is True
    assert all("unknown_sampler" not in render for render in renders)
    assert model.engineer_calls == len(renders) + 2
    assert all('Visitor says "Hello".' in render["prompt"] for render in renders)
    assert model.second_context["previous"]["last_frame"]["id"] == "clip-2-tail"
    assert images[4]["references"][0]["id"] == ("image-1" if director_cut else "clip-2-tail")
    assert recipes[0]["reference_videos"] == []
    assert recipes[0]["reference_audio"] == (["previous-episode-voice.png"] if reuse_voice else [])
    assert recipes[2]["reference_audio"] == (["previous-episode-voice.png"] if reuse_voice else ["clip-2-voice.png"])
    assert recipes[2]["reference_videos"] == ([] if director_cut else ["clip-2-tail-video.png"])
    assert "clip-1-voice.png" not in str(recipes)
    if reuse_voice:
        assert not result.waiting
        assert result.output["shots"]["items"][-1]["take"]["accepted"] is False
    else:
        assert len(result.waiting) == 1 and not compositions
        chosen = result.waiting[0]["input"]["take"]
        journal.respond(result.run_id, result.waiting[0]["path"], {"take": chosen})
    done = await runtime().resume(result.run_id)
    assert done.status == "succeeded", done.error
    assert len(renders) == 4 and len(images) == 5
    assert [a["id"] for a in compositions[0]] == ["clip-2", "clip-4"]
    assert done.output["voices"][0]["id"] == "visitor"
    assert done.output["voices"][0]["asset"]["id"] == ("previous-episode-voice" if reuse_voice else "clip-2-voice")
    assert (await runtime().resume(result.run_id)).status == "succeeded"
    assert len(compositions) == 1
    if reuse_voice and not director_cut:
        previous_images = len(images)
        previous_renders = len(renders)
        model = FilmModel()
        sequel = await runtime().run(compile_agent(spec, root),
            {"source_text": "A visitor opens a door.", "style": "2D", "language": "en",
             "target_seconds": 24, "series": done.output["series"]})
        assert sequel.status == "succeeded", sequel.error
        assert model.reference_reviews == 0
        assert len(images) - previous_images == 3  # Only shot frames; cast and location are reused.
        assert len(renders) - previous_renders == 4
        assert sequel.output["voices"] == done.output["voices"]
        assert sequel.output["series"]["references"] == done.output["series"]["references"]


@pytest.mark.parametrize("rejections", [1, 2])
async def test_reference_review_retries_locally_and_preserves_completed_assets(tmp_path, rejections):
    from evosprig.core.debug import plan_debug
    from evosprig.core.version import compile_snapshot

    root = Path(__file__).parents[1] / "examples/episode-studio"
    full = compile_agent(load_spec(root / "agent.yaml"), root)
    fragment = plan_debug(full.spec, ["reference_plan", "reference_library"])
    version = compile_snapshot(fragment.spec, {key: full.resources[key] for key in fragment.spec.resources})
    model = FilmModel(reference_rejections=rejections)
    images = []

    def generate(**kwargs):
        images.append(kwargs)
        return asset("reference-" + str(len(images)))

    registry = ToolRegistry()
    registry.register(python_tool())
    registry.register(Tool("media.generate_image", "image", {}, {}, generate))
    registry.register(Tool("media.vision", "preview", {}, {}, lambda **kw: {"images": [IMAGE]}))
    journal = SQLiteJournal(tmp_path / "references.sqlite")
    runtime = Runtime({"vision": model}, registry, journal=journal, allow_writes=True)
    result = await runtime.run(version, {"project": {"source_text": "A quiet house."}, "upstream": {
        "art_director": {"style": "A girl walks from a warm hill to a cold bedroom.", "assets": [
            {"id": "house", "kind": "location", "prompt": "Cel-shaded empty room with a blue door on the right."}]}}})
    assert len(images) == 2
    assert "girl" not in images[0]["prompt"]
    assert "No people" in images[0]["prompt"]
    assert "Remove the extra person" in images[1]["prompt"]
    assert images[0]["options"]["seed"] != images[1]["options"]["seed"]
    assert not result.waiting
    assert result.status == "succeeded", result.error
    assert result.output["reference_library"]["items"][0]["asset"]["id"] == "reference-2"
    assert len(images) == 2


def test_episode_deployment_loads_all_model_and_tool_bindings(tmp_path, monkeypatch):
    import runpy

    import yaml

    from evosprig.config import make_models, make_tools
    from evosprig.core.journal import Scope

    root = Path(__file__).parents[1] / "examples/episode-studio"
    monkeypatch.syspath_prepend(str(root))
    profile = runpy.run_path(str(root / "configure.py"))["profile"]
    settings = {"prompt": ["STRING"], "steps": ["INT", {"default": 12}],
                "scheduler": [["simple", "beta"]], "shift_video": ["FLOAT", {"default": 12}],
                "shift_audio": ["FLOAT", {"default": 3}], "duration": ["INT", {"default": 12}],
                "seed": ["INT", {"default": 42}]}
    nodes = [{"id": "settings", "type": "Settings", "widgets_values": ["", 12, "simple", 12, 3, 12, 42, "fixed"]}]
    slots = {}
    for name, count in (("reference_slots", 6), ("audio_slots", 3), ("video_slots", 1)):
        slots[name] = []
        for i in range(count):
            key = f"{name}{i}"
            nodes.append({"id": key, "type": "Loader", "widgets_values": ["reference.png"]})
            slots[name].append({"node_id": key})
    recipe = {"name": "film.recipe", "workflow": {"nodes": nodes, "links": []},
              "object_info": {"Settings": {"input": {"required": settings}, "output": ["MODEL"]},
                              "Loader": {"input": {"required": {"image": ["STRING"]}}, "output": ["IMAGE"]}},
              "outputs": ["settings"], **slots,
              "parameters": {name: {"node_id": "settings", "input_name": name} for name in settings}}
    recipe["parameters"]["action"] = {"node_id": "settings", "kind": "enabled"}
    deployment = profile(recipe, model_url="http://127.0.0.1:18882/v1", model_name="local-vision",
                         media_url="http://127.0.0.1:18880", comfy_url="http://127.0.0.1:18884")
    path = tmp_path / "deployment.yaml"
    path.write_text(yaml.safe_dump(deployment))
    spec = load_spec(root / "agent.yaml")
    models = make_models(spec, path)
    tools = make_tools(tmp_path, Scope(spec.id), profile=path)
    assert models["vision"].capabilities >= {"vision", "structured_output"}
    for tool in spec.tools.values():
        assert tools.resolve(tool.plugin, tool.version)


def test_episode_checks_source_quotes_and_speaker_identity_before_generation():
    from copy import deepcopy

    from evosprig.core.json_program import execute

    root = Path(__file__).parents[1] / "examples/episode-studio/code"
    source = 'A traveler enters. "Mara, why did you open the gate?" he asks.'
    cast = {"characters": [{"id": "traveler", "name": "Traveler", "description": "an unnamed traveler",
                            "source_quote": "A traveler enters."}],
            "dialogue": [{"speaker": "traveler", "text": "Mara, why did you open the gate?"}],
            "ending": "The traveler asks about the gate."}
    validate_source = (root / "source_valid.py").read_text()
    assert execute(validate_source, {"input": {"source_text": source}, "output": cast})["valid"]
    fabricated = deepcopy(cast)
    fabricated["characters"][0]["source_quote"] = "Mara enters."
    assert not execute(validate_source, {"input": {"source_text": source}, "output": fabricated})["valid"]
    plan = {"characters": [{"id": "mara", "name": "Mara"}], "locations": [{"id": "gate"}],
            "shots": [{"id": "opening", "characters": ["mara"], "location": "gate",
                       "dialogue": [{"speaker": "mara", "text": cast["dialogue"][0]["text"]}],
                       "narration": "", "transition": "cut", "duration_seconds": 12}]}
    inputs = {"input": {"source": cast, "brief": {"language": "en", "target_seconds": 12}}, "output": plan}
    check = (root / "plan_valid.py").read_text()
    assert not execute(check, inputs)["valid"]
    plan["characters"] = [{"id": "traveler", "name": "Traveler"}]
    plan["shots"][0]["characters"] = ["traveler"]
    plan["shots"][0]["dialogue"][0]["speaker"] = "traveler"
    assert execute(check, inputs)["valid"]
    # A declared character can still be the wrong speaker for a copied line.
    cast["characters"].append({"id": "companion", "name": "Companion"})
    plan["characters"].append({"id": "companion", "name": "Companion"})
    plan["shots"][0]["dialogue"][0]["speaker"] = "companion"
    result = execute(check, inputs)
    assert not result["valid"] and "assign this source dialogue to traveler" in result["feedback"]


def test_shot_director_changes_reference_conditioning_with_the_edit():
    from evosprig.core.json_program import execute

    root = Path(__file__).parents[1] / "examples/episode-studio/code"
    code = (root / "frame_settings.py").read_text()
    context = {"style": "2D animation", "shot": {"location": "hall", "transition": "continue"},
               "previous_shot": {"location": "hall"}, "seed": 42,
               "previous": {"last_frame": asset("last"), "tail": asset("tail", "video/mp4")},
               "references": [asset("person"), asset("room")],
               "audio_references": [{"speaker": "visitor", "asset": asset("voice", "audio/wav")}]}
    cut = execute(code, {"context": context, "prompt": "A visitor at the door.", "attempt": 0, "transition": "cut"})["context"]
    assert cut["shot"]["transition"] == "cut"
    assert cut["image_references"] == context["references"]
    assert cut["video_references"] == []
    assert cut["audio_references"] == context["audio_references"]
    continuation = execute(code, {"context": context, "prompt": "A visitor at the door.", "attempt": 1, "transition": "continue"})
    assert continuation["prompt"] == "Visual style: 2D animation\n\nA visitor at the door."
    assert continuation["context"]["image_references"][0] == asset("last")
    assert continuation["context"]["video_references"] == [asset("tail", "video/mp4")]
    assert continuation["options"]["seed"] == 43
    context["shot"]["location"] = "garden"
    moved = execute(code, {"context": context, "prompt": "A visitor at the door.", "attempt": 0, "transition": "continue"})["context"]
    assert moved["shot"]["transition"] == "cut" and moved["video_references"] == []


@pytest.mark.parametrize("dialogue,narration", [
    ([{"speaker": "visitor", "text": "你好，我们出发吧。"}], ""),
    ([], "这扇门通向远方。"),
    ([{"speaker": "visitor", "text": "Hello"}], "The journey begins."),
])
def test_render_validation_catches_missing_speech_before_generation(dialogue, narration):
    from evosprig.core.json_program import execute

    source = (Path(__file__).parents[1] / "examples/episode-studio/code/render_valid.py").read_text()
    inputs = {"input": {"shot": {"dialogue": dialogue, "narration": narration, "action_scene": False},
                        "render_profile": {"controls": {"type": "object"}}},
              "output": {"prompt": "Wind through the grass. No dialogue.", "action": False}}
    rejected = execute(source, inputs)
    assert not rejected["valid"]
    for line in dialogue:
        assert line["text"] in rejected["feedback"]
    if narration:
        assert narration in rejected["feedback"]
    inputs["output"]["prompt"] = "Dialogue: " + " ".join(line["text"] for line in dialogue) + " Voiceover: " + narration
    assert execute(source, inputs)["valid"]
    inputs["input"]["shot"] = {"dialogue": [], "narration": "", "action_scene": False}
    inputs["output"]["prompt"] = "Only wind through the grass."
    assert execute(source, inputs)["valid"]


def test_plan_feedback_includes_duration_speech_and_identity_in_one_pass():
    from evosprig.core.json_program import execute

    path = Path(__file__).parents[1] / "examples/episode-studio/code/plan_valid.py"
    plan = {"characters": [{"id": "visitor", "name": "Visitor"}],
            "locations": [{"id": "door"}],
            "shots": [{"id": "opening", "characters": ["visitor"], "location": "elsewhere",
                       "dialogue": [{"speaker": "visitor", "text": "这是一个需要更多时间才能说完的长句子。"}],
                       "narration": "", "transition": "continue", "duration_seconds": 3}]}
    result = execute(path.read_text(), {"output": plan, "input": {"brief": {"language": "zh-CN", "target_seconds": 30}}})
    assert not result["valid"]
    for issue in ["requested total is 30", "too much dialogue", "undeclared character or location", "first shot must use cut"]:
        assert issue in result["feedback"]


def test_duration_feedback_gives_a_feasible_edit_without_changing_the_plan():
    import ast
    from copy import deepcopy

    from evosprig.core.json_program import execute

    source = (Path(__file__).parents[1] / "examples/episode-studio/code/plan_valid.py").read_text()
    plan = {"characters": [], "locations": [{"id": "hill"}], "shots": [
        {"id": f"shot_{i}", "characters": [], "location": "hill", "dialogue": [],
         "narration": "风" * (70 if i == 15 else 10), "transition": "cut", "duration_seconds": 5}
        for i in range(16)]}
    before = deepcopy(plan)
    for target in (60, 180, 240):
        result = execute(source, {"output": plan, "input": {"brief": {"language": "zh", "target_seconds": target}}})
        assignment = result["feedback"].split("assignment is ", 1)[1].split(". These numbers", 1)[0]
        durations = ast.literal_eval(assignment)
        assert sum(durations.values()) == target
        assert all(3 <= value <= 15 for value in durations.values())
        assert durations["shot_15"] >= 14
    assert plan == before
