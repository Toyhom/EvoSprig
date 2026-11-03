"""A repository-maintenance team built with native EvoSprig nodes."""

from pathlib import Path

from evosprig.core.spec import save_spec
from evosprig.sdk import Builder


def obj(**props):
    return {"type": "object", "properties": props, "required": list(props), "additionalProperties": False}


TEXT = {"type": "string"}
ANY = {"type": "object"}


def ref(path):
    return {"ref": path}


def build():
    b = Builder("repository-agent", obj(request=TEXT, check={"type": "string", "minLength": 1}),
                obj(proposal=ANY, decision=ANY), spec_version="0.3")
    b.model("main", "main", ["text", "tool_calling", "structured_output"])
    for name in ["triage", "engineer", "reviewer"]:
        b.resource(name, "prompts/" + name + ".md")
    b.skill("repository", "skills/repository.md")
    b.resource("verdict", "code/verdict.py", role="code")
    b.tool("python", "code.python")
    for name in ["open", "list", "read", "write", "diff", "check"]:
        b.tool(name, "repository." + name)
    for name in ["send", "receive", "ack"]:
        b.tool("peer_" + name, "messages." + name)
    for name in ["read", "write"]:
        b.tool("document_" + name, "workspace." + name)

    def tool(name, inputs):
        return {"type": "tool", "tool": name, "inputs": inputs, "output_schema": ANY}

    def agent(name, inputs, tools, schema, mailbox):
        return {"type": "agent", "model": "main", "instructions": {"resource": name},
                "skills": ["repository"], "mailbox": mailbox, "tools": tools,
                "response_format": "json", "inputs": inputs, "output_schema": schema,
                "harness": {"tool_errors": "feedback", "max_tool_rounds": 12,
                            "output_errors": "feedback", "max_output_retries": 2, "max_output_tokens": 4096}}

    def add(name, node):
        kind = node.pop("type")
        b.node(name, kind, **node)

    add("worktree", tool("open", {}))
    add("triage", agent("triage", {"request": ref("input.request"), "workspace": ref("nodes.worktree.output.workspace")},
        ["list", "read", "document_read", "document_write"], obj(plan=TEXT), "coordinator"))
    add("baseline", tool("check", {"workspace": ref("nodes.worktree.output.workspace"), "check": ref("input.check")}))
    body = {
        "entry": "engineer",
        "nodes": {
            "engineer": agent("engineer", {"request": ref("input.request"), "workspace": ref("input.workspace"),
                "plan": ref("input.plan"), "feedback": ref("input.feedback")},
                ["list", "read", "write", "diff", "peer_send", "peer_receive", "peer_ack", "document_read"], obj(summary=TEXT), "engineer"),
            "checks": tool("check", {"workspace": ref("input.workspace"), "check": ref("input.check")}),
            "patch": tool("diff", {"workspace": ref("input.workspace")}),
            "reviewer": agent("reviewer", {"request": ref("input.request"), "workspace": ref("input.workspace"),
                "patch": ref("nodes.patch.output"), "checks": ref("nodes.checks.output"),
                "summary": ref("nodes.engineer.output.summary")}, ["read", "list", "peer_send", "peer_receive", "peer_ack"],
                obj(accepted={"type": "boolean"}, feedback=TEXT), "reviewer"),
            "verdict": {"type": "code", "tool": "python", "code": "verdict", "inputs": {
                "state": ref("input"), "checks": ref("nodes.checks.output"), "patch": ref("nodes.patch.output"),
                "review": ref("nodes.reviewer.output"), "summary": ref("nodes.engineer.output.summary")}, "output_schema": ANY},
        },
        "edges": [{"source": a, "target": b} for a, b in zip(
            ["engineer", "checks", "patch", "reviewer"], ["checks", "patch", "reviewer", "verdict"])],
        "output": {name: ref("nodes.verdict.output." + name) for name in [
            "request", "workspace", "plan", "check", "accepted", "checks", "patch", "summary", "review", "feedback"]},
    }
    b.node("repair", "loop", inputs={"request": ref("input.request"), "workspace": ref("nodes.worktree.output.workspace"),
        "check": ref("input.check"), "plan": ref("nodes.triage.output.plan"),
        "feedback": ref("nodes.baseline.output.output")}, body=body, max_iterations=3,
        until={"left": ref("input.accepted"), "op": "truthy"}, output_schema=ANY)
    b.node("approval", "human", inputs={"proposal": ref("nodes.repair.output")},
           output_schema=obj(decision={"enum": ["approve", "reject"]}, comment=TEXT))
    for source, target in zip(["worktree", "triage", "baseline", "repair"], ["triage", "baseline", "repair", "approval"]):
        b.edge(source, target)
    b.output(proposal=ref("nodes.repair.output"), decision=ref("nodes.approval.output"))
    b.execution(allow_side_effects=True, max_model_calls=96, max_steps=200, max_total_tokens=240000,
                max_output_tokens=4096, timeout_seconds=3600)
    return b.build_spec()


if __name__ == "__main__":
    save_spec(build(), Path(__file__).with_name("agent.yaml"))
