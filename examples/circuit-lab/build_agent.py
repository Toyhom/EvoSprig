"""A native design–simulate–repair loop, using actual ngspice measurements."""

from pathlib import Path

from evosprig.core.spec import save_spec
from evosprig.plugins.artifact_tools import obj
from evosprig.sdk import Builder


def build():
    any_object = {"type": "object"}
    text = {"type": "string"}
    def ref(path):
        return {"ref": path}
    b = Builder("circuit-lab", obj(request=text, analysis={"enum": ["ac", "transient"]}, target=any_object),
                any_object, spec_version="0.3")
    b.model("main", "main", ["text", "structured_output"])
    b.tool("spice", "artifacts.spice").tool("python", "code.python")
    b.resource("designer", "prompts/designer.md").skill("spice_rules", "skills/spice.md")
    b.resource("carry", "code/carry.py", role="code")
    body = {"entry": "design", "nodes": {
        "design": {"type": "agent", "model": "main", "instructions": {"resource": "designer"}, "skills": ["spice_rules"],
                   "inputs": {"request": ref("input.request"), "analysis": ref("input.analysis"), "target": ref("input.target"),
                              "previous": ref("input.previous"), "feedback": ref("input.feedback")},
                   "response_format": "json", "output_schema": obj(netlist=text, explanation=text),
                   "harness": {"output_errors": "feedback", "max_output_retries": 1, "max_output_tokens": 1600}},
        "simulate": {"type": "tool", "tool": "spice", "inputs": {"netlist": ref("nodes.design.output.netlist"),
                     "analysis": ref("input.analysis"), "target": ref("input.target")}, "output_schema": any_object},
        "carry": {"type": "code", "tool": "python", "code": "carry", "inputs": {"state": ref("input"),
                  "design": ref("nodes.design.output"), "simulation": ref("nodes.simulate.output")}, "output_schema": any_object}},
        "edges": [{"source": "design", "target": "simulate"}, {"source": "simulate", "target": "carry"}],
        "output": {key: ref("nodes.carry.output."+key) for key in ["request", "analysis", "target", "previous", "feedback", "accepted", "attempts"]}}
    b.node("engineering", "loop", inputs={"request": ref("input.request"), "analysis": ref("input.analysis"),
           "target": ref("input.target"), "previous": {"value": {}}, "feedback": {"value": {}}, "attempts": {"value": 0}},
           body=body, max_iterations=3, until={"left": ref("input.accepted"), "op": "truthy"}, output_schema=any_object)
    b.output(design=ref("nodes.engineering.output.previous"), simulation=ref("nodes.engineering.output.feedback"),
             accepted=ref("nodes.engineering.output.accepted"), attempts=ref("nodes.engineering.output.attempts"))
    return b.execution(allow_side_effects=True, max_model_calls=8, max_total_tokens=28000, max_output_tokens=1600,
                       max_steps=30, timeout_seconds=500).build_spec()


if __name__ == "__main__":
    save_spec(build(), Path(__file__).with_name("agent.yaml"))
