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
VERDICT = obj(accepted={"type": "boolean"}, issues={"type": "array", "items": TEXT}, feedback=STRING,
              continuity=obj(character_positions=STRING, lighting=STRING, props=STRING, end_action=STRING))
CONTROLS = obj(prompt=TEXT, action={"type": "boolean"})
CONTROLS["additionalProperties"] = {"type": ["string", "number", "boolean"]}


def ref(path, **extra):
    return {"ref": path, **extra}


def val(value):
    return {"value": value}


def model(resource, inputs, schema, *, vision=False, tokens=4096, validator=None):
    node = {"type": "agent", "model": "vision" if vision else "main",
            "instructions": {"resource": resource}, "skills": ["continuity", "cinematography"],
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
        "render_engineer": model("render_engineer", {
            "shot": ref("input.context.shot"), "style": ref("input.context.style"),
            "cast": ref("input.context.cast"), "previous": ref("input.context.previous"),
            "feedback": ref("input.feedback"),
            "reference_order": ref("input.reference_order"),
            "render_profile": ref("input.context.render_profile"),
        }, CONTROLS, validator="render_valid"),
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
                         "last_frame": ref("nodes.selected_take.output.last_frame"),
                         "tail": ref("nodes.selected_take.output.tail"),
                         "voice_references": ref("nodes.selected_take.output.voice_references"),
                         "continuity": ref("nodes.selected_take.output.continuity"),
                         "shot_id": ref("input.item.id"), "take": ref("nodes.selected_take.output")}, edges)


def build(max_takes=2, max_frame_takes=2):
    if not 1 <= max_takes <= 3 or not 1 <= max_frame_takes <= 3:
        raise ValueError("take limits must be between one and three")
    b = Builder("episode-studio", obj(source_text=TEXT, style=TEXT, language=TEXT,
                                      target_seconds={"type": "integer", "minimum": 12, "maximum": 300}),
                obj(film=ASSET, plan=PLAN, shots=ANY), spec_version="0.3")
    b.model("main", "main", ["text", "structured_output"])
    b.model("vision", "vision", ["text", "structured_output", "vision"])
    for name in ["source_reader", "producer", "script_editor", "art_director", "shot_director", "frame_review", "render_engineer", "continuity_review"]:
        b.resource(name, f"prompts/{name}.md")
    for name in ["continuity", "cinematography"]:
        b.skill(name, f"skills/{name}.md")
    for name in ["shot_context", "gather_references", "reference_names", "render_settings", "select_clip",
                 "review_images", "record_take", "selected_take", "timeline", "plan_valid", "art_valid",
                 "frame_settings", "frame_review_inputs", "selected_frame", "render_valid", "source_valid", "reference_prompt"]:
        b.resource(name, f"code/{name}.py", role="code")
    for name, plugin in {"python": "code.python", "image": "media.generate_image", "stage": "media.stage_reference",
                         "recipe": "film.recipe", "render_profile": "film.settings", "render": "film.render", "ingest": "media.ingest_comfy",
                         "inspect": "media.inspect_video", "vision_preview": "media.vision", "compose": "media.compose"}.items():
        b.tool(name, plugin)
    assets = graph({"prepare": code("reference_prompt", {"asset": ref("input.item"), "style": ref("input.context.style")}),
                    "generate": tool("image", {"prompt": ref("nodes.prepare.output.prompt"), "references": val([]),
                                                "options": val({"width": 1344, "height": 768, "steps": 40})}, ASSET)},
                   {"id": ref("input.item.id"), "kind": ref("input.item.kind"), "asset": ref("nodes.generate.output")})
    nodes = {
        "source_reader": model("source_reader", {"source_text": ref("input.source_text")},
                               SOURCE, tokens=6000, validator="source_valid"),
        "producer": model("producer", {"brief": ref("input"), "source": ref("nodes.source_reader.output")},
                          PLAN, tokens=12000, validator="plan_valid"),
        "script_editor": model("script_editor", {"brief": ref("input"), "draft": ref("nodes.producer.output"),
                                                   "source": ref("nodes.source_reader.output")},
                               PLAN, tokens=12000, validator="plan_valid"),
        "art_director": model("art_director", {"plan": ref("nodes.script_editor.output"), "style": ref("input.style")}, ART, tokens=6000, validator="art_valid"),
        "render_profile": tool("render_profile", {}),
        "reference_library": {"type": "map", "items": ref("nodes.art_director.output.assets"),
                              "inputs": {"style": ref("nodes.art_director.output.style")},
                              "body": assets, "max_items": 8, "output_schema": ANY},
        "shots": {"type": "map", "items": ref("nodes.script_editor.output.shots"),
                  "inputs": {"plan": ref("nodes.script_editor.output"), "art": ref("nodes.art_director.output"),
                             "assets": ref("nodes.reference_library.output.items"),
                             "render_profile": ref("nodes.render_profile.output")},
                  "carry": val({"last_frame": None, "continuity": {}, "shot_id": ""}),
                  "body": shot_graph(max_takes, max_frame_takes), "max_items": 24, "output_schema": ANY},
        "timeline": code("timeline", {"shots": ref("nodes.shots.output.items")}),
        "assemble": tool("compose", {"clips": ref("nodes.timeline.output.clips"), "preserve_audio": val(True)}, ASSET),
    }
    b.data["graph"] = graph(nodes, {"film": ref("nodes.assemble.output"), "plan": ref("nodes.script_editor.output"),
                                    "shots": ref("nodes.shots.output")})
    return b.execution(max_steps=5000, max_model_calls=240, max_total_tokens=1000000,
                       max_output_tokens=4096, max_parallel_nodes=2, max_parallel_tools=2,
                       allow_side_effects=True, timeout_seconds=3600)


if __name__ == "__main__":
    save_spec(build().build_spec(), Path(__file__).with_name("agent.yaml"))
