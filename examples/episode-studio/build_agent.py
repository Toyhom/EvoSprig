"""An episodic animation team built from EvoSprig graphs and media tools."""

from pathlib import Path

from evosprig.core.spec import save_spec
from evosprig.sdk import Builder


def obj(**properties):
    return {"type": "object", "properties": properties, "required": list(properties), "additionalProperties": False}


TEXT = {"type": "string", "minLength": 1}
STRING = {"type": "string"}
ANY = {"type": "object"}
ASSET = obj(id=TEXT, uri=TEXT, media_type=TEXT)
ASSETS = {"type": "array", "items": ASSET}
SHOT = obj(
    id=TEXT, location=TEXT, characters={"type": "array", "items": TEXT, "maxItems": 4},
    action=TEXT, camera=TEXT, dialogue={"type": "array", "items": obj(speaker=TEXT, text=TEXT)},
    narration=STRING, duration_seconds={"type": "integer", "minimum": 3, "maximum": 15},
    transition={"enum": ["cut", "continue"]}, action_scene={"type": "boolean"},
)
PLAN = obj(title=TEXT, logline=TEXT,
           characters={"type": "array", "items": obj(id=TEXT, name=TEXT, visual_identity=TEXT, voice=TEXT), "minItems": 1, "maxItems": 4},
           locations={"type": "array", "items": obj(id=TEXT, description=TEXT), "minItems": 1, "maxItems": 4},
           shots={"type": "array", "items": SHOT, "minItems": 1, "maxItems": 24})
SOURCE = obj(
    characters={"type": "array", "minItems": 1, "maxItems": 4,
                "items": obj(id=TEXT, name=TEXT, description=TEXT, source_quote=TEXT)},
    dialogue={"type": "array", "maxItems": 80, "items": obj(speaker=TEXT, text=TEXT)},
    ending=TEXT,
)
ART = obj(style=TEXT, assets={"type": "array", "items": obj(id=TEXT, kind={"enum": ["character", "location"]}, prompt=TEXT), "minItems": 1, "maxItems": 8})
VOICES = obj(voices={"type": "array", "maxItems": 5, "items": obj(
    id=TEXT, speaker={"enum": ["Chelsie", "Ethan", "Aiden"]}, text=TEXT, direction=TEXT,
    seed={"type": "integer", "minimum": 0, "maximum": 2147483647})})
BRIEF = obj(source_text=TEXT, style=TEXT, language=TEXT,
            target_seconds={"type": "integer", "minimum": 12, "maximum": 300})
DIRECTION = obj(mode={"enum": ["story", "idea"]}, expanded_story=STRING, style=TEXT, language=TEXT,
                target_seconds={"type": "integer", "minimum": 12, "maximum": 300})
VERDICT = obj(accepted={"type": "boolean"}, issues={"type": "array", "items": TEXT}, feedback=STRING,
              continuity=obj(character_positions=STRING, lighting=STRING, props=STRING, end_action=STRING))
CONTROLS = obj(prompt=TEXT, action={"type": "boolean"})
CONTROLS["additionalProperties"] = {"type": ["string", "number", "boolean"]}


def ref(path, **extra):
    return {"ref": path, **extra}


def val(value):
    return {"value": value}


def model(resource, inputs, schema, *, vision=False, tokens=4096, validator=None):
    skills = {
        "creative_director": ["screenwriting"],
        "producer": ["screenwriting", "continuity"],
        "script_editor": ["screenwriting", "continuity"],
        "art_director": ["continuity", "cinematography"],
        "shot_director": ["continuity", "cinematography"],
        "render_engineer": ["video_prompting", "continuity"],
        "continuity_review": ["continuity"],
        "frame_review": ["continuity"],
    }.get(resource, [])
    node = {"type": "agent", "model": "vision" if vision else "main",
            "instructions": {"resource": resource}, "skills": skills,
            "response_format": "json", "inputs": inputs, "output_schema": schema,
            "harness": {"output_errors": "feedback", "max_output_retries": 2, "max_output_tokens": tokens,
                        "max_tool_rounds": 1}}
    if vision:
        node["image_inputs"] = ["images"]
    if validator:
        node["output_validator"] = validator
    return node


def tool(name, inputs, schema=ANY):
    return {"type": "tool", "tool": name, "inputs": inputs, "output_schema": schema}


def code(name, inputs, schema=ANY):
    return {"type": "code", "tool": "python", "code": name, "inputs": inputs, "output_schema": schema}


def graph(nodes, output, edges=None):
    names = list(nodes)
    return {"entry": names[0], "nodes": nodes,
            "edges": edges if edges is not None else [{"source": a, "target": b} for a, b in zip(names, names[1:])],
            "output": output}


def render_attempt():
    nodes = {
        "render_preview": tool("frame_preview", {"asset": ref("input.frame")}),
        "render_engineer": model("render_engineer", {
            "shot": ref("input.context.shot"), "style": ref("input.context.style"),
            "scene": ref("input.context.scene"),
            "images": ref("nodes.render_preview.output.images"),
            "cast": ref("input.context.cast"), "previous": ref("input.context.previous"),
            "feedback": ref("input.feedback"),
            "reference_order": ref("input.reference_order"),
            "render_profile": ref("input.context.render_profile"),
        }, CONTROLS, vision=True, tokens=2048, validator="render_valid"),
        "render_settings": code("render_settings", {
            "controls": ref("nodes.render_engineer.output"), "context": ref("input.context"),
            "attempt": ref("input.attempt"),
        }),
        "configure_nodes": tool("recipe", {"controls": ref("nodes.render_settings.output"),
                                              "reference_images": ref("input.reference_images"),
                                              "reference_audio": ref("input.reference_audio"),
                                              "reference_videos": ref("input.reference_videos")}),
        "render": tool("render", {"prompt": ref("nodes.configure_nodes.output.prompt")}),
        "collect_media": tool("ingest", {"outputs": ref("nodes.render.output")}),
        "select_clip": code("select_clip", {"assets": ref("nodes.collect_media.output.assets")}, ASSET),
        "inspect_clip": tool("inspect", {"asset": ref("nodes.select_clip.output")}),
        "review_images": code("review_images", {"inspection": ref("nodes.inspect_clip.output"),
                                                   "frame": ref("input.frame"),
                                                   "previous": ref("input.context.previous")}),
        "preview": tool("vision_preview", {"assets": ref("nodes.review_images.output.assets")}),
        "continuity_review": model("continuity_review", {
            "images": ref("nodes.preview.output.images"), "shot": ref("input.context.shot"),
            "scene": ref("input.context.scene"), "previous_shot": ref("input.context.previous_shot"),
            "previous": ref("input.context.previous"), "inspection": ref("nodes.inspect_clip.output"),
            "reference_order": ref("nodes.review_images.output.labels"),
        }, VERDICT, vision=True, tokens=3072),
        "record_take": code("record_take", {
            "context": ref("input.context"), "frame": ref("input.frame"),
            "reference_images": ref("input.reference_images"), "reference_order": ref("input.reference_order"),
            "inspection": ref("nodes.inspect_clip.output"), "review": ref("nodes.continuity_review.output"),
            "attempt": ref("input.attempt"), "controls": ref("nodes.render_settings.output"),
        }),
    }
    return graph(nodes, {"context": ref("nodes.record_take.output.context"),
                         "frame": ref("input.frame"), "reference_images": ref("input.reference_images"),
                         "reference_audio": ref("input.reference_audio"), "reference_videos": ref("input.reference_videos"),
                         "reference_order": ref("input.reference_order"),
                         "attempt": ref("nodes.record_take.output.attempt"),
                         "accepted": ref("nodes.record_take.output.accepted"),
                         "feedback": ref("nodes.record_take.output.feedback"),
                         "take": ref("nodes.record_take.output.take")})


def frame_attempt():
    verdict = obj(accepted={"type": "boolean"}, feedback=STRING)
    nodes = {
        "shot_director": model("shot_director", {"context": ref("input.context"),
                                                  "feedback": ref("input.feedback")},
                               obj(prompt=TEXT, transition={"enum": ["cut", "continue"]})),
        "settings": code("frame_settings", {"context": ref("input.context"), "attempt": ref("input.attempt"),
                                               "prompt": ref("nodes.shot_director.output.prompt"),
                                               "transition": ref("nodes.shot_director.output.transition")}),
        "generate": tool("image", {"prompt": ref("nodes.settings.output.prompt"),
                                    "references": ref("nodes.settings.output.context.image_references"),
                                    "options": ref("nodes.settings.output.options")}, ASSET),
        "review_inputs": code("frame_review_inputs", {"context": ref("nodes.settings.output.context"),
                                                        "frame": ref("nodes.generate.output")}),
        "preview": tool("vision_preview", {"assets": ref("nodes.review_inputs.output.assets")}),
        "frame_review": model("frame_review", {"images": ref("nodes.preview.output.images"),
                                                "context": ref("nodes.settings.output.context"),
                                                "labels": ref("nodes.review_inputs.output.labels")}, verdict, vision=True),
    }
    return graph(nodes, {"context": ref("nodes.settings.output.context"), "attempt": ref("nodes.settings.output.attempt"),
                         "frame": ref("nodes.generate.output"), "accepted": ref("nodes.frame_review.output.accepted"),
                         "feedback": ref("nodes.frame_review.output.feedback")})


def shot_graph(max_takes, max_frame_takes):
    staging = graph({"stage": tool("stage", {"asset": ref("input.item")})},
                    {"filename": ref("nodes.stage.output.filename"), "media_type": ref("input.item.media_type")})
    nodes = {
        "shot_context": code("shot_context", {"shot": ref("input.item"), "index": ref("input.index"),
                                               "context": ref("input.context"), "previous": ref("input.previous")}),
        "frame_takes": {"type": "loop", "inputs": {"context": ref("nodes.shot_context.output"),
                                                     "feedback": val(""), "attempt": val(0)},
                        "body": frame_attempt(), "max_iterations": max_frame_takes,
                        "until": {"left": ref("input.accepted"), "op": "truthy"}, "output_schema": ANY},
        "frame_accepted": {"type": "condition", "condition": {"left": ref("nodes.frame_takes.output.accepted"), "op": "truthy"},
                           "output_schema": obj(value={"type": "boolean"})},
        "approved_frame": {"type": "transform", "inputs": {"frame": ref("nodes.frame_takes.output.frame")}, "output_schema": obj(frame=ASSET)},
        "frame_attention": {"type": "human", "inputs": {"frame": ref("nodes.frame_takes.output.frame"),
                                                         "feedback": ref("nodes.frame_takes.output.feedback")}, "output_schema": obj(frame=ASSET)},
        "frame_choice": {"type": "join", "join": "selected", "output_schema": ANY,
                         "inputs": {"approved": ref("nodes.approved_frame.output", optional=True, default=None),
                                    "reviewed": ref("nodes.frame_attention.output", optional=True, default=None)}},
        "first_frame": code("selected_frame", {"approved": ref("nodes.frame_choice.output.approved"),
                                                 "reviewed": ref("nodes.frame_choice.output.reviewed")}, ASSET),
        "gather_references": code("gather_references", {"frame": ref("nodes.first_frame.output"),
                                                         "context": ref("nodes.frame_takes.output.context")}),
        "stage_references": {"type": "map", "items": ref("nodes.gather_references.output.assets"),
                             "body": staging, "inputs": {}, "max_items": 12, "output_schema": ANY},
        "reference_names": code("reference_names", {"items": ref("nodes.stage_references.output.items")}),
        "takes": {"type": "loop", "inputs": {
            "context": ref("nodes.frame_takes.output.context"), "frame": ref("nodes.first_frame.output"),
            "reference_images": ref("nodes.reference_names.output.images"),
            "reference_audio": ref("nodes.reference_names.output.audio"),
            "reference_videos": ref("nodes.reference_names.output.videos"),
            "reference_order": ref("nodes.gather_references.output.labels"),
            "feedback": val(""), "attempt": val(0),
        }, "body": render_attempt(), "max_iterations": max_takes,
            "until": {"left": ref("input.accepted"), "op": "truthy"}, "output_schema": ANY},
        "accepted": {"type": "condition", "condition": {"left": ref("nodes.takes.output.accepted"), "op": "truthy"},
                     "output_schema": obj(value={"type": "boolean"})},
        "approved": {"type": "transform", "inputs": {"take": ref("nodes.takes.output.take")}, "output_schema": ANY},
        "needs_review": {"type": "human", "inputs": {"take": ref("nodes.takes.output.take"),
                                                        "feedback": ref("nodes.takes.output.feedback")},
                         "output_schema": obj(take=ANY)},
        "gather_selected": {"type": "join", "join": "selected", "output_schema": ANY,
                            "inputs": {"approved": ref("nodes.approved.output", optional=True, default=None),
                                       "reviewed": ref("nodes.needs_review.output", optional=True, default=None)}},
        "selected_take": code("selected_take", {"approved": ref("nodes.gather_selected.output.approved"),
                                                 "reviewed": ref("nodes.gather_selected.output.reviewed")}),
    }
    names = ["first_frame", "gather_references", "stage_references", "reference_names", "takes", "accepted"]
    edges = [{"source": a, "target": b} for a, b in zip(names, names[1:])]
    edges += [{"source": "shot_context", "target": "frame_takes"},
              {"source": "frame_takes", "target": "frame_accepted"},
              {"source": "frame_accepted", "target": "approved_frame", "when": True},
              {"source": "frame_accepted", "target": "frame_attention", "when": False},
              {"source": "approved_frame", "target": "frame_choice"},
              {"source": "frame_attention", "target": "frame_choice"},
              {"source": "frame_choice", "target": "first_frame"}]
    edges += [{"source": "accepted", "target": "approved", "when": True},
              {"source": "accepted", "target": "needs_review", "when": False},
              {"source": "approved", "target": "gather_selected"},
              {"source": "needs_review", "target": "gather_selected"},
              {"source": "gather_selected", "target": "selected_take"}]
    return graph(nodes, {"clip": ref("nodes.selected_take.output.clip"),
                         "frame_accepted": ref("nodes.frame_takes.output.accepted"),
                         "frame_feedback": ref("nodes.frame_takes.output.feedback"),
                         "last_frame": ref("nodes.selected_take.output.last_frame"),
                         "tail": ref("nodes.selected_take.output.tail"),
                         "voice_references": ref("nodes.selected_take.output.voice_references"),
                         "continuity": ref("nodes.selected_take.output.continuity"),
                         "shot_id": ref("input.item.id"), "take": ref("nodes.selected_take.output")}, edges)


def reference_graph(max_takes):
    attempt = graph({
        "prepare": code("reference_prompt", {"item": ref("input.item"), "index": ref("input.index"),
                                              "attempt": ref("input.attempt"), "feedback": ref("input.feedback")}),
        "generate": tool("image", {"prompt": ref("nodes.prepare.output.prompt"), "references": val([]),
                                    "options": ref("nodes.prepare.output.options")}, ASSET),
        "review_inputs": code("reference_review_inputs", {"asset": ref("nodes.generate.output")}),
        "preview": tool("vision_preview", {"assets": ref("nodes.review_inputs.output.assets")}),
        "review": model("reference_review", {"images": ref("nodes.preview.output.images"),
                                              "asset": ref("input.item")},
                        obj(accepted={"type": "boolean"}, feedback=STRING), vision=True, tokens=1536),
    }, {"item": ref("input.item"), "index": ref("input.index"), "attempt": ref("nodes.prepare.output.attempt"),
        "asset": ref("nodes.generate.output"), "accepted": ref("nodes.review.output.accepted"),
        "feedback": ref("nodes.review.output.feedback")})
    nodes = {
        "takes": {"type": "loop", "inputs": {"item": ref("input.item"), "index": ref("input.index"),
                    "attempt": val(0), "feedback": val("")}, "body": attempt, "max_iterations": max_takes,
                    "until": {"left": ref("input.accepted"), "op": "truthy"}, "output_schema": ANY},
        "accepted": {"type": "condition", "condition": {"left": ref("nodes.takes.output.accepted"), "op": "truthy"},
                     "output_schema": obj(value={"type": "boolean"})},
        "approved": {"type": "transform", "inputs": {"frame": ref("nodes.takes.output.asset")}, "output_schema": obj(frame=ASSET)},
        "needs_review": {"type": "human", "inputs": {"frame": ref("nodes.takes.output.asset"),
                            "feedback": ref("nodes.takes.output.feedback")}, "output_schema": obj(frame=ASSET)},
        "choice": {"type": "join", "join": "selected", "output_schema": ANY,
                   "inputs": {"approved": ref("nodes.approved.output", optional=True, default=None),
                              "reviewed": ref("nodes.needs_review.output", optional=True, default=None)}},
        "selected_reference": code("selected_frame", {"approved": ref("nodes.choice.output.approved"),
                                                        "reviewed": ref("nodes.choice.output.reviewed")}, ASSET),
    }
    edges = [{"source": "takes", "target": "accepted"},
             {"source": "accepted", "target": "approved", "when": True},
             {"source": "accepted", "target": "needs_review", "when": False},
             {"source": "approved", "target": "choice"}, {"source": "needs_review", "target": "choice"},
             {"source": "choice", "target": "selected_reference"}]
    return graph(nodes, {"id": ref("input.item.id"), "kind": ref("input.item.kind"),
                         "review": ref("nodes.takes.output"),
                         "asset": ref("nodes.selected_reference.output")}, edges)


def build(max_takes=2, max_frame_takes=2, *, enable_voice=False, max_reference_takes=2,
          review_policy="continue"):
    if review_policy not in {"continue", "pause"}:
        raise ValueError("review_policy must be continue or pause")
    if any(not 1 <= limit <= 3 for limit in (max_takes, max_frame_takes, max_reference_takes)):
        raise ValueError("take limits must be between one and three")
    request = {**BRIEF, "required": ["source_text"]}
    request["properties"] = {**BRIEF["properties"], "series": {"type": "object", "properties": {
        "characters": PLAN["properties"]["characters"], "locations": PLAN["properties"]["locations"],
        "style": STRING, "references": {"type": "array", "maxItems": 8, "items": obj(id=TEXT, kind={"enum": ["character", "location"]}, asset=ASSET)},
        "voices": {"type": "array", "maxItems": 5, "items": obj(id=TEXT, asset=ASSET)}}, "additionalProperties": False}, "voices": {
        "type": "array", "maxItems": 5, "items": obj(id=TEXT, asset=ASSET)}}
    b = Builder("episode-studio", request,
                obj(film=ASSET, plan=PLAN, shots=ANY, series=ANY,
                    notes={"type": "array", "items": obj(stage=TEXT, id=TEXT, feedback=STRING)},
                    voices={"type": "array", "items": obj(id=TEXT, asset=ASSET)}), spec_version="0.3")
    b.model("main", "main", ["text", "structured_output"])
    b.model("vision", "vision", ["text", "structured_output", "vision"])
    for name in ["creative_director", "source_reader", "producer", "script_editor", "art_director", "reference_review", "shot_director", "frame_review", "render_engineer", "continuity_review"]:
        b.resource(name, f"prompts/{name}.md")
    if enable_voice:
        b.resource("voice_director", "prompts/voice_director.md")
        b.resource("voice_valid", "code/voice_valid.py", role="code")
        b.tool("voice", "media.generate_voice")
    for name in ["continuity", "cinematography", "screenwriting", "video_prompting"]:
        b.skill(name, f"skills/{name}.md")
    for name in ["shot_context", "gather_references", "reference_names", "render_settings", "select_clip",
                 "review_images", "record_take", "selected_take", "timeline", "plan_valid", "art_valid",
                 "frame_settings", "frame_review_inputs", "selected_frame", "render_valid", "source_valid", "reference_prompt",
                 "production_brief", "direction_valid", "reference_review_inputs", "voice_catalog", "production_notes", "reference_plan", "reference_catalog", "series_catalog", "supplied_voices", "schedule_plan"]:
        b.resource(name, f"code/{name}.py", role="code")
    for name, plugin in {"python": "code.python", "image": "media.generate_image", "stage": "media.stage_reference",
                         "recipe": "film.recipe", "render_profile": "film.settings", "render": "film.render", "ingest": "media.ingest_comfy",
                         "inspect": "media.inspect_video", "vision_preview": "media.vision",
                         "frame_preview": "media.frame_vision", "compose": "media.compose"}.items():
        b.tool(name, plugin)
    assets = reference_graph(max_reference_takes)
    nodes = {
        "creative_director": model("creative_director", {"request": ref("input")}, DIRECTION,
                                    tokens=6000, validator="direction_valid"),
        "production_brief": code("production_brief", {"request": ref("input"),
                                                        "direction": ref("nodes.creative_director.output")}, BRIEF),
        "source_reader": model("source_reader", {"source_text": ref("nodes.production_brief.output.source_text"),
                               "cast": ref("input.series.characters", optional=True, default=[])},
                               SOURCE, tokens=6000, validator="source_valid"),
        "producer": model("producer", {"brief": ref("nodes.production_brief.output"), "source": ref("nodes.source_reader.output"),
                           "series": ref("input.series", optional=True, default={}), "schedule_by_tool": val(True)},
                          PLAN, tokens=12000, validator="plan_valid"),
        "draft_schedule": code("schedule_plan", {"plan": ref("nodes.producer.output"),
                                "brief": ref("nodes.production_brief.output")}, PLAN),
        "draft_timing": code("plan_valid", {"output": ref("nodes.draft_schedule.output"),
                                            "brief": ref("nodes.production_brief.output"),
                                            "source": ref("nodes.source_reader.output")}),
        "script_editor": model("script_editor", {"brief": ref("nodes.production_brief.output"), "draft": ref("nodes.draft_schedule.output"),
                                                   "timing": ref("nodes.draft_timing.output"),
                                                   "source": ref("nodes.source_reader.output"), "series": ref("input.series", optional=True, default={}), "schedule_by_tool": val(True)},
                               PLAN, tokens=12000, validator="plan_valid"),
        "shooting_plan": code("schedule_plan", {"plan": ref("nodes.script_editor.output"),
                                "brief": ref("nodes.production_brief.output")}, PLAN),
        "art_director": model("art_director", {"plan": ref("nodes.shooting_plan.output"), "style": ref("nodes.production_brief.output.style")}, ART, tokens=6000, validator="art_valid"),
        "render_profile": tool("render_profile", {}),
        "reference_plan": code("reference_plan", {"assets": ref("nodes.art_director.output.assets"),
                                "supplied": ref("input.series.references", optional=True, default=[])}),
        "reference_library": {"type": "map", "items": ref("nodes.reference_plan.output.pending"),
                              "inputs": {},
                              "body": assets, "max_items": 8, "output_schema": ANY},
        "reference_catalog": code("reference_catalog", {"reused": ref("nodes.reference_plan.output.reused"),
                                "generated": ref("nodes.reference_library.output.items")}),
        "supplied_voices": code("supplied_voices", {"series": ref("input.series.voices", optional=True, default=[]),
                                "voices": ref("input.voices", optional=True, default=[])}),
        "shots": {"type": "map", "items": ref("nodes.script_editor.output.shots"),
                  "inputs": {"plan": ref("nodes.shooting_plan.output"), "art": ref("nodes.art_director.output"),
                             "assets": ref("nodes.reference_catalog.output.items"),
                             "voices": ref("nodes.supplied_voices.output.voices"),
                             "render_profile": ref("nodes.render_profile.output")},
                  "carry": val({"last_frame": None, "continuity": {}, "shot_id": ""}),
                  "body": shot_graph(max_takes, max_frame_takes), "max_items": 24, "output_schema": ANY},
        "production_notes": code("production_notes", {"shots": ref("nodes.shots.output.items"),
                                                       "references": ref("nodes.reference_catalog.output.items")}),
        "voice_catalog": code("voice_catalog", {"shots": ref("nodes.shots.output.items"),
                                                 "supplied": ref("nodes.supplied_voices.output.voices")}),
        "series_catalog": code("series_catalog", {"plan": ref("nodes.shooting_plan.output"),
                                 "style": ref("nodes.art_director.output.style"),
                                 "references": ref("nodes.reference_catalog.output.items"),
                                 "voices": ref("nodes.voice_catalog.output.voices")}),
        "timeline": code("timeline", {"shots": ref("nodes.shots.output.items")}),
        "assemble": tool("compose", {"clips": ref("nodes.timeline.output.clips"), "preserve_audio": val(True)}, ASSET),
    }
    if enable_voice:
        voice_nodes = {
            "voice_director": model("voice_director", {"plan": ref("nodes.shooting_plan.output"),
                "language": ref("nodes.production_brief.output.language")}, VOICES, validator="voice_valid"),
            "voice_library": {"type": "map", "items": ref("nodes.voice_director.output.voices"),
                "inputs": {}, "max_items": 5, "output_schema": ANY,
                "body": graph({"record": tool("voice", {"text": ref("input.item.text"),
                    "speaker": ref("input.item.speaker"), "direction": ref("input.item.direction"),
                    "seed": ref("input.item.seed"), "max_seconds": val(5)}, ASSET)},
                    {"id": ref("input.item.id"), "asset": ref("nodes.record.output")})},
        }
        # Finish the voice library before images to avoid alternating model loads.
        position = list(nodes).index("reference_library")
        nodes = dict(list(nodes.items())[:position] + list(voice_nodes.items()) + list(nodes.items())[position:])
        nodes["shots"]["inputs"]["voices"] = ref("nodes.voice_library.output.items")
    b.data["graph"] = graph(nodes, {"film": ref("nodes.assemble.output"), "plan": ref("nodes.shooting_plan.output"),
                                    "notes": ref("nodes.production_notes.output.notes"),
                                    "shots": ref("nodes.shots.output"), "voices": ref("nodes.voice_catalog.output.voices"),
                                    "series": ref("nodes.series_catalog.output")})
    if review_policy == "continue":
        def continue_after_limit(flow):
            for name, node in list(flow["nodes"].items()):
                if node["type"] == "human":
                    flow["nodes"][name] = {"type": "transform", "output_schema": node["output_schema"],
                        "inputs": {key: node["inputs"][key] for key in node["output_schema"]["properties"]}}
                elif "body" in node:
                    continue_after_limit(node["body"])
        continue_after_limit(b.data["graph"])
    return b.execution(max_steps=5000, max_model_calls=240, max_total_tokens=1000000,
                       max_output_tokens=4096, max_parallel_nodes=2, max_parallel_tools=2,
                       pure_checkpoint_interval=16,
                       allow_side_effects=True, timeout_seconds=21600)


if __name__ == "__main__":
    save_spec(build().build_spec(), Path(__file__).with_name("agent.yaml"))
