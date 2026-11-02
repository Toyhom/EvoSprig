"""Original three-shot growth film; model plans, a separate CPU service renders."""

from pathlib import Path

from evosprig.core.spec import save_spec
from evosprig.sdk import Builder

STORY = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "title": {"type": "string", "minLength": 1, "maxLength": 48},
        "shots": {
            "type": "array",
            "minItems": 3,
            "maxItems": 3,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "caption": {"type": "string", "minLength": 1, "maxLength": 80},
                    "stage": {"enum": ["seed", "sprout", "bloom"]},
                    "palette": {"enum": ["dawn", "day", "night"]},
                },
                "required": ["caption", "stage", "palette"],
            },
        },
    },
    "required": ["title", "shots"],
}
ARTIFACT = {
    "type": "object",
    "properties": {
        "path": {"type": "string"},
        "sha256": {"type": "string"},
        "media_type": {"const": "video/mp4"},
        "duration_seconds": {"const": 18},
        "job_id": {"type": "string"},
    },
    "required": ["path", "sha256", "media_type", "duration_seconds", "job_id"],
    "additionalProperties": False,
}
INPUT = {
    "type": "object",
    "properties": {"brief": {"type": "string"}},
    "required": ["brief"],
    "additionalProperties": False,
}
spec = (
    Builder("short-film", INPUT, ARTIFACT, spec_version="0.2")
    .model("director", "main", ["text", "structured_output"])
    .resource("director", "prompts/director.md")
    .tool("render", "media.render")
    .node(
        "storyboard",
        "model",
        model="director",
        response_format="json",
        instructions={"resource": "director"},
        inputs={"brief": {"ref": "input.brief"}},
        output_schema=STORY,
    )
    .node(
        "review",
        "human",
        inputs={"storyboard": {"ref": "nodes.storyboard.output"}},
        output_schema=STORY,
    )
    .node(
        "render",
        "tool",
        tool="render",
        inputs={"storyboard": {"ref": "nodes.review.output"}},
        output_schema=ARTIFACT,
    )
    .edge("storyboard", "review")
    .edge("review", "render")
    .output(**{key: {"ref": "nodes.render.output." + key} for key in ARTIFACT["properties"]})
    .execution(
        allow_side_effects=True,
        max_steps=8,
        max_model_calls=1,
        max_total_tokens=4096,
        max_output_tokens=768,
        timeout_seconds=120.0,
    )
    .build_spec()
)

if __name__ == "__main__":
    save_spec(spec, Path(__file__).with_name("agent.yaml"))
