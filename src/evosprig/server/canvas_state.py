"""Presentation metadata: grouping never changes execution or behavior hashes."""

from typing import Literal

from pydantic import Field

from evosprig.core.spec import Contract


class CanvasGroup(Contract):
    id: str = Field(pattern=r"^group:[A-Za-z][A-Za-z0-9_-]{0,63}$")
    label: str = Field(min_length=1, max_length=80)
    members: list[str] = Field(min_length=1, max_length=128)
    collapsed: bool = False
    direction: Literal["RIGHT", "DOWN"] = "DOWN"


class CanvasState(Contract):
    groups: dict[str, list[CanvasGroup]] = Field(default_factory=dict, max_length=256)

    def validate_for(self, spec):
        for path, groups in self.groups.items():
            parts = path.split("/")
            if parts.pop(0) != "graph" or len(parts) > 48:
                raise ValueError("invalid canvas graph path")
            graph = spec.graph
            while parts:
                if len(parts) < 2:
                    raise ValueError("invalid canvas graph path")
                node, kind = parts.pop(0), parts.pop(0)
                if node not in graph.nodes:
                    raise ValueError("canvas graph does not exist")
                config = graph.nodes[node]
                if kind == "body":
                    graph = config.body
                elif kind == "branches" and parts:
                    graph = config.branches.get(parts.pop(0))
                else:
                    raise ValueError("invalid canvas graph path")
                if graph is None:
                    raise ValueError("canvas graph does not exist")
            entries = {group.id: group for group in groups}
            if len(entries) != len(groups) or len(groups) > 128:
                raise ValueError("canvas groups must have unique bounded IDs")
            parents = {}
            for group in groups:
                for member in group.members:
                    if member in parents or member not in graph.nodes and member not in entries:
                        raise ValueError(
                            "a canvas member must exist and belong to at most one group"
                        )
                    parents[member] = group.id
            for identifier in entries:
                seen = set()
                while identifier in parents:
                    if identifier in seen:
                        raise ValueError("canvas groups cannot contain cycles")
                    seen.add(identifier)
                    identifier = parents[identifier]
        return self


class CanvasPosition(Contract):
    x: float = Field(allow_inf_nan=False)
    y: float = Field(allow_inf_nan=False)


class StudioView(Contract):
    """Optional studio.json sidecar, independent from executable AgentSpec."""

    canvas: CanvasState = Field(default_factory=CanvasState)
    layout: dict[str, CanvasPosition] = Field(default_factory=dict, max_length=32768)

    @classmethod
    def read(cls, path, spec):
        if not path.exists():
            return cls()
        if path.stat().st_size > 2_000_000:
            raise ValueError("Studio view exceeds 2 MB")
        view = cls.model_validate_json(path.read_text())
        view.canvas.validate_for(spec)
        return view
