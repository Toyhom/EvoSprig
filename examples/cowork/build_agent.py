"""CoworkOS's main/coordinator/specialist pattern, built with EvoSprig."""

from pathlib import Path

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
DOC = obj(name=TEXT, content=TEXT)
TASK = obj(role={"type": "string", "pattern": "^[a-zA-Z][a-zA-Z0-9_-]{0,63}$"}, task=TEXT, document=TEXT)
PLAN = obj(title=TEXT, tasks={"type": "array", "items": TASK, "minItems": 1, "maxItems": 6})


def build(*, rsi=False):
    b = Builder(
        "cowork-rsi" if rsi else "cowork",
        obj(request=TEXT),
        obj(report={"type": "object"}, team={"type": "object"}, follow_up=TEXT),
        spec_version="0.3",
    )
    b.model("main", "main", ["text", "tool_calling", "structured_output"])
    for name in ["plan", "specialist", "editor", "follow_up", "acceptance"]:
        b.resource(name, "prompts/" + name + ".md")
    b.skill("collaboration", "prompts/collaboration.md")
    for name in ["list", "read", "write", "history", "wait"]:
        b.tool(name, "workspace." + name)
    for name in ["context", "search", "write"]:
        b.tool("memory_" + name, "memory." + name)
    for name in ["send", "receive", "ack", "wait"]:
        b.tool("peer_" + name, "messages." + name)
    b.node("context", "tool", tool="memory_context", inputs={}, output_schema={"type": "object"})
    b.node(
        "plan",
        "agent",
        model="main",
        instructions={"resource": "plan"},
        skills=["collaboration"],
        tools=["list", "read"],
        tool_errors="feedback",
        max_tool_rounds=6,
        response_format="json",
        output_errors="feedback",
        max_output_retries=2,
        inputs={"request": {"ref": "input.request"}, "memory": {"ref": "nodes.context.output"}},
        output_schema=PLAN,
    )
    body = {
        "entry": "specialist",
        "nodes": {
            "specialist": {
                "type": "agent",
                "model": "main",
                "instructions": {"resource": "specialist"},
                "skills": ["collaboration"],
                "tools": ["list", "read", "memory_search", "peer_send", "peer_receive", "peer_ack", "peer_wait"],
                "mailbox": {"ref": "input.item.role"},
                "tool_errors": "feedback",
                "max_tool_rounds": 8,
                "parallel_tool_calls": True,
                "response_format": "json",
                "output_errors": "feedback",
                "max_output_retries": 2,
                "inputs": {
                    "assignment": {"ref": "input.item"},
                    "request": {"ref": "input.context.request"},
                    "roster": {"ref": "input.context.roster"},
                },
                "max_output_tokens": 4096,
                "output_schema": obj(content=TEXT),
            },
            "current": {
                "type": "tool",
                "tool": "read",
                "inputs": {"name": {"ref": "input.item.document"}},
                "output_schema": {"type": "object"},
            },
            "save": {
                "type": "agent",
                "model": "main",
                "instructions": {"resource": "editor"},
                "tools": ["read", "write"],
                "tool_errors": "feedback",
                "max_tool_rounds": 8,
                "response_format": "json",
                "output_errors": "feedback",
                "inputs": {
                    "name": {"ref": "input.item.document"},
                    "draft": {"ref": "nodes.specialist.output.content"},
                    "current": {"ref": "nodes.current.output"},
                },
                "output_schema": obj(
                    name=TEXT, revision={"type": "integer", "minimum": 1}, summary=TEXT
                ),
            },
        },
        "edges": [
            {"source": "specialist", "target": "current"},
            {"source": "current", "target": "save"},
        ],
        "output": {"assignment": {"ref": "input.item"}, "document": {"ref": "nodes.save.output"}},
    }
    b.map(
        "team",
        items={"ref": "nodes.plan.output.tasks"},
        inputs={"request": {"ref": "input.request"}},
        body=body,
        max_items=6,
        output_schema={"type": "object"},
    )
    # Main reviews each wave and can delegate targeted follow-up assignments.
    dispatch = b.data["graph"]["nodes"].pop("team")
    dispatch["items"] = {"ref": "input.tasks"}
    dispatch["inputs"] = {"request": {"ref": "input.request"}, "roster": {"ref": "input.tasks"}}
    verdict = obj(
        content=TEXT,
        accepted={"type": "boolean"},
        tasks={"type": "array", "items": TASK, "maxItems": 6},
    )
    verdict["allOf"] = [
        {
            "if": {"properties": {"accepted": {"const": False}}},
            "then": {"properties": {"tasks": {"minItems": 1}}},
            "else": {"properties": {"tasks": {"maxItems": 0}}},
        }
    ]
    b.node(
        "team",
        "loop",
        inputs={"request": {"ref": "input.request"}, "tasks": {"ref": "nodes.plan.output.tasks"}},
        max_iterations=3,
        until={"left": {"ref": "input.accepted"}, "op": "truthy"},
        body={
            "entry": "dispatch",
            "nodes": {
                "dispatch": dispatch,
                "acceptance": {
                    "type": "agent",
                    "model": "main",
                    "instructions": {"resource": "acceptance"},
                    "skills": ["collaboration"],
                    "tools": ["read", "list", "peer_send", "peer_receive", "peer_ack"],
                    "mailbox": "main",
                    "parallel_tool_calls": True,
                    "tool_errors": "feedback",
                    "max_tool_rounds": 10,
                    "response_format": "json",
                    "output_errors": "feedback",
                    "max_output_retries": 2,
                    "inputs": {
                        "request": {"ref": "input.request"},
                        "wave": {"ref": "nodes.dispatch.output"},
                    },
                    "output_schema": verdict,
                },
            },
            "edges": [{"source": "dispatch", "target": "acceptance"}],
            "output": {
                "request": {"ref": "input.request"},
                "tasks": {"ref": "nodes.acceptance.output.tasks"},
                "accepted": {"ref": "nodes.acceptance.output.accepted"},
                "content": {"ref": "nodes.acceptance.output.content"},
                "last_wave": {"ref": "nodes.dispatch.output"},
            },
        },
        output_schema={"type": "object"},
    )
    b.node(
        "review",
        "human",
        inputs={
            "draft": {"ref": "nodes.team.output.content"},
            "team": {"ref": "nodes.team.output"},
        },
        output_schema=obj(content=TEXT),
    )
    b.node(
        "publish",
        "agent",
        model="main",
        instructions={"resource": "editor"},
        tools=["read", "write"],
        tool_errors="feedback",
        max_tool_rounds=8,
        response_format="json",
        output_errors="feedback",
        inputs={
            "name": {"value": "deliverables/brief.md"},
            "draft": {"ref": "nodes.review.output.content"},
        },
        output_schema=obj(name=TEXT, revision={"type": "integer", "minimum": 1}, summary=TEXT),
    )
    b.node(
        "remember",
        "tool",
        tool="memory_write",
        inputs={
            "content": {"ref": "nodes.publish.output.summary"},
            "source": {"value": "deliverables/brief.md"},
        },
        output_schema={"type": "object"},
    )
    b.node(
        "wake",
        "tool",
        tool="wait",
        inputs={
            "seconds": {"ref": "input.follow_up_seconds", "optional": True, "default": 0},
            "message": {
                "value": "Review the latest project documents and prepare the next actions."
            },
        },
        output_schema={"type": "object"},
    )
    b.node(
        "follow_up",
        "agent",
        model="main",
        instructions={"resource": "follow_up"},
        tools=["list", "read", "memory_search"],
        tool_errors="feedback",
        max_tool_rounds=6,
        inputs={"request": {"ref": "input.request"}, "wake": {"ref": "nodes.wake.output"}},
        output_schema=obj(text=TEXT),
    )
    b.data["input_schema"]["properties"]["follow_up_seconds"] = {
        "type": "number",
        "minimum": 0,
        "maximum": 604800,
    }
    seq = [
        "context",
        "plan",
        "team",
        "review",
        "publish",
        "remember",
        "wake",
        "follow_up",
    ]
    if rsi:
        b.node(
            "lessons",
            "tool",
            tool="memory_search",
            inputs={"query": {"ref": "input.request"}, "limit": {"value": 5}},
            output_schema={"type": "object"},
        )
        seq.insert(seq.index("plan"), "lessons")
        b.data["graph"]["nodes"]["plan"]["inputs"]["lessons"] = {"ref": "nodes.lessons.output"}
        b.resource("retrospective", "prompts/retrospective.md")
        b.node(
            "retrospective",
            "model",
            model="main",
            instructions={"resource": "retrospective"},
            response_format="json",
            output_errors="feedback",
            max_output_retries=2,
            inputs={
                "request": {"ref": "input.request"},
                "team_review": {"ref": "nodes.team.output"},
                "approved_document": {"ref": "nodes.review.output.content"},
            },
            output_schema=obj(memory=TEXT),
            max_output_tokens=1200,
        )
        seq.insert(seq.index("remember"), "retrospective")
        b.data["graph"]["nodes"]["remember"]["inputs"]["content"] = {
            "ref": "nodes.retrospective.output.memory"
        }
    for left, right in zip(seq, seq[1:]):
        b.edge(left, right)
    b.output(
        report={"ref": "nodes.publish.output"},
        team={"ref": "nodes.team.output"},
        follow_up={"ref": "nodes.follow_up.output.text"},
    )
    b.execution(
        allow_side_effects=True,
        max_steps=640,
        max_model_calls=128,
        max_total_tokens=500000,
        max_output_tokens=4096,
        max_parallel_nodes=3,
        max_parallel_tools=3,
        timeout_seconds=1200,
    )
    def configure_harness(graph):
        for node in graph["nodes"].values():
            if node["type"] == "agent":
                node["harness"] = {
                    "max_tool_rounds": node.get("max_tool_rounds", 8),
                    "tool_errors": "feedback",
                    "output_errors": "feedback",
                    "max_output_retries": node.get("max_output_retries", 1),
                }
            if node.get("body"):
                configure_harness(node["body"])
            for branch in node.get("branches", {}).values():
                configure_harness(branch)

    configure_harness(b.data["graph"])
    return b.build_spec()


if __name__ == "__main__":
    save_spec(build(), Path(__file__).with_name("agent.yaml"))
    save_spec(build(rsi=True), Path(__file__).with_name("rsi-agent.yaml"))
