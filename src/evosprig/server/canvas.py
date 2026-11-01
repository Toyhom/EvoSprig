"""Canvas is an editable projection of AgentSpec; positions live separately."""

from evosprig.core.spec import AgentSpec


def to_canvas(spec: AgentSpec, layout: dict | None = None) -> dict:
    layout = layout or {}
    return {
        "nodes": [
            {
                "id": key,
                "position": layout.get(key, {"x": index * 280, "y": 120}),
                "data": {"label": key, "node": node.model_dump(mode="json")},
            }
            for index, (key, node) in enumerate(spec.graph.nodes.items())
        ],
        "edges": [
            {"id": f"{edge.source}--{edge.target}", "source": edge.source, "target": edge.target}
            for edge in spec.graph.edges
        ],
    }


def from_canvas(spec: AgentSpec, canvas: dict) -> tuple[AgentSpec, dict]:
    data = spec.model_dump(mode="json")
    nodes = canvas["nodes"]
    if len({node["id"] for node in nodes}) != len(nodes):
        raise ValueError("duplicate canvas node IDs")
    data["graph"]["nodes"] = {node["id"]: node["data"]["node"] for node in nodes}
    data["graph"]["edges"] = [
        {"source": edge["source"], "target": edge["target"]} for edge in canvas["edges"]
    ]
    return AgentSpec.model_validate(data), {node["id"]: node["position"] for node in nodes}
