"""RAI's observe, reason, manipulate and observe cycle in EvoSprig."""

from pathlib import Path

import yaml

from evosprig.core.spec import save_spec
from evosprig.sdk import Builder


def obj(**props):
    return {
        "type": "object",
        "properties": props,
        "required": list(props),
        "additionalProperties": False,
    }


TEXT = {"type": "string", "minLength": 1}
OBJECT = {"enum": ["red", "blue", "yellow"]}
ACTION = obj(
    kind={"enum": ["move", "finish"]},
    object=OBJECT,
    position={"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3},
)
GOAL = obj(object=OBJECT, kind={"enum": ["in_tray", "on", "unchanged"]}, target=OBJECT)
INPUT = obj(request=TEXT, goals={"type": "array", "items": GOAL, "minItems": 1})
CONTRACTS = {
    "start": obj(scene={"const": "tabletop"}),
    "observe": obj(episode=TEXT),
    "act": obj(episode=TEXT, action=ACTION),
    "check": obj(episode=TEXT, goals=INPUT["properties"]["goals"]),
}


def build():
    b = Builder(
        "rai-manipulation",
        INPUT,
        obj(result={"type": "object"}, episode=TEXT, last_action={"type": "object"}),
        spec_version="0.3",
    )
    b.model("controller", "vision", ["vision", "structured_output", "text"])
    b.resource("controller", "prompts/controller.md")
    b.skill("manipulation", "skills/manipulation.md")
    for name in CONTRACTS:
        b.tool(name, "robot." + name)
    b.node(
        "start",
        "tool",
        tool="start",
        inputs={"scene": {"value": "tabletop"}},
        output_schema={"type": "object"},
    )
    b.node(
        "manipulate",
        "loop",
        max_iterations=8,
        inputs={
            "episode": {"ref": "nodes.start.output.episode"},
            "request": {"ref": "input.request"},
            "last_action": {"value": {}},
        },
        until={"left": {"ref": "input.kind"}, "op": "eq", "right": {"value": "finish"}},
        body={
            "entry": "observe",
            "nodes": {
                "observe": {
                    "type": "tool",
                    "tool": "observe",
                    "inputs": {"episode": {"ref": "input.episode"}},
                    "output_schema": {"type": "object"},
                },
                "decide": {
                    "type": "model",
                    "model": "controller",
                    "instructions": {"resource": "controller"},
                    "skills": ["manipulation"],
                    "inputs": {
                        "request": {"ref": "input.request"},
                        "images": {"ref": "nodes.observe.output.images"},
                        "objects": {"ref": "nodes.observe.output.objects"},
                        "tray": {"ref": "nodes.observe.output.tray"},
                        "last_action": {"ref": "input.last_action"},
                    },
                    "image_inputs": ["images"],
                    "response_format": "json",
                    "output_errors": "feedback",
                    "max_output_retries": 2,
                    "max_output_tokens": 1200,
                    "output_schema": obj(action=ACTION, reasoning=TEXT),
                },
                "act": {
                    "type": "tool",
                    "tool": "act",
                    "inputs": {
                        "episode": {"ref": "input.episode"},
                        "action": {"ref": "nodes.decide.output.action"},
                    },
                    "output_schema": {"type": "object"},
                },
            },
            "edges": [
                {"source": "observe", "target": "decide"},
                {"source": "decide", "target": "act"},
            ],
            "output": {
                "episode": {"ref": "input.episode"},
                "request": {"ref": "input.request"},
                "kind": {"ref": "nodes.decide.output.action.kind"},
                "last_action": {"ref": "nodes.act.output"},
            },
        },
        output_schema={"type": "object"},
    )
    b.node(
        "check",
        "tool",
        tool="check",
        inputs={"episode": {"ref": "nodes.start.output.episode"}, "goals": {"ref": "input.goals"}},
        output_schema={"type": "object"},
    )
    b.edge("start", "manipulate").edge("manipulate", "check")
    b.output(
        result={"ref": "nodes.check.output"},
        episode={"ref": "nodes.start.output.episode"},
        last_action={"ref": "nodes.manipulate.output.last_action"},
    )
    return b.execution(
        allow_side_effects=True,
        max_steps=100,
        max_model_calls=16,
        max_total_tokens=40000,
        max_output_tokens=1200,
        timeout_seconds=900,
    ).build_spec()


def profile():
    return {
        "models": {
            "vision": {
                "base_url": "https://api.moonshot.cn/v1",
                "model": "kimi-k3.1-pro",
                "api_key_env": "MOONSHOT_API_KEY",
                "capabilities": ["text", "vision", "structured_output"],
                "timeout_seconds": 180,
                "token_limit_field": "max_completion_tokens",
                "send_sampling_parameters": False,
                "options": {"reasoning_effort": "low"},
            }
        },
        "tools": {
            "robot." + name: {
                "kind": "http",
                "name": "robot." + name,
                "description": {
                    "start": "Create a Franka tabletop scene",
                    "observe": "Read camera and object poses",
                    "act": "Move one cube or finish",
                    "check": "Check the final physical state",
                }[name],
                "endpoint": "http://127.0.0.1:18890/" + name,
                "method": "POST",
                "input_schema": schema,
                "output_schema": {"type": "object"},
                "side_effect": "write" if name in {"start", "act"} else "read_only",
                "idempotent": name in {"start", "act"},
                "timeout_seconds": 90,
            }
            for name, schema in CONTRACTS.items()
        },
    }


if __name__ == "__main__":
    root = Path(__file__).parent
    save_spec(build(), root / "agent.yaml")
    (root / "deployment.example.yaml").write_text(yaml.safe_dump(profile(), sort_keys=False))
