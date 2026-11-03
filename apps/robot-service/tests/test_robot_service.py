"""Physical placements, persisted action receipts and independent goal checks."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import Goal, Store  # noqa: E402


def test_place_restart_and_same_operation_does_not_move_twice(tmp_path):
    store = Store(tmp_path, "http://127.0.0.1:18890")
    started = store.transact("start", {"scene": "tabletop"}, "start")
    episode = started["episode"]
    assert store.observe(episode)["images"][0].startswith("data:image/jpeg;base64,")
    payload = {
        "episode": episode,
        "action": {"kind": "move", "object": "red", "position": [0.55, 0.25, 0.031]},
    }
    result = store.transact("act", payload, "move-red")
    assert result["success"], result
    fresh = Store(tmp_path, "http://127.0.0.1:18890")
    assert fresh.transact("act", payload, "move-red") == result
    assert fresh.check(
        episode, [Goal(object="red", kind="in_tray"), Goal(object="blue", kind="unchanged")]
    )["success"]
    with pytest.raises(ValueError, match="another intent"):
        fresh.transact(
            "act", {**payload, "action": {**payload["action"], "object": "blue"}}, "move-red"
        )
    before = fresh.state(episode)
    rejected = fresh.transact(
        "act",
        {**payload, "action": {"kind": "move", "object": "blue", "position": [99, 99, 99]}},
        "outside",
    )
    assert not rejected["success"]
    assert fresh.check(episode, [Goal(object="blue", kind="unchanged")])["success"]
    assert (
        before[0]["objects"]["blue"]["position"]
        == pytest.approx(fresh.state(episode)[0]["objects"]["blue"]["position"], abs=0.001)
    )


def test_completion_uses_physical_state_not_model_claim(tmp_path):
    store = Store(tmp_path, "http://127.0.0.1:18890")
    episode = store.transact("start", {"scene": "tabletop"}, "start")["episode"]
    store.transact(
        "act",
        {"episode": episode, "action": {"kind": "finish", "object": "red", "position": [0, 0, 0]}},
        "finish",
    )
    assert not store.check(episode, [Goal(object="red", kind="in_tray")])["success"]
