"""Resolve node-level edit scope without changing other users of shared resources."""

from __future__ import annotations

import hashlib
from typing import Literal

from pydantic import Field, model_validator

from evosprig.core.spec import AgentSpec, Contract
from evosprig.core.version import compile_snapshot

from .space import SearchSpace, parts, read_pointer, write_pointer


class EvolutionTarget(Contract):
    node: str
    modules: list[Literal["prompt", "skill", "code", "harness", "memory", "model"]] = Field(
        default_factory=lambda: ["prompt"], min_length=1, max_length=6
    )

    @model_validator(mode="after")
    def valid(self):
        keys = parts(self.node)
        if keys[:2] != ["graph", "nodes"] or len(keys) < 3 or keys[-2] != "nodes":
            raise ValueError("target node must be a graph node JSON pointer")
        if len(self.modules) != len(set(self.modules)):
            raise ValueError("target modules must be unique")
        return self

    def prepare(self, base, allowed, search_space):
        data = base.spec.model_dump(mode="json")
        node = read_pointer(data, self.node)
        if not isinstance(node, dict) or node.get("type") not in {"agent", "model", "code"}:
            raise ValueError("choose an agent, model or code node")
        if set(self.modules) & {"harness", "memory"} and node["type"] != "agent":
            raise ValueError("harness and memory evolution need an agent node")
        if "model" in self.modules and node["type"] == "code":
            raise ValueError("model routing needs an agent or model node")
        available = {}
        inline = None
        if "prompt" in self.modules:
            if node["type"] not in {"agent", "model"}:
                raise ValueError("prompt evolution needs an agent or model node")
            if isinstance(node["instructions"], dict):
                available[node["instructions"]["resource"]] = "prompt"
            else:
                inline = node["instructions"]
        if "skill" in self.modules:
            available.update({name: "skill" for name in node["skills"]})
        if "code" in self.modules:
            available.update({name: "code" for name in [node["code"], node["output_validator"]] if name})
        if set(allowed) - set(available):
            raise ValueError("editable resources must belong to the selected node and modules")
        selected = allowed or list(available)
        prefixes = []
        if "harness" in self.modules:
            prefixes.append(self.node + "/harness/")
        if "memory" in self.modules:
            prefixes.append(self.node + "/harness/memory/")
        fields = search_space.fields if search_space else {}
        for path in fields:
            if not any(path.startswith(prefix) for prefix in prefixes) and not (
                "model" in self.modules and path == self.node + "/model"
            ):
                raise ValueError("search fields must stay inside the selected node and modules")
        if search_space and search_space.tool_grants:
            raise ValueError("node-scoped evolution cannot change tool authority")

        resources = dict(base.resources)
        mapping = {}

        def shared_elsewhere(graph, prefix="/graph"):
            names = set()
            for name, item in graph["nodes"].items():
                path = prefix + "/nodes/" + name
                if path != self.node:
                    if isinstance(item["instructions"], dict):
                        names.add(item["instructions"]["resource"])
                    names.update(item["skills"])
                    names.update(n for n in [item["code"], item["output_validator"]] if n)
                if item["body"]:
                    names.update(shared_elsewhere(item["body"], path + "/body"))
                for branch, body in item["branches"].items():
                    names.update(shared_elsewhere(body, path + "/branches/" + branch))
            return names

        shared = shared_elsewhere(data["graph"])

        def isolate(name, content, role, *, force=False):
            if not force and name in base.resources and name not in shared:
                mapping[name] = name
                return name
            suffix = hashlib.sha256((self.node + ":" + name).encode()).hexdigest()[:12]
            stem = "evolve_" + name[:32] + "_" + suffix
            alias, index = stem, 2
            extension = "py" if role == "code" else "md"
            while alias in data["resources"] or f"evolution/{alias}.{extension}" in {
                item["path"] for item in data["resources"].values()
            }:
                alias, index = stem + "_" + str(index), index + 1
            data["resources"][alias] = {"path": f"evolution/{alias}.{extension}", "role": role}
            resources[alias] = content
            mapping[name] = alias
            return alias

        for name in selected:
            alias = isolate(name, resources[name], available[name])
            if node["instructions"] == {"resource": name} and "prompt" in self.modules:
                node["instructions"] = {"resource": alias}
            if "skill" in self.modules:
                node["skills"] = [alias if item == name else item for item in node["skills"]]
            if "code" in self.modules:
                for key in ("code", "output_validator"):
                    if node[key] == name:
                        node[key] = alias
        if inline is not None and not allowed:
            node["instructions"] = {"resource": isolate("inline_prompt", inline, "prompt", force=True)}
        if not mapping and not fields:
            raise ValueError("selected modules have no editable resources or bounded fields")
        write_pointer(data, self.node, node)
        prepared = compile_snapshot(AgentSpec.model_validate(data), resources)
        space = None
        if search_space:
            raw = search_space.model_dump()
            raw["modules"] = {
                module: ["resource:" + mapping.get(t[9:], t[9:]) if t.startswith("resource:") else t
                         for t in targets]
                for module, targets in raw["modules"].items()
            }
            space = SearchSpace.model_validate(raw)
            space.validate_base(prepared, list(mapping.values()))
        return prepared, list(mapping.values()), space, mapping
