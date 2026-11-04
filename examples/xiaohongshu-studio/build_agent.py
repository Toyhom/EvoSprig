"""A source-aware writing desk using EvoSprig's native revision loop."""

from pathlib import Path

from evosprig.core.spec import save_spec
from evosprig.sdk import Builder


def obj(**fields):
    return {"type": "object", "properties": fields, "required": list(fields), "additionalProperties": False}


TEXT = {"type": "string"}
STRINGS = {"type": "array", "items": TEXT, "maxItems": 12}
ANY = {"type": "object"}
POST = obj(title={"type": "string", "minLength": 1}, body={"type": "string", "minLength": 1},
           tags={"type": "array", "items": {"type": "string", "minLength": 1}, "minItems": 1, "maxItems": 8})
BRIEF = obj(reader_need=TEXT, angle=TEXT, facts=STRINGS, qualifications=STRINGS,
            example_id=TEXT, structure=TEXT)
REVIEW = obj(accepted={"type": "boolean"}, reader_feedback=STRINGS,
             factual_issues=STRINGS, edits=STRINGS)


def ref(path):
    return {"ref": path}


def build():
    inputs = obj(
        source={"type": "string", "minLength": 1, "maxLength": 12000},
        audience={"type": "string", "maxLength": 500},
        voice={"enum": ["observer", "brand", "personal"]},
        emoji={"enum": ["none", "light", "lively"]},
        goal={"type": "string", "maxLength": 500},
        required_terms=STRINGS,
        links={"type": "array", "maxItems": 3, "items": {"type": "string", "pattern": "^https?://[^\\s]+$", "maxLength": 300}},
        references={"type": "array", "maxItems": 3, "items": {"type": "string", "maxLength": 2000}},
        max_title_chars={"type": "integer", "minimum": 10, "maximum": 60},
        max_body_chars={"type": "integer", "minimum": 100, "maximum": 1500},
    )
    inputs["required"] = ["source"]
    b = Builder("xiaohongshu-studio", inputs,
                obj(text=TEXT, post=POST, ready={"type": "boolean"}, feedback=STRINGS,
                    rounds={"type": "integer"}, changes={"type": "array"}), spec_version="0.3")
    b.model("main", "main", ["text", "structured_output"])
    b.tool("python", "code.python")
    for name in ["prepare", "check", "remember", "format"]:
        b.resource(name, f"code/{name}.py", role="code")
    for name in ["brief", "draft", "review"]:
        b.resource(name, f"prompts/{name}.md")
    for name in ["voice", "source_fidelity", "examples"]:
        b.skill(name, f"skills/{name}.md")

    def code(name, bindings):
        return {"type": "code", "tool": "python", "code": name, "inputs": bindings, "output_schema": ANY}

    def model(name, bindings, schema, skills):
        return {"type": "agent", "model": "main", "instructions": {"resource": name},
                "inputs": bindings, "skills": skills, "output_schema": schema, "response_format": "json",
                "temperature": 0.6 if name == "draft" else 0.2,
                "harness": {"output_errors": "feedback", "max_output_retries": 1, "max_output_tokens": 2400,
                            "max_tool_rounds": 1}}

    def add(name, node):
        b.node(name, node.pop("type"), **node)

    add("prepare", code("prepare", {"request": ref("input")}))
    add("brief", model("brief", {"request": ref("nodes.prepare.output")}, BRIEF,
                       ["source_fidelity", "examples"]))
    body = {
        "entry": "draft",
        "nodes": {
            "draft": model("draft", {"request": ref("input.request"), "brief": ref("input.brief"),
                                     "previous": ref("input.previous"), "feedback": ref("input.feedback")},
                           POST, ["voice", "source_fidelity", "examples"]),
            "check": code("check", {"request": ref("input.request"), "post": ref("nodes.draft.output")}),
            "review": model("review", {"request": ref("input.request"), "brief": ref("input.brief"),
                                       "post": ref("nodes.draft.output"), "checks": ref("nodes.check.output")},
                            REVIEW, ["voice", "source_fidelity"]),
            "remember": code("remember", {"state": ref("input"), "post": ref("nodes.draft.output"),
                                          "checks": ref("nodes.check.output"), "review": ref("nodes.review.output")}),
        },
        "edges": [{"source": a, "target": z} for a, z in
                  [("draft", "check"), ("check", "review"), ("review", "remember")]],
        "output": {name: ref("nodes.remember.output." + name) for name in
                   ["request", "brief", "previous", "feedback", "accepted", "rounds", "changes"]},
    }
    b.node("editing", "loop", inputs={"request": ref("nodes.prepare.output"), "brief": ref("nodes.brief.output"),
           "previous": {"value": {}}, "feedback": {"value": []}, "rounds": {"value": 0}, "changes": {"value": []}},
           body=body, max_iterations=3, until={"left": ref("input.accepted"), "op": "truthy"}, output_schema=ANY)
    add("format", code("format", {"state": ref("nodes.editing.output")}))
    b.edge("prepare", "brief").edge("brief", "editing").edge("editing", "format")
    b.output(**{key: ref("nodes.format.output." + key) for key in
                ["text", "post", "ready", "feedback", "rounds", "changes"]})
    b.execution(max_model_calls=16, max_total_tokens=65000, max_output_tokens=2400,
                max_steps=48, timeout_seconds=600, allow_side_effects=False)
    return b.build_spec()


if __name__ == "__main__":
    save_spec(build(), Path(__file__).with_name("agent.yaml"))
