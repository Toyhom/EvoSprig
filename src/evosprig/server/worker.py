"""Bounded local worker pool over the durable journal; API requests only enqueue work."""

import asyncio
import uuid

from evosprig.core.journal import LeaseConflict, LeaseLost


class Worker:
    def __init__(self, journal, runtime_factory, concurrency=4):
        if concurrency < 1 or concurrency > 64:
            raise ValueError("worker concurrency must be between 1 and 64")
        self.journal, self.runtime_factory = journal, runtime_factory
        self.concurrency = concurrency
        self.tasks = {}
        self.shutdown = asyncio.Event()
        self.pump = None
        self.last_error = None

    async def start(self):
        self.shutdown.clear()
        if self.pump is None:
            self.pump = asyncio.create_task(self._pump())

    def dispatch(self, run_id):
        if run_id in self.tasks or len(self.tasks) >= self.concurrency or self.shutdown.is_set():
            return False
        task = asyncio.create_task(self._work(run_id))
        self.tasks[run_id] = task
        task.add_done_callback(lambda _: self.tasks.pop(run_id, None))
        return True

    async def _pump(self):
        while not self.shutdown.is_set():
            try:
                for run_id in self.journal.due():
                    self.dispatch(run_id)
                self.last_error = None
            except Exception as exc:
                # Database outages must not silently kill the queue pump.
                self.last_error = type(exc).__name__
            try:
                await asyncio.wait_for(self.shutdown.wait(), 0.2)
            except TimeoutError:
                pass

    async def _work(self, run_id):
        try:
            runtime = self.runtime_factory(self.journal.get(run_id))
            await runtime.resume(run_id, shutdown=self.shutdown)
        except (LeaseConflict, LeaseLost):
            return
        except Exception as exc:
            # Only a fresh lease may turn an adapter/configuration failure into a final state.
            try:
                lease = self.journal.claim(run_id, "dispatch-" + uuid.uuid4().hex, 30)
            except (LeaseConflict, LeaseLost):
                return
            checkpoint = self.journal.get(run_id)["checkpoint"]
            checkpoint["error"] = {
                "code": "worker_configuration",
                "message": type(exc).__name__ + ": worker configuration failed",
            }
            self.journal.save(
                lease,
                checkpoint,
                "failed",
                [{"type": "run.failed", "data": {"error": checkpoint["error"]}}],
                release=True,
            )

    async def stop(self):
        self.shutdown.set()
        if self.pump:
            await self.pump
            self.pump = None
        await asyncio.gather(*list(self.tasks.values()), return_exceptions=True)
