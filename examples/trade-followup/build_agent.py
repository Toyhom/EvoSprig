"""Customer-scoped drafts with factual review and an explicit approval checkpoint."""

from pathlib import Path

from evosprig.core.spec import save_spec
from evosprig.plugins.artifact_tools import obj
from evosprig.sdk import Builder


def build():
    text, any_object = {"type": "string"}, {"type": "object"}
    def ref(path):
        return {"ref": path}
    inputs = obj(customer_id={"type": "string", "pattern": "^[A-Za-z0-9_-]{1,64}$"},
                 thread_id={"type": "string", "pattern": "^[A-Za-z0-9_-]{1,64}$"},
                 product_facts={"type": "array", "items": obj(id=text, text=text), "minItems": 1, "maxItems": 30},
                 conversation=text, language=text, goal=text)
    b = Builder("trade-followup", inputs, any_object, spec_version="0.3")
    b.model("main", "main", ["text", "structured_output"])
    b.tool("python", "code.python").tool("read", "workspace.read").tool("write", "workspace.write")
    for key in ["key", "checks", "record", "facts_valid"]:
        b.resource(key, f"code/{key}.py", role="code")
    for key in ["draft", "review"]:
        b.resource(key, f"prompts/{key}.md")
    b.skill("sales", "skills/sales.md")
    b.node("customer_key", "code", tool="python", code="key", inputs={"request": ref("input")}, output_schema=any_object)
    b.node("history", "tool", tool="read", inputs={"name": ref("nodes.customer_key.output.name")}, output_schema=any_object)
    b.node("context", "code", tool="python", code="checks", inputs={"request": ref("input"),
           "history": ref("nodes.history.output")}, output_schema=any_object)
    draft = obj(subject=text, body=text, claims={"type": "array", "items": obj(sentence=text, fact_id=text)},
                missing_information={"type": "array", "items": text}, next_action=text)
    b.node("writer", "agent", model="main", instructions={"resource": "draft"}, skills=["sales"],
           inputs={"request": ref("input"), "context": ref("nodes.context.output")}, output_schema=draft,
           response_format="json", harness={"output_errors": "feedback", "max_output_retries": 2, "max_output_tokens": 2200})
    b.node("fact_editor", "agent", model="main", instructions={"resource": "review"}, skills=["sales"],
           inputs={"request": ref("input"), "draft": ref("nodes.writer.output"), "context": ref("nodes.context.output")},
           output_schema=draft, response_format="json", output_validator="facts_valid", harness={"output_errors": "feedback", "max_output_retries": 2, "max_output_tokens": 2200})
    b.node("approve", "human", inputs={"draft": ref("nodes.fact_editor.output"), "context": ref("nodes.context.output")},
           output_schema=obj(approved={"type": "boolean"}, note=text))
    b.node("record", "code", tool="python", code="record", inputs={"request": ref("input"),
           "history": ref("nodes.history.output"), "draft": ref("nodes.fact_editor.output"), "approval": ref("nodes.approve.output")}, output_schema=any_object)
    b.node("save", "tool", tool="write", inputs={"name": ref("nodes.customer_key.output.name"),
           "content": ref("nodes.record.output.content"), "expected_revision": ref("nodes.history.output.revision")}, output_schema=any_object)
    names = ["customer_key", "history", "context", "writer", "fact_editor", "approve", "record", "save"]
    for a,z in zip(names,names[1:]):
        b.edge(a,z)
    b.output(draft=ref("nodes.fact_editor.output"), approval=ref("nodes.approve.output"), context=ref("nodes.context.output"),
             customer_document=ref("nodes.save.output.name"))
    return b.execution(allow_side_effects=True, max_model_calls=8, max_total_tokens=32000, max_output_tokens=2200,
                       timeout_seconds=600).build_spec()


if __name__ == "__main__":
    save_spec(build(), Path(__file__).with_name("agent.yaml"))
