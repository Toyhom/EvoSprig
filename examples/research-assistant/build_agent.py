"""A small evidence-and-tool assistant shared by the evolution demonstration."""

from pathlib import Path

from evosprig.core.spec import save_spec
from evosprig.sdk import Builder

INPUT = {
    "type": "object",
    "properties": {"question": {"type": "string"}, "evidence": {"type": "string"}},
    "required": ["question", "evidence"],
    "additionalProperties": False,
}
OUTPUT = {
    "type": "object",
    "properties": {"answer": {"type": "string"}},
    "required": ["answer"],
    "additionalProperties": False,
}

spec = (
    Builder("research-assistant", INPUT, OUTPUT)
    .model("research", "main", ["text", "structured_output", "tool_calling"])
    .tool("add", "builtin.add")
    .tool("retrieve", "documents.search")
    .resource("instructions", "prompts/assistant.md")
    .node(
        "answer",
        "agent",
        model="research",
        instructions={"resource": "instructions"},
        tools=["add", "retrieve"],
        response_format="json",
        inputs={"question": {"ref": "input.question"}, "evidence": {"ref": "input.evidence"}},
        output_schema=OUTPUT,
    )
    .output(answer={"ref": "nodes.answer.output.answer"})
    .execution(
        max_steps=8,
        max_model_calls=3,
        max_total_tokens=8192,
        max_output_tokens=192,
        timeout_seconds=90.0,
    )
    .build_spec()
)

if __name__ == "__main__":
    save_spec(spec, Path(__file__).with_name("agent.yaml"))
