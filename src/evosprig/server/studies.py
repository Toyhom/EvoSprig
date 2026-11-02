"""Bounded background study workers; opaque searches are never replayed after crashes."""

from __future__ import annotations

import asyncio
import uuid

from evosprig.config import restore_models
from evosprig.core.journal import LeaseConflict, LeaseLost, Scope
from evosprig.evolution.study import StudyConfig, execute_study


class StudyWorker:
    def __init__(self, store, workspace, *, concurrency=1, model_factory=restore_models):
        self.store, self.workspace = store, workspace
        self.concurrency, self.model_factory = concurrency, model_factory
        self.tasks, self.cancellations = {}, {}
        self.shutdown = asyncio.Event()
        self.pump = None
        self.last_error = None

    async def start(self):
        self.shutdown.clear()
        self.pump = asyncio.create_task(self._pump())

    async def _pump(self):
        while not self.shutdown.is_set():
            try:
                for record in self.store.pending_studies():
                    self.dispatch(record)
                self.last_error = None
            except Exception as exc:
                self.last_error = type(exc).__name__
            try:
                await asyncio.wait_for(self.shutdown.wait(), 0.3)
            except TimeoutError:
                pass

    def dispatch(self, record):
        identifier = record["id"]
        if (
            identifier in self.tasks
            or len(self.tasks) >= self.concurrency
            or self.shutdown.is_set()
        ):
            return False
        task = asyncio.create_task(self._work(record))
        self.tasks[identifier] = task
        task.add_done_callback(lambda _: self.tasks.pop(identifier, None))
        return True

    async def _work(self, record):
        scope, identifier, owner = Scope(**record["scope"]), record["id"], uuid.uuid4().hex
        try:
            generation = self.store.claim_study(scope, identifier, owner)
        except LeaseConflict:
            return
        cancel = asyncio.Event()
        self.cancellations[identifier] = cancel

        def update(**changes):
            return self.store.update_study(scope, identifier, owner, generation, **changes)

        async def heartbeat():
            while True:
                await asyncio.sleep(1)
                state = update()
                if state["cancel_requested"] or self.shutdown.is_set():
                    cancel.set()

        heartbeat_task = asyncio.create_task(heartbeat())
        try:
            models = self.model_factory(record["bindings"]["models"])
            proposer = self.model_factory({"proposer": record["bindings"]["proposer"]})["proposer"]
            result = await execute_study(
                base=self.store.get(scope, record["base_version"]),
                suite=self.store.get_suite(scope, record["suite_id"]),
                config=StudyConfig.model_validate(record["config"]),
                models=models,
                proposer=proposer,
                workspace=self.workspace,
                store=self.store,
                scope=scope,
                job_id=identifier,
                tool_bindings=record["bindings"].get("tools", {}),
                on_event=lambda event: update(event=event),
                on_usage=lambda usage: update(usage=usage),
                cancel=cancel,
            )
            update(status=result["status"], result=result, usage=result["usage"])
        except LeaseLost:
            cancel.set()
        except Exception as exc:
            try:
                update(
                    status="failed",
                    error=type(exc).__name__
                    + ": study failed; inspect recorded events and configuration",
                )
            except LeaseLost:
                pass
        finally:
            cancel.set()
            heartbeat_task.cancel()
            await asyncio.gather(heartbeat_task, return_exceptions=True)
            self.cancellations.pop(identifier, None)

    async def stop(self):
        self.shutdown.set()
        for cancel in self.cancellations.values():
            cancel.set()
        if self.pump:
            await self.pump
            self.pump = None
        await asyncio.gather(*list(self.tasks.values()), return_exceptions=True)
