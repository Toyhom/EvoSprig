"""Explicit construction; reading specs never imports or executes user code."""

from copy import deepcopy

from evosprig.core.spec import AgentSpec


class Builder:
    def __init__(self, project_id: str, input_schema: dict, output_schema: dict):
        self.data = {
            "spec_version": "0.1",
            "id": project_id,
            "input_schema": deepcopy(input_schema),
            "output_schema": deepcopy(output_schema),
            "models": {},
            "tools": {},
            "resources": {},
            "graph": {"entry": "", "nodes": {}, "edges": [], "output": {}},
        }

    def model(self, name: str, binding: str, requires: list[str] | None = None):
        self.data["models"][name] = {"binding": binding, "requires": requires or ["text"]}
        return self

    def tool(self, name: str, plugin: str, version: str = "1"):
        self.data["tools"][name] = {"plugin": plugin, "version": version}
        return self

    def resource(self, name: str, path: str, role: str = "prompt"):
        self.data["resources"][name] = {"path": path, "role": role}
        return self

    def node(self, node_id: str, node_type: str, *, entry: bool = False, **config):
        if node_id in self.data["graph"]["nodes"]:
            raise ValueError(f"duplicate node: {node_id}")
        self.data["graph"]["nodes"][node_id] = {"type": node_type, **deepcopy(config)}
        if entry or not self.data["graph"]["entry"]:
            self.data["graph"]["entry"] = node_id
        return self

    def edge(self, source: str, target: str):
        self.data["graph"]["edges"].append({"source": source, "target": target})
        return self

    def output(self, **bindings):
        self.data["graph"]["output"] = deepcopy(bindings)
        return self

    def execution(self, **limits):
        self.data["execution"] = dict(limits)
        return self

    def build_spec(self) -> AgentSpec:
        return AgentSpec.model_validate(deepcopy(self.data))
