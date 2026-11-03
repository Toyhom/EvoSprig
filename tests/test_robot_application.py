"""The robot application uses native visual nodes, loops and tool receipts."""

import json
from pathlib import Path

from evosprig.core.protocols import ModelResponse, Tool, ToolRegistry
from evosprig.core.runtime import Runtime
from evosprig.core.spec import load_spec
from evosprig.core.version import compile_agent
from evosprig.plugins.mock import MockProvider
from evosprig.plugins.sqlite_journal import SQLiteJournal


async def test_robot_observes_after_action_and_checks_world_independently(tmp_path):
    class Vision(MockProvider):
        capabilities = frozenset({"vision", "text", "structured_output"})

        async def complete(self, request):
            self.requests.append(request)
            parts = request.messages[1]["content"]
            assert any(p["type"] == "image_url" for p in parts)
            return ModelResponse(
                text=json.dumps(
                    {
                        "action": {
                            "kind": "move" if len(self.requests) == 1 else "finish",
                            "object": "red",
                            "position": [0.55, 0.25, 0.031],
                        },
                        "reasoning": "Use the latest camera frame",
                    }
                )
            )

    state = {"moved": False, "observed": []}
    image = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aV5kAAAAASUVORK5CYII="

    def observe(**kwargs):
        state["observed"].append(state["moved"])
        return {"images": [image], "objects": {}, "tray": {}}

    def act(action, **kwargs):
        state["moved"] = True
        return {"success": True}

    registry = ToolRegistry()
    for name, fn in [
        ("start", lambda **kw: {"episode": "scene"}),
        ("observe", observe),
        ("act", act),
        ("check", lambda **kw: {"success": False}),
    ]:
        registry.register(
            Tool(
                "robot." + name,
                name,
                {},
                {},
                fn,
                side_effect="write" if name in {"start", "act"} else "read_only",
                idempotent=name in {"start", "act"},
            )
        )
    root = Path(__file__).resolve().parents[1] / "examples/rai-manipulation"
    model = Vision()
    result = await Runtime(
        {"vision": model},
        registry,
        allow_writes=True,
        journal=SQLiteJournal(tmp_path / "runs.sqlite"),
    ).run(
        compile_agent(load_spec(root / "agent.yaml"), root),
        {"request": "Move red", "goals": [{"kind": "in_tray", "object": "red", "target": "blue"}]},
    )
    assert result.status == "succeeded", result.error
    assert state["observed"] == [False, True]
    assert result.output["result"]["success"] is False
