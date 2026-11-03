"""Public runtime facade shared by SDK, CLI, Studio and exported applications."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

from .model_sessions import model_sessions
from .protocols import ToolRegistry


@dataclass
class RunResult:
    run_id: str
    agent_version: str
    status: str = "running"
    output: dict | None = None
    error: dict | None = None
    events: list[dict] = field(default_factory=list)
    usage: dict = field(default_factory=dict)
    duration_seconds: float = 0.0
    waiting: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


class Runtime:
    def __init__(
        self,
        models,
        tools: ToolRegistry | None = None,
        *,
        journal=None,
        allow_writes=False,
        lease_seconds=30.0,
    ):
        from .engine import Engine

        self.models = models
        self.tools = tools or ToolRegistry()
        self._engine = Engine(
            models, self.tools, journal, allow_writes=allow_writes, lease_seconds=lease_seconds
        )
        self.journal = self._engine.journal

    def create_run(self, version, inputs, *, run_id=None, scope=None, context=None):
        return self._engine.create_run(version, inputs, run_id=run_id, scope=scope, context=context)

    def create_event_run(self, version, inputs, trigger, *, scope=None):
        from .triggers import create_event_run

        return create_event_run(self, version, inputs, trigger, scope=scope)

    async def run(
        self, version, inputs, *, run_id=None, scope=None, cancel=None, on_event=None, shutdown=None
    ):
        async with model_sessions(self.models.values()):
            return await self._engine.run(
                version,
                inputs,
                run_id=run_id,
                scope=scope,
                cancel=cancel,
                on_event=on_event,
                shutdown=shutdown,
            )

    async def resume(self, run_id, *, scope=None, cancel=None, on_event=None, shutdown=None):
        async with model_sessions(self.models.values()):
            return await self._engine.resume(
                run_id, scope=scope, cancel=cancel, on_event=on_event, shutdown=shutdown
            )

    def get(self, run_id, scope=None):
        return self._engine.result(run_id, scope)

    async def cancel_run(self, run_id, *, scope=None):
        self.journal.cancel(run_id, scope)
        record = self.journal.get(run_id, scope)
        if record["owner"] is None:
            return await self.resume(run_id, scope=scope)
        return self.get(run_id, scope)
