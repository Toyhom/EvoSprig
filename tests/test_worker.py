import asyncio

from evosprig.core.protocols import ModelResponse
from evosprig.core.runtime import Runtime
from evosprig.core.version import compile_agent
from evosprig.plugins.builtin_tools import builtin_registry
from evosprig.plugins.mock import MockProvider
from evosprig.plugins.sqlite_journal import SQLiteJournal
from evosprig.server.worker import Worker


async def test_graceful_worker_shutdown_leaves_resumable_checkpoint(spec, example_root, tmp_path):
    entered = asyncio.Event()
    resumed = False

    class SlowModel(MockProvider):
        async def complete(self, request):
            entered.set()
            if not resumed:
                await asyncio.sleep(10)
            return ModelResponse(text="resumed", model=self.model_id)

    model = SlowModel()
    store = SQLiteJournal(tmp_path / "runs.sqlite")
    runtime = Runtime({"main-model": model}, builtin_registry(), journal=store)
    runtime.create_run(compile_agent(spec, example_root), {"question": "hello"}, run_id="shutdown")
    first = Worker(store, lambda _: runtime)
    await first.start()
    await asyncio.wait_for(entered.wait(), 5)
    await asyncio.wait_for(first.stop(), 5)
    assert store.get("shutdown")["status"] == "queued"
    assert store.get("shutdown")["owner"] is None
    assert store.get("shutdown")["checkpoint"]["error"]["code"] == "worker_shutdown"
    resumed = True
    second = Worker(store, lambda _: runtime)
    await second.start()
    for _ in range(100):
        if store.get("shutdown")["status"] == "succeeded":
            break
        await asyncio.sleep(0.02)
    await second.stop()
    assert runtime.get("shutdown").output == {"answer": "resumed"}
    assert runtime.get("shutdown").usage["unreported_model_calls"] == 1


async def test_two_workers_claim_each_run_once(spec, example_root, tmp_path):
    class CountingModel(MockProvider):
        async def complete(self, request):
            self.requests.append(request)
            await asyncio.sleep(0.02)
            return ModelResponse(text="ok", model=self.model_id)

    model = CountingModel()
    store = SQLiteJournal(tmp_path / "runs.sqlite")
    runtime = Runtime({"main-model": model}, builtin_registry(), journal=store)
    for i in range(4):
        runtime.create_run(
            compile_agent(spec, example_root), {"question": "hello"}, run_id=f"queued-{i}"
        )
    first, second = Worker(store, lambda _: runtime, 2), Worker(store, lambda _: runtime, 2)
    await first.start()
    await second.start()
    for _ in range(150):
        if all(store.get(f"queued-{i}")["status"] == "succeeded" for i in range(4)):
            break
        await asyncio.sleep(0.02)
    await first.stop()
    await second.stop()
    assert len(model.requests) == 4
    assert all(store.get(f"queued-{i}")["status"] == "succeeded" for i in range(4))
