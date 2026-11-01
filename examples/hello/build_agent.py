from pathlib import Path

from evosprig.core.spec import save_spec
from evosprig.sdk import Builder


def object_schema(properties):
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }


builder = Builder(
    "hello",
    object_schema({"question": {"type": "string"}}),
    object_schema({"answer": {"type": "string"}}),
)
builder.model("main", "main-model").tool("stats", "builtin.text_stats")
builder.resource("instructions", "prompts/assistant.md")
builder.node(
    "measure",
    "tool",
    tool="stats",
    inputs={"text": {"ref": "input.question"}},
    output_schema=object_schema({"characters": {"type": "integer"}, "words": {"type": "integer"}}),
)
builder.node(
    "assistant",
    "model",
    model="main",
    instructions={"resource": "instructions"},
    inputs={
        "question": {"ref": "input.question"},
        "word_count": {"ref": "nodes.measure.output.words"},
    },
    output_schema=object_schema({"text": {"type": "string"}}),
)
builder.edge("measure", "assistant").output(answer={"ref": "nodes.assistant.output.text"})
builder.execution(
    max_steps=12,
    max_model_calls=2,
    max_total_tokens=4096,
    max_output_tokens=256,
    timeout_seconds=60.0,
)
spec = builder.build_spec()

if __name__ == "__main__":
    save_spec(spec, Path(__file__).with_name("agent.yaml"))
