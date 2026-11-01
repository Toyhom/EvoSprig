"""The executable, JSON-only AgentSpec 0.1 DAG subset."""

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
    requires: list[Literal["text", "tool_calling", "structured_output"]] = Field(
        default_factory=lambda: ["text"]
    )


class ToolBinding(Contract):
    plugin: str
    version: str = "1"


class Node(Contract):
    type: Literal["model", "agent", "tool"]
    inputs: dict[str, Ref | Value] = Field(default_factory=dict)
    output_schema: dict[str, Any]
    model: str | None = None
    instructions: str | ResourceRef = ""
    tools: list[str] = Field(default_factory=list)
    tool: str | None = None
    response_format: Literal["text", "json"] = "text"

    @model_validator(mode="after")
    def valid_node(self):
        check_schema(self.output_schema)
        if self.type == "tool":
            if (
                not self.tool
                or self.model
                or self.tools
                or self.instructions
                or self.response_format != "text"
            ):
                raise ValueError("tool nodes require only tool, inputs and output_schema")
        elif not self.model or self.tool or (self.type == "model" and self.tools):
            raise ValueError("model/agent nodes require model; only agent nodes accept tools")
        return self


class Edge(Contract):
    source: str
    target: str


class Graph(Contract):
    entry: str
    nodes: dict[str, Node] = Field(min_length=1, max_length=128)
    edges: list[Edge] = Field(default_factory=list, max_length=1024)
    output: dict[str, Ref | Value]


class Execution(Contract):
    max_steps: int = Field(default=32, ge=1, le=1000)
    max_model_calls: int = Field(default=8, ge=0, le=100)
    max_total_tokens: int = Field(default=8192, ge=1, le=1000000)
    max_output_tokens: int = Field(default=512, ge=1, le=32768)
    timeout_seconds: float = Field(default=60.0, gt=0, le=3600)


class AgentSpec(Contract):
    spec_version: Literal["0.1"] = "0.1"
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
        order, ancestors = self.topology()
        for node_id in order:
            node = self.graph.nodes[node_id]
            if node.model and node.model not in self.models:
                raise ValueError(f"{node_id}: unknown model {node.model}")
            for tool in [node.tool] if node.tool else node.tools:
                if tool not in self.tools:
                    raise ValueError(f"{node_id}: unknown tool {tool}")
            if (
                isinstance(node.instructions, ResourceRef)
                and node.instructions.resource not in self.resources
            ):
                raise ValueError(f"{node_id}: unknown instruction resource")
            self._check_refs(node.inputs, ancestors[node_id], node_id)
        self._check_refs(self.graph.output, set(order), "graph.output")
        return self

    def _check_refs(self, values: dict, available: set[str], location: str):
        for value in values.values():
            if isinstance(value, Ref) and value.ref.startswith("nodes."):
                source = value.ref.split(".")[1]
                if source not in available:
                    raise ValueError(f"{location}: reference {value.ref} requires an upstream edge")

    def topology(self) -> tuple[list[str], dict[str, set[str]]]:
        graph = self.graph
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
            raise ValueError("M0 graphs must be acyclic and reachable from entry")
        return order, ancestors

    def canonical(self) -> str:
        data = self.model_dump(mode="json")
        data["graph"]["edges"].sort(key=lambda edge: (edge["source"], edge["target"]))
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
