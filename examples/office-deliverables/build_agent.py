"""Calculate once, write a brief, then produce editable office files."""

from pathlib import Path

from evosprig.core.spec import save_spec
from evosprig.plugins.artifact_tools import ROWS, obj
from evosprig.sdk import Builder


def build():
    text = {"type": "string", "maxLength": 400}
    any_object = {"type": "object"}
    def ref(path):
        return {"ref": path}
    b = Builder("office-deliverables", obj(rows=ROWS, goal=text), any_object, spec_version="0.3")
    b.model("main", "main", ["text", "structured_output"])
    b.tool("table", "artifacts.table").tool("office", "artifacts.office")
    b.resource("analyst", "prompts/analyst.md").skill("reporting", "skills/reporting.md")
    b.resource("metrics_valid", "code/metrics_valid.py", role="code")
    b.node("calculate", "tool", tool="table", inputs={"rows": ref("input.rows")}, output_schema=any_object)
    b.node("analyst", "agent", model="main", instructions={"resource": "analyst"}, skills=["reporting"],
           inputs={"goal": ref("input.goal"), "metrics": ref("nodes.calculate.output")}, response_format="json",
           output_schema=obj(title={"type": "string", "maxLength": 100}, summary=text,
                             recommendations={"type": "array", "items": {"type": "string", "maxLength": 200}, "minItems": 1, "maxItems": 6}),
           output_validator="metrics_valid", harness={"output_errors": "feedback", "max_output_retries": 2, "max_output_tokens": 1400, "max_tool_result_chars": 8000})
    b.node("deliver", "tool", tool="office", inputs={"rows": ref("input.rows"),
           **{key: ref("nodes.analyst.output."+key) for key in ["title", "summary", "recommendations"]}}, output_schema=any_object)
    b.edge("calculate", "analyst").edge("analyst", "deliver")
    b.output(**{key: ref("nodes.deliver.output."+key) for key in ["files", "directory", "metrics", "summary", "recommendations"]})
    return b.execution(allow_side_effects=True, max_model_calls=4, max_total_tokens=18000,
                       max_output_tokens=1400, timeout_seconds=300).build_spec()


if __name__ == "__main__":
    save_spec(build(), Path(__file__).with_name("agent.yaml"))
