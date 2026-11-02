import pytest

from evosprig.plugins.sqlite_projects import ProjectStore
from evosprig.server.canvas_state import CanvasState


def test_nested_canvas_groups_persist_without_changing_behavior(spec, tmp_path):
    node = next(iter(spec.graph.nodes))
    canvas = (
        CanvasState.model_validate(
            {
                "groups": {
                    "graph": [
                        {"id": "group:inner", "label": "Research", "members": [node]},
                        {
                            "id": "group:outer",
                            "label": "Team",
                            "members": ["group:inner"],
                            "collapsed": True,
                        },
                    ]
                }
            }
        )
        .validate_for(spec)
        .model_dump()
    )
    store = ProjectStore(tmp_path / "projects.sqlite")
    before = store.create(spec, canvas=canvas)
    after = store.update(spec.id, spec, {}, 1)
    assert after["canvas"] == canvas
    assert after["spec_hash"] == before["spec_hash"] == spec.spec_hash
    assert store.update(spec.id, spec, {}, 2, canvas={})["canvas"] == {}


@pytest.mark.parametrize(
    "groups",
    [
        [
            {"id": "group:a", "label": "A", "members": ["group:b"]},
            {"id": "group:b", "label": "B", "members": ["group:a"]},
        ],
        [{"id": "group:a", "label": "A", "members": ["missing"]}],
        [{"id": "group:a", "label": "A", "members": ["group:a"]}],
    ],
)
def test_invalid_group_references_are_rejected(spec, groups):
    with pytest.raises(ValueError):
        CanvasState.model_validate({"groups": {"graph": groups}}).validate_for(spec)


def test_bad_graph_path_is_rejected(spec):
    with pytest.raises(ValueError):
        CanvasState(groups={"graph/missing/body": []}).validate_for(spec)


def test_studio_sidecar_checks_groups_and_finite_positions(spec, tmp_path):
    import json

    from evosprig.server.canvas_state import StudioView

    path = tmp_path / "studio.json"
    assert StudioView.read(path, spec).layout == {}
    node = next(iter(spec.graph.nodes))
    path.write_text(json.dumps({"layout": {node: {"x": 20, "y": 30}}, "canvas": {"groups": {}}}))
    assert StudioView.read(path, spec).layout[node].x == 20
    path.write_text(json.dumps({"layout": {node: {"x": float("inf"), "y": 30}}}))
    with pytest.raises(ValueError):
        StudioView.read(path, spec)
