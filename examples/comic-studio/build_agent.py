"""A comic chapter: adapt, share character references, draw panels, typeset pages."""

from pathlib import Path

from evosprig.core.spec import save_spec
from evosprig.plugins.artifact_tools import obj
from evosprig.sdk import Builder

TEXT = {"type": "string"}
ANY = {"type": "object"}
ASSET = obj(id=TEXT, uri=TEXT, media_type=TEXT)
CHARACTERS = {"type": "array", "items": obj(id=TEXT, description=TEXT), "minItems": 1, "maxItems": 3}
PANEL = obj(id=TEXT, description=TEXT, camera=TEXT, characters={"type": "array", "items": TEXT},
            caption={"type": "string", "maxLength": 55}, dialogue={"type": "string", "maxLength": 55})


def build():
    def ref(path):
        return {"ref": path}
    b = Builder("comic-studio", obj(story={"type": "string", "maxLength": 6000}), ANY, spec_version="0.3")
    b.model("main", "main", ["text", "structured_output"])
    b.tool("assets", "media.assets").tool("image", "comic.image").tool("preview", "comic.vision").tool("layout", "artifacts.comic").tool("python", "code.python")
    b.model("vision", "vision", ["text", "structured_output", "vision"])
    b.resource("frame_director", "prompts/frame_director.md").resource("frame_review", "prompts/frame_review.md")
    b.resource("adapter", "prompts/adapter.md").skill("continuity", "skills/continuity.md")
    for name in ["panel", "frame_context", "frame_carry"]:
        b.resource(name, f"code/{name}.py", role="code")
    b.node("adapt", "agent", model="main", instructions={"resource": "adapter"}, skills=["continuity"],
           inputs={"story": ref("input.story")}, response_format="json",
           output_schema=obj(title=TEXT, style=TEXT, characters=CHARACTERS,
                             panels={"type": "array", "items": PANEL, "minItems": 4, "maxItems": 8}),
           harness={"output_errors": "feedback", "max_output_retries": 2, "max_output_tokens": 3200})
    b.node("cast", "tool", tool="assets", inputs={"characters": ref("nodes.adapt.output.characters"),
           "style": ref("nodes.adapt.output.style")}, output_schema=ANY)
    attempt = {"entry": "direct", "nodes": {
        "direct": {"type": "agent", "model": "main", "instructions": {"resource": "frame_director"},
                   "inputs": {"context": ref("input")}, "response_format": "json", "output_schema": obj(prompt=TEXT),
                   "harness": {"output_errors": "feedback", "max_output_retries": 1, "max_output_tokens": 1800}},
        "draw": {"type": "tool", "tool": "image", "inputs": {"prompt": ref("nodes.direct.output.prompt"),
                 "references": ref("input.references"), "options": {"ref": "input.options", "optional": True, "default": {}}}, "output_schema": ASSET},
        "preview": {"type": "tool", "tool": "preview", "inputs": {"asset": ref("nodes.draw.output")}, "output_schema": ANY},
        "review": {"type": "agent", "model": "vision", "instructions": {"resource": "frame_review"},
                   "inputs": {"panel": ref("input.panel"), "images": ref("nodes.preview.output.images")}, "image_inputs": ["images"],
                   "response_format": "json", "output_schema": obj(accepted={"type": "boolean"}, feedback=TEXT),
                   "harness": {"output_errors": "feedback", "max_output_retries": 1, "max_output_tokens": 1200}},
        "remember": {"type": "code", "tool": "python", "code": "frame_carry", "inputs": {"state": ref("input"),
                     "image": ref("nodes.draw.output"), "review": ref("nodes.review.output")}, "output_schema": ANY}},
        "edges": [{"source": a, "target": z} for a,z in zip(["direct", "draw", "preview", "review"], ["draw", "preview", "review", "remember"])],
        "output": {key: ref("nodes.remember.output."+key) for key in ["panel", "style", "references", "reference_ids", "seed", "options", "attempt", "feedback", "accepted", "image"]}}
    body = {"entry": "context", "nodes": {
        "context": {"type": "code", "tool": "python", "code": "frame_context", "inputs": {"panel": ref("input.item"),
                    "catalog": ref("input.context.catalog"), "style": ref("input.context.style"), "index": ref("input.index")}, "output_schema": ANY},
        "takes": {"type": "loop", "inputs": {key: ref("nodes.context.output."+key) for key in ["panel", "style", "references", "reference_ids", "seed", "options", "attempt", "feedback"]},
                  "body": attempt, "max_iterations": 3, "until": {"left": ref("input.accepted"), "op": "truthy"}, "output_schema": ANY},
        "letter": {"type": "code", "tool": "python", "code": "panel", "inputs": {"panel": ref("input.item"),
                   "image": ref("nodes.takes.output.image")}, "output_schema": ANY}},
        "edges": [{"source": "context", "target": "takes"}, {"source": "takes", "target": "letter"}],
        "output": {key: ref("nodes.letter.output."+key) for key in ["image", "caption", "dialogue"]}}
    b.node("panels", "map", items=ref("nodes.adapt.output.panels"), max_items=8,
           inputs={"catalog": ref("nodes.cast.output"), "style": ref("nodes.adapt.output.style")}, body=body, output_schema=ANY)
    b.node("pages", "tool", tool="layout", inputs={"title": ref("nodes.adapt.output.title"),
           "panels": ref("nodes.panels.output.items")}, output_schema=ANY)
    b.edge("adapt", "cast").edge("cast", "panels").edge("panels", "pages")
    b.output(chapter=ref("nodes.pages.output"), plan=ref("nodes.adapt.output"), catalog=ref("nodes.cast.output"),
             panels=ref("nodes.panels.output.items"))
    return b.execution(allow_side_effects=True, max_model_calls=60, max_total_tokens=250000, max_output_tokens=3200,
                       max_steps=250, timeout_seconds=7200).build_spec()


if __name__ == "__main__":
    save_spec(build(), Path(__file__).with_name("agent.yaml"))
