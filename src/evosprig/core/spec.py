"""Versioned JSON-only graphs, control nodes and portable value references."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Literal

import yaml
from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError
from pydantic import BaseModel, ConfigDict, Field, model_validator

IDENTIFIER = re.compile(r"^[a-zA-Z][a-zA-Z0-9_-]{0,63}$")
REFERENCE = re.compile(
    r"^(input(?:\.[A-Za-z0-9_-]+)*|nodes\.[A-Za-z][A-Za-z0-9_-]*\.output(?:\.[A-Za-z0-9_-]+)*)$"
)


def canonical_json(value: Any) -> str:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    )


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode()).hexdigest()


def check_schema(schema: dict) -> None:
    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError as exc:
        raise ValueError("invalid JSON Schema") from exc

    def inspect(value: Any) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                if key in ("$ref", "$dynamicRef") and not str(item).startswith("#"):
                    raise ValueError("JSON Schema references must be local fragments")
                inspect(item)
        elif isinstance(value, list):
            for item in value:
                inspect(item)

    inspect(schema)


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Ref(Contract):
    ref: str
    optional: bool = False
    default: Any = None

    @model_validator(mode="after")
    def valid_ref(self):
        if not REFERENCE.fullmatch(self.ref):
            raise ValueError(f"invalid reference: {self.ref}")
        return self


class Value(Contract):
    value: Any


class ResourceRef(Contract):
    resource: str


class Resource(Contract):
    path: str
    role: Literal["prompt", "skill"] = "prompt"


class ModelRequirement(Contract):
    binding: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")
    requires: list[Literal["text", "tool_calling", "structured_output", "vision"]] = Field(
        default_factory=lambda: ["text"]
    )


class ToolBinding(Contract):
    plugin: str
    version: str = "1"


class Predicate(Contract):
    left: Ref | Value
    op: Literal["eq", "ne", "lt", "le", "gt", "ge", "contains", "truthy"]
    right: Ref | Value | None = None

    @model_validator(mode="after")
    def valid_predicate(self):
        if self.op != "truthy" and self.right is None:
            raise ValueError("binary predicates require a right operand")
        if self.op == "truthy" and self.right is not None:
            raise ValueError("truthy takes one operand")
        return self


class Node(Contract):
    type: Literal[
        "model",
        "agent",
        "tool",
        "transform",
        "condition",
        "join",
        "loop",
        "parallel",
        "map",
        "human",
    ]
    inputs: dict[str, Ref | Value] = Field(default_factory=dict)
    output_schema: dict[str, Any]
    model: str | None = None
    instructions: str | ResourceRef = ""
    skills: list[str] = Field(default_factory=list, max_length=32)
    image_inputs: list[str] = Field(default_factory=list, max_length=16)
    temperature: float | None = Field(default=None, ge=0, le=2, allow_inf_nan=False)
    top_p: float | None = Field(default=None, gt=0, le=1, allow_inf_nan=False)
    tools: list[str] = Field(default_factory=list)
    tool: str | None = None
    response_format: Literal["text", "json"] = "text"
    condition: Predicate | None = None
    body: Graph | None = None
    branches: dict[str, Graph] = Field(default_factory=dict, max_length=16)
    max_iterations: int = Field(default=1, ge=1, le=100)
    until: Predicate | None = None
    join: Literal["all", "selected"] = "all"
    items: Ref | Value | None = None
    max_items: int = Field(default=32, ge=1, le=256)
    tool_errors: Literal["raise", "feedback"] = "raise"
    parallel_tool_calls: bool = False
    tool_selection: Literal["all", "relevant"] = "all"
    tool_limit: int = Field(default=8, ge=1, le=64)
    max_tool_rounds: int | None = Field(default=None, ge=1, le=256)
    output_errors: Literal["raise", "feedback"] = "raise"
    max_output_retries: int = Field(default=1, ge=0, le=3)
    max_output_tokens: int | None = Field(default=None, ge=1, le=32768)

    @model_validator(mode="after")
    def valid_node(self):
        check_schema(self.output_schema)
        if self.image_inputs and self.type not in {"model", "agent"}:
            raise ValueError("image inputs require a model or agent node")
        if len(set(self.image_inputs)) != len(self.image_inputs) or any(
            name not in self.inputs for name in self.image_inputs
        ):
            raise ValueError("image inputs must name distinct node input bindings")
        if self.type not in {"model", "agent"} and (
            self.skills or self.temperature is not None or self.top_p is not None
        ):
            raise ValueError("skills and sampling parameters require a model or agent node")
        if len(self.skills) != len(set(self.skills)):
            raise ValueError("node skills must be unique")
        if self.max_output_tokens is not None and self.type not in {"model", "agent"}:
            raise ValueError("per-node output tokens require a model or agent node")
        if len(self.tools) != len(set(self.tools)):
            raise ValueError("agent tool aliases must be unique")
        if self.type == "tool":
            if (
                not self.tool
                or self.model
                or self.tools
                or self.instructions
                or self.response_format != "text"
            ):
                raise ValueError("tool nodes require only tool, inputs and output_schema")
        elif self.type in {"model", "agent"}:
            if not self.model or self.tool or (self.type == "model" and self.tools):
                raise ValueError("model/agent nodes require model; only agent nodes accept tools")
        elif (
            self.model
            or self.tool
            or self.tools
            or self.instructions
            or self.response_format != "text"
        ):
            raise ValueError("control nodes use typed inputs and control configuration")
        if (self.type == "condition") != (self.condition is not None):
            raise ValueError(
                "condition nodes require a predicate; other nodes cannot set condition"
            )
        if (self.type in {"loop", "map"}) != (self.body is not None):
            raise ValueError("loop and map nodes require a body graph")
        if (self.type == "map") != (self.items is not None):
            raise ValueError("map nodes require an items binding")
        if self.type != "map" and self.max_items != 32:
            raise ValueError("max_items belongs to map nodes")
        if self.type != "agent" and self.tool_errors != "raise":
            raise ValueError("tool feedback belongs to agent nodes")
        if self.type != "agent" and (
            self.parallel_tool_calls
            or self.tool_selection != "all"
            or self.tool_limit != 8
            or self.max_tool_rounds is not None
        ):
            raise ValueError("tool policies belong to agent nodes")
        if self.type not in {"agent", "model"} and (
            self.output_errors != "raise" or self.max_output_retries != 1
        ):
            raise ValueError("output feedback belongs to model and agent nodes")
        if self.type != "loop" and (self.until is not None or self.max_iterations != 1):
            raise ValueError("iteration settings belong to loop nodes")
        if (self.type == "parallel") != bool(self.branches):
            raise ValueError("parallel nodes require named branch graphs")
        if self.type not in {"join", "parallel"} and self.join != "all":
            raise ValueError("join strategy belongs to join/parallel nodes")
        if self.type == "parallel" and self.join != "all":
            raise ValueError("parallel branches use the all join strategy")
        return self


class Edge(Contract):
    source: str
    target: str
    when: bool | None = None


class Graph(Contract):
    entry: str
    nodes: dict[str, Node] = Field(min_length=1, max_length=128)
    edges: list[Edge] = Field(default_factory=list, max_length=1024)
    output: dict[str, Ref | Value]


class Execution(Contract):
    max_steps: int = Field(default=32, ge=1, le=1000)
    max_model_calls: int = Field(default=8, ge=0, le=1000)
    max_total_tokens: int = Field(default=8192, ge=1, le=1000000)
    max_output_tokens: int = Field(default=512, ge=1, le=32768)
    image_token_reserve: int = Field(default=4096, ge=256, le=65536)
    timeout_seconds: float = Field(default=60.0, gt=0, le=3600)
    max_parallel_nodes: int = Field(default=1, ge=1, le=32)
    max_parallel_tools: int = Field(default=1, ge=1, le=16)
    allow_side_effects: bool = False


class AgentSpec(Contract):
    spec_version: Literal["0.1", "0.2", "0.3"] = "0.1"
    id: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    models: dict[str, ModelRequirement] = Field(default_factory=dict)
    tools: dict[str, ToolBinding] = Field(default_factory=dict)
    resources: dict[str, Resource] = Field(default_factory=dict)
    graph: Graph
    execution: Execution = Field(default_factory=Execution)

    @model_validator(mode="after")
    def validate_graph(self):
        canonical_json(self.model_dump())
        check_schema(self.input_schema)
        check_schema(self.output_schema)
        for name in [self.id, *self.models, *self.tools, *self.resources, *self.graph.nodes]:
            if not IDENTIFIER.fullmatch(name):
                raise ValueError(f"invalid identifier: {name}")
        self._validate_subgraph(self.graph, "graph", 0)
        if self.spec_version == "0.1":
            if any(
                node.type not in {"model", "agent", "tool"} for node in self.graph.nodes.values()
            ):
                raise ValueError("control nodes require spec_version 0.2")
            if any(edge.when is not None for edge in self.graph.edges):
                raise ValueError("conditional edges require spec_version 0.2")
            if (
                self.execution.max_parallel_nodes != 1
                or self.execution.max_parallel_tools != 1
                or self.execution.allow_side_effects
            ):
                raise ValueError("concurrency and write permissions require spec_version 0.2")
            values = [
                value for node in self.graph.nodes.values() for value in node.inputs.values()
            ] + list(self.graph.output.values())
            if any(
                isinstance(value, Ref) and (value.optional or value.default is not None)
                for value in values
            ):
                raise ValueError("optional references require spec_version 0.2")
        return self

    def _validate_subgraph(self, graph: Graph, location: str, depth: int):
        if depth > 8:
            raise ValueError("subgraph nesting exceeds eight levels")
        order, ancestors = self.topology(graph)
        for name in graph.nodes:
            if not IDENTIFIER.fullmatch(name):
                raise ValueError(f"invalid node identifier in {location}")
        for edge in graph.edges:
            if edge.when is not None and graph.nodes[edge.source].type != "condition":
                raise ValueError("conditional edges must originate from a condition node")
        for node_id in order:
            node = graph.nodes[node_id]
            if self.spec_version != "0.3" and (
                node.parallel_tool_calls
                or node.tool_selection != "all"
                or node.tool_limit != 8
                or node.max_tool_rounds is not None
                or node.output_errors != "raise"
                or node.max_output_retries != 1
            ):
                raise ValueError("tool policies require spec_version 0.3")
            if self.spec_version != "0.3" and (node.type == "map" or node.tool_errors != "raise"):
                raise ValueError("map nodes and tool feedback require spec_version 0.3")
            if node.model and node.model not in self.models:
                raise ValueError(f"{node_id}: unknown model {node.model}")
            if node.image_inputs and "vision" not in self.models[node.model].requires:
                raise ValueError(f"{node_id}: image inputs require a vision-capable model")
            for tool in [node.tool] if node.tool else node.tools:
                if tool not in self.tools:
                    raise ValueError(f"{node_id}: unknown tool {tool}")
            if (
                isinstance(node.instructions, ResourceRef)
                and node.instructions.resource not in self.resources
            ):
                raise ValueError(f"{node_id}: unknown instruction resource")
            for skill in node.skills:
                if skill not in self.resources or self.resources[skill].role != "skill":
                    raise ValueError(f"{node_id}: skills must reference declared skill resources")
            self._check_refs(node.inputs, ancestors[node_id], node_id)
            if node.items:
                self._check_refs({"items": node.items}, ancestors[node_id], node_id)
            if node.condition:
                self._check_refs(
                    {"left": node.condition.left, "right": node.condition.right},
                    ancestors[node_id],
                    node_id,
                )
            if node.body:
                self._validate_subgraph(node.body, location + "." + node_id, depth + 1)
            if node.until:
                for operand in (node.until.left, node.until.right):
                    if isinstance(operand, Ref) and not operand.ref.startswith("input"):
                        raise ValueError(
                            "loop until predicates reference input: the latest loop output"
                        )
            for name, branch in node.branches.items():
                if not IDENTIFIER.fullmatch(name):
                    raise ValueError("invalid parallel branch identifier")
                self._validate_subgraph(branch, location + "." + node_id + "." + name, depth + 1)
        self._check_refs(graph.output, set(order), location + ".output")

    def _check_refs(self, values: dict, available: set[str], location: str):
        for value in values.values():
            if isinstance(value, Ref) and value.ref.startswith("nodes."):
                source = value.ref.split(".")[1]
                if source not in available:
                    raise ValueError(f"{location}: reference {value.ref} requires an upstream edge")

    def topology(self, graph: Graph | None = None) -> tuple[list[str], dict[str, set[str]]]:
        graph = graph or self.graph
        parents = {key: set() for key in graph.nodes}
        children = {key: set() for key in graph.nodes}
        for edge in graph.edges:
            if edge.source not in parents or edge.target not in parents:
                raise ValueError("edge references an unknown node")
            if edge.target in children[edge.source]:
                raise ValueError("duplicate edge")
            parents[edge.target].add(edge.source)
            children[edge.source].add(edge.target)
        roots = sorted(key for key, value in parents.items() if not value)
        if roots != [graph.entry]:
            raise ValueError("graph must have exactly one root matching entry")
        pending = {key: set(value) for key, value in parents.items()}
        ready, order, ancestors = roots[:], [], {}
        while ready:
            key = ready.pop(0)
            order.append(key)
            ancestors[key] = set(parents[key])
            for parent in parents[key]:
                ancestors[key].update(ancestors[parent])
            for child in sorted(children[key]):
                pending[child].remove(key)
                if not pending[child]:
                    ready.append(child)
        if len(order) != len(graph.nodes):
            raise ValueError(
                "graphs must be acyclic and reachable from entry; use a bounded loop node"
            )
        return order, ancestors

    def used_resources(self) -> set[str]:
        """Text resources consumed by nodes, including nested executable graphs."""
        names = set()

        def visit(graph):
            for node in graph.nodes.values():
                if isinstance(node.instructions, ResourceRef):
                    names.add(node.instructions.resource)
                names.update(node.skills)
                if node.body:
                    visit(node.body)
                for branch in node.branches.values():
                    visit(branch)

        visit(self.graph)
        return names

    def canonical(self) -> str:
        data = self.model_dump(mode="json")
        if data["execution"]["image_token_reserve"] == 4096:
            data["execution"].pop("image_token_reserve")

        def normalize(graph):
            graph["edges"].sort(key=lambda edge: (edge["source"], edge["target"]))
            for node in graph["nodes"].values():
                for key, default in (
                    ("parallel_tool_calls", False),
                    ("tool_selection", "all"),
                    ("tool_limit", 8),
                    ("max_tool_rounds", None),
                    ("output_errors", "raise"),
                    ("max_output_retries", 1),
                    ("max_output_tokens", None),
                    ("skills", []),
                    ("image_inputs", []),
                    ("temperature", None),
                    ("top_p", None),
                ):
                    if node[key] == default:
                        node.pop(key)
                if self.spec_version != "0.3":
                    for key in ("items", "max_items", "tool_errors"):
                        node.pop(key)
                if node["body"]:
                    normalize(node["body"])
                for branch in node["branches"].values():
                    normalize(branch)

        normalize(data["graph"])
        if self.spec_version == "0.1":
            for node in data["graph"]["nodes"].values():
                for key in ("condition", "body", "branches", "max_iterations", "until", "join"):
                    node.pop(key)
            for edge in data["graph"]["edges"]:
                edge.pop("when")
            for key in ("max_parallel_nodes", "max_parallel_tools", "allow_side_effects"):
                data["execution"].pop(key)
            for values in [node["inputs"] for node in data["graph"]["nodes"].values()] + [
                data["graph"]["output"]
            ]:
                for value in values.values():
                    if "ref" in value:
                        value.pop("optional")
                        value.pop("default")
        return canonical_json(data)

    @property
    def spec_hash(self) -> str:
        return hashlib.sha256(self.canonical().encode()).hexdigest()


def load_spec(path: str | Path) -> AgentSpec:
    path = Path(path)
    if path.stat().st_size > 2_000_000:
        raise ValueError("spec exceeds 2 MB")
    return AgentSpec.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))


def save_spec(spec: AgentSpec, path: str | Path) -> None:
    Path(path).write_text(
        yaml.safe_dump(json.loads(spec.canonical()), sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
