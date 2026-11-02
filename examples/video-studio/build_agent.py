"""VideoClaw-style production expressed as portable EvoSprig graphs."""

from pathlib import Path

import yaml

from evosprig.core.spec import save_spec
from evosprig.sdk import Builder


def obj(**properties):
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }


TEXT = {"type": "string", "minLength": 1}
ASSET = obj(id=TEXT, uri=TEXT, media_type=TEXT)
CHARACTER_ASSET = obj(character_id=TEXT, asset=ASSET)
CATALOG = obj(assets={"type": "array", "items": CHARACTER_ASSET, "minItems": 1})
SHOT = obj(
    id=TEXT,
    description=TEXT,
    camera=TEXT,
    dialogue={"type": "string"},
    characters={"type": "array", "items": TEXT},
    duration_seconds={"type": "integer", "minimum": 1, "maximum": 20},
)
PLAN = obj(
    title=TEXT,
    style=TEXT,
    characters={"type": "array", "items": obj(id=TEXT, description=TEXT)},
    shots={"type": "array", "items": SHOT, "minItems": 1, "maxItems": 12},
)
TIMELINE = obj(
    clips={"type": "array", "items": ASSET, "minItems": 1, "maxItems": 20},
    audio={"type": "array", "items": ASSET},
    subtitles={"type": "string"},
)
CONTRACTS = {
    "assets": (obj(characters=PLAN["properties"]["characters"], style=TEXT), CATALOG),
    "image": (obj(shot=SHOT, catalog=CATALOG, style=TEXT), ASSET),
    "video": (obj(shot=SHOT, first_frame=ASSET, catalog=CATALOG), ASSET),
    "compose": (TIMELINE, ASSET),
}


def shot_builder(identifier="video-shot", visual_review=False):
    b = Builder(
        identifier,
        obj(shot=SHOT, catalog=CATALOG, style=TEXT),
        obj(clip=ASSET, first_frame=ASSET),
        spec_version="0.2",
    )
    b.tool("image", "media.image").tool("video", "media.video")
    if visual_review:
        b.data["spec_version"] = "0.3"
        b.model("artist", "main", ["text", "structured_output"])
        b.model("reviewer", "vision", ["text", "structured_output", "vision"])
        b.resource("storyboard", "prompts/storyboard.md")
        b.resource("frame_review", "prompts/frame-review.md")
        b.tool("vision", "media.vision")
        b.node("frame_prompt", "model", entry=True, model="artist",
               instructions={"resource": "storyboard"}, response_format="json",
               inputs={"shot": {"ref": "input.shot"}, "style": {"ref": "input.style"},
                       "feedback": {"ref": "input.feedback", "optional": True, "default": ""}},
               output_schema=obj(prompt=TEXT), max_output_tokens=2048)
    b.node(
        "frame",
        "tool",
        tool="image",
        inputs={k: {"ref": f"input.{k}"} for k in ("shot", "catalog", "style")},
        output_schema=ASSET,
    )
    b.node(
        "frame_review",
        "human",
        inputs={"frame": {"ref": "nodes.frame.output"}, "shot": {"ref": "input.shot"}},
        output_schema=ASSET,
    )
    if visual_review:
        b.data["graph"]["nodes"]["frame"]["inputs"]["prompt"] = {"ref": "nodes.frame_prompt.output.prompt"}
        b.edge("frame_prompt", "frame")
        b.node("preview", "tool", tool="vision",
               inputs={"asset": {"ref": "nodes.frame.output"}},
               output_schema=obj(images={"type": "array", "items": TEXT}))
        b.node("visual_check", "model", model="reviewer",
               instructions={"resource": "frame_review"},
               inputs={"images": {"ref": "nodes.preview.output.images"},
                       "shot": {"ref": "input.shot"}}, image_inputs=["images"],
               response_format="json", max_output_tokens=2048,
               output_schema=obj(acceptable={"type": "boolean"},
                                 issues={"type": "array", "items": TEXT}, recommendation=TEXT))
        b.data["graph"]["nodes"]["frame_review"]["inputs"]["review"] = {"ref": "nodes.visual_check.output"}
    b.node(
        "clip",
        "tool",
        tool="video",
        inputs={
            "shot": {"ref": "input.shot"},
            "catalog": {"ref": "input.catalog"},
            "first_frame": {"ref": "nodes.frame_review.output"},
        },
        output_schema=ASSET,
    )
    if visual_review:
        b.edge("frame", "preview").edge("preview", "visual_check").edge("visual_check", "frame_review")
    else:
        b.edge("frame", "frame_review")
    b.edge("frame_review", "clip")
    b.output(clip={"ref": "nodes.clip.output"}, first_frame={"ref": "nodes.frame_review.output"})
    return b.execution(allow_side_effects=True, max_steps=16, max_output_tokens=2048,
                       max_total_tokens=24000, timeout_seconds=3600)


def production(visual_review=False):
    b = Builder(
        "video-studio",
        obj(brief=TEXT),
        obj(film=ASSET, plan=PLAN, catalog=CATALOG, takes={"type": "object"}),
        spec_version="0.2",
    )
    b.model("director", "main", ["text", "structured_output"])
    b.resource("director", "prompts/director.md")
    b.tool("assets", "media.assets").tool("image", "media.image").tool("video", "media.video").tool(
        "compose", "media.compose"
    )
    b.node(
        "script",
        "model",
        model="director",
        instructions={"resource": "director"},
        response_format="json",
        inputs={"brief": {"ref": "input.brief"}},
        output_schema=PLAN,
    )
    b.node(
        "script_review",
        "human",
        inputs={"plan": {"ref": "nodes.script.output"}},
        output_schema=PLAN,
    )
    b.node(
        "characters",
        "tool",
        tool="assets",
        inputs={
            "characters": {"ref": "nodes.script_review.output.characters"},
            "style": {"ref": "nodes.script_review.output.style"},
        },
        output_schema=CATALOG,
    )
    shot = shot_builder(visual_review=visual_review)
    if visual_review:
        b.model("artist", "main", ["text", "structured_output"])
        b.model("reviewer", "vision", ["text", "structured_output", "vision"])
        b.resource("storyboard", "prompts/storyboard.md")
        b.resource("frame_review", "prompts/frame-review.md")
        b.tool("vision", "media.vision")
    body = shot.data["graph"]
    # A map body receives one shot plus shared production context.
    for node in body["nodes"].values():
        for binding in node["inputs"].values():
            if binding.get("ref") == "input.shot":
                binding["ref"] = "input.item"
            elif binding.get("ref") in {"input.catalog", "input.style"}:
                binding["ref"] = binding["ref"].replace("input.", "input.context.", 1)
    body["output"]["shot"] = {"ref": "input.item"}
    b.map(
        "shots",
        items={"ref": "nodes.script_review.output.shots"},
        inputs={
            "style": {"ref": "nodes.script_review.output.style"},
            "catalog": {"ref": "nodes.characters.output"},
        },
        body=body,
        max_items=12,
        output_schema=obj(
            items={"type": "array", "items": obj(shot=SHOT, clip=ASSET, first_frame=ASSET)}
        ),
    )
    b.node(
        "edit_review",
        "human",
        inputs={
            "takes": {"ref": "nodes.shots.output"},
            "plan": {"ref": "nodes.script_review.output"},
        },
        output_schema=TIMELINE,
    )
    b.node(
        "assemble",
        "tool",
        tool="compose",
        inputs={k: {"ref": f"nodes.edit_review.output.{k}"} for k in TIMELINE["properties"]},
        output_schema=ASSET,
    )
    for a, c in zip(
        ["script", "script_review", "characters", "shots", "edit_review"],
        ["script_review", "characters", "shots", "edit_review", "assemble"],
    ):
        b.edge(a, c)
    return (
        b.output(
            film={"ref": "nodes.assemble.output"},
            plan={"ref": "nodes.script_review.output"},
            catalog={"ref": "nodes.characters.output"},
            takes={"ref": "nodes.shots.output"},
        )
        .execution(
            allow_side_effects=True,
            max_steps=240,
            max_model_calls=32 if visual_review else 1,
            max_total_tokens=150000 if visual_review else 8192,
            max_output_tokens=6000 if visual_review else 4096,
            max_parallel_nodes=3,
            max_parallel_tools=3,
            timeout_seconds=3600,
        )
        .build_spec()
    )


def profile():
    return {
        "models": {
            "main": {
                "base_url": "https://api.deepseek.com",
                "model": "deepseek-flash",
                "api_key_env": "DEEPSEEK_API_KEY",
                "options": {"thinking": {"type": "disabled"}},
            }
        },
        "tools": {
            f"media.{name}": {
                "kind": "external_http",
                "name": f"media.{name}",
                "description": f"Video production {name} service",
                "endpoint": f"http://127.0.0.1:18880/{name}",
                "auth_env": "EVOSPRIG_MEDIA_TOKEN",
                "input_schema": schemas[0],
                "output_schema": schemas[1],
                "side_effect": "write",
                "idempotent": True,
            }
            for name, schemas in CONTRACTS.items()
        },
    }


def script_agent():
    source = production()
    b = Builder("video-script", source.input_schema, obj(plan=PLAN), spec_version="0.3")
    b.model("director", "main", ["text", "structured_output"])
    b.resource("director", "prompts/director.md")
    node = source.graph.nodes["script"].model_dump(exclude={"type"})
    node.update(output_errors="feedback", max_output_retries=1)
    b.node("script", "model", **node).output(plan={"ref": "nodes.script.output"})
    return b.execution(
        max_model_calls=3, max_output_tokens=4096, max_total_tokens=32000
    ).build_spec()


def local_profile():
    result = profile()
    connection = {
        "base_url": "https://api.moonshot.cn/v1", "model": "kimi-k3.1-pro",
        "api_key_env": "MOONSHOT_API_KEY", "timeout_seconds": 300,
        "token_limit_field": "max_completion_tokens", "send_sampling_parameters": False,
        "capabilities": ["text", "structured_output", "tool_calling", "vision"],
        "options": {"reasoning_effort": "low"},
    }
    result["models"] = {"main": connection, "vision": dict(connection)}
    for tool in result["tools"].values():
        tool.pop("auth_env")
    result["tools"]["media.image"]["input_schema"]["properties"]["prompt"] = TEXT
    result["tools"]["media.vision"] = {
        "kind": "http", "name": "media.vision", "description": "Read a generated frame for visual review",
        "endpoint": "http://127.0.0.1:18880/vision", "method": "POST",
        "input_schema": obj(asset=ASSET),
        "output_schema": obj(images={"type": "array", "items": TEXT}),
        "side_effect": "read_only", "max_response_bytes": 2000000,
    }
    return result


def frame_agent():
    b = shot_builder("video-frame", visual_review=True)
    b.data["input_schema"]["properties"]["feedback"] = {"type": "string"}
    for name in ("frame_review", "clip"):
        del b.data["graph"]["nodes"][name]
    b.data["graph"]["edges"] = [edge for edge in b.data["graph"]["edges"]
                                 if edge["target"] not in {"frame_review", "clip"}]
    b.data["graph"]["output"] = {
        "frame": {"ref": "nodes.frame.output"}, "review": {"ref": "nodes.visual_check.output"},
        "prompt": {"ref": "nodes.frame_prompt.output.prompt"},
    }
    b.data["output_schema"] = obj(frame=ASSET, review={"type": "object"}, prompt=TEXT)
    return b.build_spec()


if __name__ == "__main__":
    root = Path(__file__).parent
    save_spec(production(), root / "agent.yaml")
    save_spec(script_agent(), root / "script-agent.yaml")
    save_spec(shot_builder().build_spec(), root / "shot-agent.yaml")
    save_spec(production(visual_review=True), root / "local-agent.yaml")
    save_spec(shot_builder("local-video-shot", visual_review=True).build_spec(), root / "local-shot-agent.yaml")
    save_spec(frame_agent(), root / "frame-agent.yaml")
    (root / "deployment.local.yaml").write_text(yaml.safe_dump(local_profile(), sort_keys=False))
    compose = Builder("video-compose", TIMELINE, obj(film=ASSET), spec_version="0.2").tool(
        "compose", "media.compose"
    )
    compose.node(
        "assemble",
        "tool",
        tool="compose",
        inputs={k: {"ref": f"input.{k}"} for k in TIMELINE["properties"]},
        output_schema=ASSET,
    )
    save_spec(
        compose.output(film={"ref": "nodes.assemble.output"})
        .execution(allow_side_effects=True, timeout_seconds=3600)
        .build_spec(),
        root / "compose-agent.yaml",
    )
    (root / "deployment.example.yaml").write_text(yaml.safe_dump(profile(), sort_keys=False))
