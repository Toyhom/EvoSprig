"""Create the workflow used by the first tutorial."""
from pathlib import Path

from evosprig.core.spec import save_spec
from evosprig.sdk import Builder

DEFAULT_MODEL = "main"
builder = Builder("first-agent", {"type": "object", "properties": {"question": {"type": "string"}},
                                  "required": ["question"]}, {"type": "object"})
builder.default_model(DEFAULT_MODEL)
builder.node("assistant", "model", instructions="Explain the answer in three short, concrete steps.",
             inputs={"question": {"ref": "input.question"}}, output_schema={"type": "object"})
builder.output(answer={"ref": "nodes.assistant.output.text"})
if __name__ == "__main__":
    target = Path(".evosprig/tutorial/agent.yaml")
    target.parent.mkdir(parents=True, exist_ok=True)
    save_spec(builder.build_spec(), target)
    print(target)
