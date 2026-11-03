"""Run a selected graph fragment through the normal durable runtime."""

from __future__ import annotations

import re
from copy import deepcopy
from dataclasses import dataclass

from .expressions import resolve_inputs, resolve_value
from .spec import AgentSpec, Graph


def saved_debug_context(spec, path, checkpoint, initial_input, requested_prefix="graph"):
    """Recover a map item, loop iteration or branch without running its parents."""
    pattern, graph, index = "graph", spec.graph, 0
    segments = []
    while index < len(path):
        name, field = path[index:index + 2]
        node = graph.nodes[name]
        pattern += "/" + re.escape(name)
        if field == "body" and node.body is not None:
            marker = "item" if node.type == "map" else "iteration"
            pattern += "/(" + marker + r"-[0-9]+)"
            segments.append((graph, name, node.type))
            graph, index = node.body, index + 2
        elif field == "branches":
            branch = path[index + 2]
            pattern += "/" + re.escape(branch)
            segments.append((graph, name, branch))
            graph, index = node.branches[branch], index + 3
        else:
            raise ValueError("invalid saved subflow path")
    prefixes = sorted({key.rsplit("/", 1)[0] for key in checkpoint["nodes"]
                       if re.fullmatch(pattern + r"/[^/]+", key)},
                      key=lambda value: [int(part) if part.isdigit() else part for part in re.split(r"(\d+)", value)])
    if not prefixes:
        raise ValueError("this subflow has no saved execution")
    if requested_prefix == "graph" and path:
        requested_prefix = prefixes[-1]
    if requested_prefix not in prefixes:
        raise ValueError("choose a saved execution of the selected subflow")

    def context(current, inputs, prefix):
        return {"input": inputs, "nodes": {
            name: {"output": checkpoint["nodes"][prefix + "/" + name]["output"]}
            for name in current.nodes
            if checkpoint["nodes"].get(prefix + "/" + name, {}).get("status") == "succeeded"}}

    prefix, inputs = "graph", initial_input
    for current, name, kind in segments:
        node = current.nodes[name]
        ctx = context(current, inputs, prefix)
        arguments = checkpoint["nodes"].get(prefix + "/" + name, {}).get("inputs")
        if arguments is None:
            arguments = resolve_inputs(node.inputs, ctx)
        prefix += "/" + name
        marker = requested_prefix[len(prefix) + 1:].split("/", 1)[0]
        if node.type == "map":
            position = int(marker.removeprefix("item-"))
            items = resolve_value(node.items, ctx)
            inputs = {"item": items[position], "index": position, "context": arguments}
            if node.carry is not None:
                previous = resolve_value(node.carry, ctx)
                for i in range(position):
                    prior = {"item": items[i], "index": i, "context": arguments, "previous": previous}
                    previous = resolve_inputs(node.body.output, context(node.body, prior, prefix + f"/item-{i}"))
                inputs["previous"] = previous
        elif node.type == "loop":
            inputs = arguments
            for i in range(int(marker.removeprefix("iteration-"))):
                inputs = resolve_inputs(node.body.output, context(node.body, inputs, prefix + f"/iteration-{i}"))
        else:
            inputs = arguments
        prefix += "/" + marker
    return requested_prefix, prefixes, inputs


def graph_at(spec: AgentSpec, path: list[str]) -> Graph:
    graph, index = spec.graph, 0
    while index < len(path):
        node = graph.nodes[path[index]]
        field = path[index + 1]
        if field == "body" and node.body is not None:
            graph, index = node.body, index + 2
        elif field == "branches":
            graph, index = node.branches[path[index + 2]], index + 3
        else:
            raise ValueError("invalid subgraph path")
    return graph


@dataclass(frozen=True)
class DebugPlan:
    spec: AgentSpec
    boundary: list[dict]
    selected: list[str]
    path: list[str]

    def describe(self):
        return {"selected": self.selected, "path": self.path, "boundary": self.boundary,
                "input_schema": self.spec.input_schema}


def plan_debug(spec: AgentSpec, selected: list[str], path: list[str] | None = None) -> DebugPlan:
    path = path or []
    graph = graph_at(spec, path)
    if not selected or len(set(selected)) != len(selected) or set(selected) - graph.nodes.keys():
        raise ValueError("select distinct nodes from the current graph")
    selected_set, boundary = set(selected), {}
    upstream_required = set()
    project_fields, project_required = set(), set()
    whole_input = False
    dependencies = set()
    data = spec.model_dump(mode="json")
    nodes = {key: graph.nodes[key].model_dump(mode="json") for key in selected}

    def rewrite(value, target):
        nonlocal whole_input
        if not isinstance(value, dict) or "ref" not in value:
            return
        ref = value["ref"]
        if ref == "input" or ref.startswith("input."):
            if ref == "input":
                whole_input = True
            else:
                field = ref.split(".")[1]
                project_fields.add(field)
                if not value.get("optional", False):
                    project_required.add(field)
            value["ref"] = "input.project" + ref[5:]
        elif ref.startswith("nodes."):
            _, source, _, *tail = ref.split(".")
            if source in selected_set:
                dependencies.add((source, target))
            else:
                value["ref"] = ".".join(["input", "upstream", source, *tail])
                boundary[ref] = {"reference": ref, "source": source, "field": ".".join(tail),
                                 "optional": value.get("optional", False),
                                 "schema": graph.nodes[source].output_schema}
                if not value.get("optional", False):
                    upstream_required.add(source)

    for name, node in nodes.items():
        for value in node["inputs"].values():
            rewrite(value, name)
        for field in ("items", "carry", "mailbox"):
            rewrite(node.get(field), name)
        if node.get("condition"):
            rewrite(node["condition"]["left"], name)
            rewrite(node["condition"].get("right"), name)
        # Nested bodies and loop predicates have their own input/node scope.

    entry = "debug_start"
    while entry in nodes:
        entry += "_"
    nodes[entry] = {"type": "transform", "inputs": {}, "output_schema": {"type": "object"}}
    edges = [edge.model_dump(exclude_none=True) for edge in graph.edges
             if edge.source in selected_set and edge.target in selected_set]
    # Removing intermediate nodes can sever a selected node's data dependency.
    # Keep live selected outputs ordered, while omitted outputs stay boundary inputs.
    def reachable(source, target):
        pending, visited = [source], set()
        while pending:
            current = pending.pop()
            if current == target:
                return True
            if current not in visited:
                visited.add(current)
                pending.extend(edge["target"] for edge in edges if edge["source"] == current)
        return False

    for source, target in sorted(dependencies):
        if not reachable(source, target):
            edges.append({"source": source, "target": target})
    targets = {edge["target"] for edge in edges}
    edges.extend({"source": entry, "target": key} for key in selected if key not in targets)
    data["spec_version"] = "0.3"
    data["graph"] = {"entry": entry, "nodes": nodes, "edges": edges,
                     "output": {key: {"ref": f"nodes.{key}.output", "optional": True} for key in selected}}
    # A subflow receives a user-supplied local context (item/index/context for maps).
    project_schema = deepcopy(spec.input_schema) if not path else {"type": "object"}
    if not whole_input:
        # A selected render should not require an unrelated top-level briefing.
        properties = project_schema.get("properties", {})
        project_schema = {"type": "object", "properties": {
            key: deepcopy(properties.get(key, {})) for key in sorted(project_fields)
        }, "required": sorted(project_required), "additionalProperties": True}
    data["input_schema"] = {
        "type": "object", "required": ["project", "upstream"], "additionalProperties": False,
        "properties": {"project": project_schema, "upstream": {
            "type": "object", "required": sorted(upstream_required),
            "properties": {item["source"]: item["schema"] for item in boundary.values()},
            "additionalProperties": False,
        }},
    }
    data["output_schema"] = {"type": "object"}
    data["execution"]["max_steps"] = min(10000, data["execution"]["max_steps"] + 1)
    # Preflight should only require services used by the selected fragment.
    models, tools, resources = set(), set(), set()

    def collect(graph_nodes):
        for node in graph_nodes.values():
            if node.get("model"):
                models.add(node["model"])
            tools.update(node.get("tools", []))
            if node.get("tool"):
                tools.add(node["tool"])
            resources.update(node.get("skills", []))
            if isinstance(node.get("instructions"), dict):
                resources.add(node["instructions"]["resource"])
            if node.get("code"):
                resources.add(node["code"])
            if node.get("output_validator"):
                resources.add(node["output_validator"])
            if node.get("body"):
                collect(node["body"]["nodes"])
            for branch in node.get("branches", {}).values():
                collect(branch["nodes"])

    collect(nodes)
    for field, keep in (("models", models), ("tools", tools), ("resources", resources)):
        data[field] = {key: value for key, value in data[field].items() if key in keep}
    return DebugPlan(AgentSpec.model_validate(data), list(boundary.values()), selected[:], path[:])
