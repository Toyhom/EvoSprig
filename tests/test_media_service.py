import base64
import importlib.util
import io
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from PIL import Image

SERVICE = Path(__file__).parents[1] / "apps" / "media-service"
# This optional service is executable independently of the framework package.
def load(name):
    spec = importlib.util.spec_from_file_location("media_test_" + name, SERVICE / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


JobStore = load("store").JobStore
MediaBackend = load("backend").MediaBackend


@pytest.fixture
def service(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(SERVICE))
    app_module = load("app")
    store = JobStore(tmp_path / "jobs.sqlite")
    backend = MediaBackend(tmp_path / "outputs", "unused-image", "unused-video", "http://127.0.0.1:18880")
    return store, backend, app_module.create_app(store, backend, start_worker=False)


async def test_idempotency_and_restart_do_not_render_twice(service):
    store, backend, app = service
    calls = []
    backend.execute = lambda operation, payload, job, canceled: calls.append(job) or {"id": job}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client:
        headers = {"Idempotency-Key": "first"}
        first = await client.post("/generate-image", json={"prompt": "A drone"}, headers=headers)
        job = first.json()["job_id"]
        again = await client.post("/generate-image", json={"prompt": "A drone"}, headers=headers)
        assert again.json()["job_id"] == job
        conflict = await client.post("/generate-image", json={"prompt": "A bird"}, headers=headers)
        assert conflict.status_code == 409
        assert store.run_once(backend)
        assert not store.run_once(backend)
        assert calls == [job]
        store.recover()
        result = (await client.get("/generate-image/" + job)).json()
        assert result == {"status": "succeeded", "output": {"id": job}}
        assert (await client.get("/video/" + job)).status_code == 404


def test_cancel_and_interrupted_job_are_not_replayed(service):
    store, backend, app = service
    job = store.submit("image", "cancel", {})
    store.claim()
    store.cancel(job)
    store.finish(job, {"id": "late-output"})
    assert store.get(job)["status"] == "canceled"
    second = store.submit("image", "interrupted", {})
    store.claim()
    JobStore(store.path).recover()
    assert store.get(second)["status"] == "failed"
    assert store.claim() is None


async def test_uploaded_images_can_be_used_for_vision_without_local_file_access(service):
    store, backend, app = service
    data = io.BytesIO()
    Image.new("RGB", (1200, 800), "red").save(data, format="PNG")
    encoded = "data:image/png;base64," + base64.b64encode(data.getvalue()).decode()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client:
        asset = (await client.post("/upload", json={"image": encoded})).json()
        result = await client.post("/vision", json={"assets": [asset], "max_side": 512})
        assert result.status_code == 200
        raw = base64.b64decode(result.json()["images"][0].split(",", 1)[1])
        image = Image.open(io.BytesIO(raw))
        assert image.size == (512, 341)
        for uri in ["file:///etc/passwd", "http://other.invalid/x.png", backend.base_url + "/files/../../private.png"]:
            assert (await client.post("/vision", json={"assets": [{"uri": uri}]})).status_code == 422
        assert (await client.post("/generate-image", json={"prompt":"x"})).status_code == 422
        assert (await client.post("/upload", json={"image": encoded}, headers={"Origin":"https://example.org"})).status_code == 403


def test_hunyuan_call_uses_its_supported_signature_and_cleans_up_cancellation(service, monkeypatch):
    _, backend, _ = service
    path = backend.root / ("a" * 32 + ".png")
    Image.new("RGB", (848, 480)).save(path)
    callbacks, removed = [], []
    class Generator:
        def __init__(self, device):
            assert device == "cpu"
        def manual_seed(self, seed):
            return self
    class Pipeline:
        transformer = SimpleNamespace(register_forward_pre_hook=lambda callback:
            callbacks.append(callback) or SimpleNamespace(remove=lambda: removed.append(True)))
        # The pinned Hunyuan API selects its own output resolution from the image.
        def __call__(self, *, prompt, image, num_frames, num_inference_steps, generator):
            assert image.size == (848, 480) and num_frames == 121
            callbacks[-1](self.transformer, ())
            return SimpleNamespace(frames=[[SimpleNamespace(shape=(480, 832, 3))] * num_frames])
    monkeypatch.setitem(sys.modules, "torch", SimpleNamespace(Generator=Generator))
    monkeypatch.setitem(sys.modules, "diffusers", SimpleNamespace())
    monkeypatch.setitem(sys.modules, "diffusers.utils", SimpleNamespace(
        export_to_video=lambda frames, target, fps: Path(target).write_bytes(b"video")))
    monkeypatch.setattr(backend, "load", lambda kind: Pipeline())
    name = "b" * 32
    result = backend.video("A person walks", backend.asset(path), 5, name, lambda: False)
    assert result["media_type"] == "video/mp4" and removed == [True]
    metadata = json.loads((backend.root / (name + ".json")).read_text())
    assert (metadata["width"], metadata["height"], metadata["frames"]) == (832, 480, 121)
    calls = iter([False, True])
    with pytest.raises(RuntimeError, match="canceled"):
        backend.video("A person walks", backend.asset(path), 5, "c" * 32, lambda: next(calls))
    assert removed == [True, True]
    assert not (backend.root / ("c" * 32 + ".mp4")).exists()
