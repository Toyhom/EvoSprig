"""Developer-owned search spaces for immutable application candidates."""

from __future__ import annotations

import copy
from typing import Any, Literal

from pydantic import Field, model_validator

from evosprig.core.spec import AgentSpec, Contract, canonical_json
from evosprig.core.version import compile_snapshot


class Dimension(Contract):
    kind: Literal["choice", "integer", "number", "graph"] = "choice"
    choices: list[Any] = Field(default_factory=list, max_length=128)
    minimum: float | None = Field(default=None, allow_inf_nan=False)
    maximum: float | None = Field(default=None, allow_inf_nan=False)

    @model_validator(mode="after")
    def valid(self):
        if self.kind == "choice" and not self.choices:
            raise ValueError("a choice dimension needs values")
        if self.kind in {"integer", "number"} and (
            self.minimum is None or self.maximum is None or self.minimum > self.maximum
        ):
            raise ValueError("numeric dimensions need ordered finite bounds")
        canonical_json(self.model_dump())
        return self

    def check(self, value):
        if self.kind == "choice":
            if canonical_json(value) not in {canonical_json(v) for v in self.choices}:
                raise ValueError("candidate is outside the declared choices")
        elif self.kind in {"integer", "number"}:
            types = (int,) if self.kind == "integer" else (int, float)
            if type(value) not in types or not self.minimum <= value <= self.maximum:
                raise ValueError("candidate is outside the numeric bounds")
        elif not isinstance(value, dict):
            raise ValueError("graph candidate must be an object")


def parts(pointer):
    if not pointer.startswith("/") or "~" in pointer or "//" in pointer:
        raise ValueError("use an absolute JSON pointer with plain component names")
    return pointer[1:].split("/")


def read_pointer(data, pointer):
    for key in parts(pointer):
        data = data[int(key)] if isinstance(data, list) else data[key]
    return copy.deepcopy(data)


def write_pointer(data, pointer, value):
    keys = parts(pointer)
    for key in keys[:-1]:
        data = data[int(key)] if isinstance(data, list) else data[key]
    data[int(keys[-1]) if isinstance(data, list) else keys[-1]] = copy.deepcopy(value)


class SearchSpace(Contract):
    fields: dict[str, Dimension] = Field(default_factory=dict, max_length=64)
    # Each target belongs to one module. Resource targets use resource:<name>.
    modules: dict[str, list[str]] = Field(default_factory=dict, max_length=32)
    tool_grants: dict[str, list[str]] = Field(default_factory=dict, max_length=128)

    @model_validator(mode="after")
    def disjoint(self):
        paths = list(self.fields)
        for path, dimension in self.fields.items():
            parts(path)
            if not path.startswith("/graph/") and path != "/graph":
                raise ValueError("only graph behavior can be searched; deployment stays fixed")
            if dimension.kind == "graph" and path != "/graph":
                raise ValueError("a graph dimension targets /graph")
            if any(other != path and other.startswith(path + "/") for other in paths):
                raise ValueError("search dimensions cannot overlap")
        targets = [target for targets in self.modules.values() for target in targets]
        if len(targets) != len(set(targets)) or any(not v for v in self.modules.values()):
            raise ValueError("modules need nonempty disjoint target ownership")
        return self

    def seed(self, base, allowed):
        data = base.spec.model_dump(mode="json")
        fields = {path: read_pointer(data, path) for path in self.fields}
        # A seed may sit outside requested numeric choices; it remains the baseline.
        return {"resources": {n: base.resources[n] for n in allowed}, "fields": fields}

    def validate_base(self, base, allowed):
        self.seed(base, allowed)
        targets = {*self.fields, *("resource:" + n for n in allowed)}
        if any(t not in targets for ts in self.modules.values() for t in ts):
            raise ValueError("module targets must belong to this search space")
        if any(set(aliases) - set(base.spec.tools) for aliases in self.tool_grants.values()):
            raise ValueError("tool grants must use declared deployment bindings")

    def compile(self, base, allowed, candidate):
        if not isinstance(candidate, dict) or set(candidate) != {"resources", "fields"}:
            raise ValueError("candidate needs resources and fields")
        texts, fields = candidate["resources"], candidate["fields"]
        if not isinstance(texts, dict) or set(texts) != set(allowed):
            raise ValueError("candidate must preserve the editable resource set")
        if not isinstance(fields, dict) or set(fields) != set(self.fields):
            raise ValueError("candidate must preserve the declared field set")
        data = base.spec.model_dump(mode="json")
        for path, value in fields.items():
            if canonical_json(value) != canonical_json(read_pointer(data, path)):
                self.fields[path].check(value)
            write_pointer(data, path, value)
        spec = AgentSpec.model_validate(data)
        self.check_authority(base.spec, spec)
        return compile_snapshot(spec, {**base.resources, **texts})

    def check_authority(self, base, candidate):
        def nodes(graph, prefix=""):
            out = {}
            for name, node in graph.nodes.items():
                path = prefix + "/" + name
                out[path] = node
                if node.body:
                    out.update(nodes(node.body, path + "/body"))
                for branch, body in node.branches.items():
                    out.update(nodes(body, path + "/" + branch))
            return out

        previous = nodes(base.graph)
        for path, node in nodes(candidate.graph).items():
            old = previous.get(path)
            authority = set(old.tools + ([old.tool] if old.tool else [])) if old else set()
            authority.update(self.tool_grants.get(path, []))
            requested = set(node.tools + ([node.tool] if node.tool else []))
            if not requested <= authority:
                raise ValueError("candidate cannot add tool authority to a node")
            if node.mailbox != (old.mailbox if old else None):
                raise ValueError("candidate cannot change a node's messaging identity")
        # Schemas at the application boundary, bindings, budgets and permissions are
        # outside /graph and cannot be proposed by an optimizer.


def targets(candidate):
    if set(candidate) == {"resources", "fields"} and isinstance(candidate["resources"], dict):
        return {
            **{"resource:" + k: v for k, v in candidate["resources"].items()},
            **candidate["fields"],
        }
    return {"resource:" + k: v for k, v in candidate.items()}


def replace_targets(candidate, changes):
    updated = copy.deepcopy(candidate)
    structured = set(updated) == {"resources", "fields"} and isinstance(updated["resources"], dict)
    for target, value in changes.items():
        if target.startswith("resource:"):
            (updated["resources"] if structured else updated)[target[9:]] = copy.deepcopy(value)
        elif structured:
            updated["fields"][target] = copy.deepcopy(value)
        else:
            raise ValueError("structured changes need a search space")
    return updated
