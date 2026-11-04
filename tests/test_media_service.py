import base64
import importlib.util
import io
import json
import subprocess
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


def test_optional_speech_inspection_preserves_transcript_timing_and_confidence(tmp_path):
    np = pytest.importorskip("numpy")
    backend = MediaBackend(tmp_path, "unused", None, "http://localhost:18880", speech_model=tmp_path / "speech")
    calls = []
    audio = np.zeros(48000, dtype=np.float32)
    def transcribe(waveform, **kwargs):
        assert waveform is audio
        calls.append(kwargs)
        return iter([SimpleNamespace(start=0.2, end=2.4, text=" 窗外是什么？ ", avg_logprob=-0.2, no_speech_prob=0.01)]), SimpleNamespace(language="zh", language_probability=0.98)
    backend.transcriber = SimpleNamespace(transcribe=transcribe)
    result = backend.transcribe(audio)
    assert result["text"] == "窗外是什么？"
    assert result["segments"][0]["end"] == 2.4
    assert result["language"] == "zh"
    assert calls[0]["condition_on_previous_text"] is False


@pytest.fixture
def service(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(SERVICE))
    app_module = load("app")
    store = JobStore(tmp_path / "jobs.sqlite")
    backend = MediaBackend(
        tmp_path / "outputs", "unused-image", "unused-video", "http://127.0.0.1:18880"
    )
    return store, backend, app_module.create_app(store, backend, start_worker=False)


async def test_preload_readiness_waits_for_weights_and_shutdown_closes_worker(tmp_path, monkeypatch):
    import asyncio
    import threading

    monkeypatch.syspath_prepend(str(SERVICE))
    started, release, closed = threading.Event(), threading.Event(), threading.Event()
    backend = MediaBackend(tmp_path / "assets", "unused", None, "http://localhost")
    def execute(operation, payload, name, canceled):
        assert operation == "warmup" and payload == {"family": "voice"}
        started.set()
        assert release.wait(5)
        backend.loaded = "voice"
        return {"loaded": "voice"}
    backend.execute = execute
    backend.close = closed.set
    app = load("app").create_app(JobStore(tmp_path / "jobs.sqlite"), backend, preload="voice")
    async with app.router.lifespan_context(app):
        try:
            assert await asyncio.to_thread(started.wait, 5)
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://localhost") as client:
                response = await client.get("/health")
                assert response.status_code == 503 and response.json()["status"] == "loading"
                release.set()
                for _ in range(50):
                    response = await client.get("/health")
                    if response.status_code == 200:
                        break
                    await asyncio.sleep(.02)
                assert response.json()["loaded"] == "voice"
        finally:
            release.set()
    assert closed.is_set()


async def test_cpu_media_jobs_complete_while_image_inference_is_busy(tmp_path, monkeypatch):
    import asyncio
    import threading

    monkeypatch.syspath_prepend(str(SERVICE))
    entered, release = threading.Event(), threading.Event()
    calls = []
    backend = MediaBackend(tmp_path / "assets", "unused", None, "http://localhost")
    def execute(operation, payload, name, canceled):
        calls.append(name)
        if operation == "generate-image":
            entered.set()
            assert release.wait(10)
        return {"id": name}
    backend.execute = execute
    store = JobStore(tmp_path / "jobs.sqlite")
    image_job = store.submit("generate-image", "image", {})
    compose_job = store.submit("compose", "compose", {})
    app = load("app").create_app(store, backend)
    async with app.router.lifespan_context(app):
        try:
            assert await asyncio.to_thread(entered.wait, 5)
            for _ in range(100):
                if store.get(compose_job)["status"] == "succeeded":
                    break
                await asyncio.sleep(.02)
            assert store.get(compose_job)["status"] == "succeeded"
            assert store.get(image_job)["status"] == "running"
            assert store.counts() == {"running": 1, "succeeded": 1}
        finally:
            release.set()
    assert calls.count(image_job) == calls.count(compose_job) == 1


async def test_idempotency_and_restart_do_not_render_twice(service):
    store, backend, app = service
    calls = []
    backend.execute = lambda operation, payload, job, canceled: calls.append(job) or {"id": job}
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app), base_url="http://test"
    ) as client:
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
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app), base_url="http://test"
    ) as client:
        asset = (await client.post("/upload", json={"image": encoded})).json()
        result = await client.post("/vision", json={"assets": [asset], "max_side": 512})
        assert result.status_code == 200
        raw = base64.b64decode(result.json()["images"][0].split(",", 1)[1])
        image = Image.open(io.BytesIO(raw))
        assert image.size == (512, 341)
        # Four characters, a location, the candidate frame and a prior end pose.
        cast_review = await client.post("/vision", json={"assets": [asset] * 7, "max_side": 128})
        assert cast_review.status_code == 200 and len(cast_review.json()["images"]) == 7
        assert (await client.post("/vision", json={"assets": [asset] * 9})).status_code == 422
        for uri in [
            "file:///etc/passwd",
            "http://other.invalid/x.png",
            backend.base_url + "/files/../../private.png",
        ]:
            assert (
                await client.post("/vision", json={"assets": [{"uri": uri}]})
            ).status_code == 422
        assert (await client.post("/generate-image", json={"prompt": "x"})).status_code == 422
        assert (
            await client.post(
                "/upload", json={"image": encoded}, headers={"Origin": "https://example.org"}
            )
        ).status_code == 403


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
        transformer = SimpleNamespace(
            register_forward_pre_hook=lambda callback: callbacks.append(callback)
            or SimpleNamespace(remove=lambda: removed.append(True))
        )

        # The pinned Hunyuan API selects its own output resolution from the image.
        def __call__(self, *, prompt, image, num_frames, num_inference_steps, generator):
            assert image.size == (848, 480) and num_frames == 121
            callbacks[-1](self.transformer, ())
            return SimpleNamespace(frames=[[SimpleNamespace(shape=(480, 832, 3))] * num_frames])

    monkeypatch.setitem(sys.modules, "torch", SimpleNamespace(Generator=Generator))
    monkeypatch.setitem(sys.modules, "diffusers", SimpleNamespace())
    monkeypatch.setitem(
        sys.modules,
        "diffusers.utils",
        SimpleNamespace(
            export_to_video=lambda frames, target, fps: Path(target).write_bytes(b"video")
        ),
    )
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


async def test_failed_media_job_can_be_explicitly_retried(service):
    store, backend, app = service
    identifier = store.submit("video", "retry", {"shot": "same-intent"})
    store.claim()
    store.recover()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app), base_url="http://test"
    ) as client:
        assert (await client.post("/jobs/" + identifier + "/retry")).status_code == 200
        row = store.claim()
        assert row["id"] == identifier and json.loads(row["payload"]) == {"shot": "same-intent"}
        store.finish(identifier, {"uri": "film.mp4"})
        assert (await client.post("/jobs/" + identifier + "/retry")).status_code == 409


def test_model_process_reuse_switch_and_cancel(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(SERVICE))
    from isolated import IsolatedMediaBackend

    worker = tmp_path / "worker.py"
    worker.write_text("""import json,os,sys,time
json.loads(sys.stdin.readline())
for line in sys.stdin:
    task=json.loads(line)
    if task['payload'].get('malformed'):
        print('broken response',flush=True)
        continue
    if task['payload'].get('slow'):time.sleep(20)
    print(json.dumps({'output':{'pid':os.getpid()}}),flush=True)
""")
    backend = IsolatedMediaBackend(tmp_path / "outputs", "image", "video", "http://127.0.0.1:18880")
    backend.worker_script = worker
    try:
        first = backend.execute("image", {}, "one", lambda: False)
        assert backend.execute("image", {}, "two", lambda: False) == first
        assert backend.execute("video", {}, "three", lambda: False) != first
        with pytest.raises(RuntimeError, match="invalid response"):
            backend.execute("video", {"malformed": True}, "invalid", lambda: False)
        assert backend.child is None
        import time

        deadline = time.monotonic() + 0.5
        with pytest.raises(RuntimeError, match="canceled"):
            backend.execute("video", {"slow": True}, "four", lambda: time.monotonic() > deadline)
        assert backend.child is None
        from concurrent.futures import ThreadPoolExecutor

        with ThreadPoolExecutor(1) as pool:
            pending = pool.submit(backend.execute, "image", {"slow": True}, "five", lambda: False)
            time.sleep(0.1)
            backend.shutdown()
            with pytest.raises(RuntimeError, match="canceled"):
                pending.result(timeout=5)
        assert backend.child is None
    finally:
        backend.close()


def test_video_inspection_decodes_final_frame_and_detects_silent_audio(service):
    pytest.importorskip("av")
    np = pytest.importorskip("numpy")
    import imageio_ffmpeg

    _, backend, _ = service
    decoded = []
    backend.speech_model = "configured"
    def transcribe(waveform, **kwargs):
        decoded.append(waveform)
        return iter([]), SimpleNamespace(language="en", language_probability=0.9)
    backend.transcriber = SimpleNamespace(transcribe=transcribe)
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    for index, sound in enumerate(("sine=frequency=440:sample_rate=48000:duration=2",
                                   "anullsrc=r=48000:cl=mono")):
        path = backend.root / (str(index) * 32 + ".mp4")
        subprocess.run([ffmpeg, "-y", "-v", "error", "-f", "lavfi", "-i", "color=red:s=64x48:r=24:d=2",
                        "-f", "lavfi", "-i", sound, "-vf", "drawbox=color=blue:t=fill:enable='gte(n,47)'",
                        "-t", "2", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(path)],
                       check=True, capture_output=True, timeout=30)
        result = backend.inspect_video(backend.asset(path), str(index + 2) * 32)
        assert result["duration_seconds"] == pytest.approx(2, abs=0.05)
        assert result["frame_count"] == 48 and result["has_audio"]
        with Image.open(backend.resolve(result["last_frame"])) as final:
            red, _, blue = final.getpixel((32, 24))
            assert blue > 200 and red < 30
        assert (result["audio"]["rms_dbfs"] > -55) == (index == 0)
        assert decoded[-1].dtype == np.float32 and decoded[-1].ndim == 1
        assert len(decoded[-1]) / 16000 == pytest.approx(2, abs=0.05)
        assert (result["audio"]["audible_fraction"] > 0.01) == (index == 0)


def test_composition_preserves_audio_across_the_cut(service):
    av = pytest.importorskip("av")
    np = pytest.importorskip("numpy")
    import imageio_ffmpeg

    _, backend, _ = service
    clips = []
    for index, frequency in enumerate((440, 880)):
        path = backend.root / (str(index) * 32 + ".mp4")
        subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-v", "error", "-f", "lavfi", "-i",
                        "color=red:s=64x48:r=24:d=2", "-f", "lavfi", "-i",
                        f"sine=frequency={frequency}:sample_rate=48000:duration=2",
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(path)],
                       check=True, capture_output=True, timeout=30)
        clips.append(backend.asset(path))
    film = backend.compose(clips, [], "", "f" * 32, preserve_audio=True)
    result = backend.inspect_video(film, "e" * 32)
    assert result["duration_seconds"] == pytest.approx(4, abs=0.1)
    with av.open(str(backend.resolve(film))) as container:
        samples = np.concatenate([frame.to_ndarray().reshape(-1) for frame in container.decode(audio=0)])
    for index, frequency in enumerate((440, 880)):
        section = samples[48000 * (2 * index) + 12000:48000 * (2 * index) + 36000]
        dominant = np.argmax(np.abs(np.fft.rfft(section))) * 48000 / len(section)
        assert dominant == pytest.approx(frequency, abs=5)


def test_voice_reference_uses_spoken_section_and_fits_multi_speaker_budget(service, monkeypatch):
    av = pytest.importorskip("av")
    np = pytest.importorskip("numpy")
    import imageio_ffmpeg

    _, backend, _ = service
    backend.speech_model = "configured"
    path = backend.root / ("7" * 32 + ".mp4")
    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-v", "error", "-f", "lavfi", "-i",
                    "color=blue:s=64x48:r=12:d=8", "-f", "lavfi", "-i",
                    "sine=frequency=440:sample_rate=32000:duration=3", "-af", "adelay=5000",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(path)],
                   check=True, capture_output=True, timeout=30)
    def speech(waveform):
        assert waveform.dtype == np.float32
        assert len(waveform) == pytest.approx(8 * 16000, abs=1600)
        return {"text": "Hello", "language": "en", "segments": [
            {"start": 5, "end": 7.8, "text": "Hello", "no_speech_prob": 0.01}]}
    monkeypatch.setattr(backend, "transcribe", speech)
    result = backend.inspect_video(backend.asset(path), "8" * 32)
    assert result["audio_excerpt"]["start_seconds"] == pytest.approx(4.85)
    assert result["audio_excerpt"]["duration_seconds"] <= 4
    with av.open(str(backend.resolve(result["audio_asset"]))) as track:
        assert 3 <= track.duration / av.time_base <= 4
        waveform = np.concatenate([frame.to_ndarray().reshape(-1) for frame in track.decode(audio=0)])
        assert np.abs(waveform).max() > 100
    assert result["speech"]["text"] == "Hello"


@pytest.mark.parametrize("silent_first", [False, True])
def test_composition_keeps_timing_with_mixed_size_fps_and_missing_sound(service, silent_first):
    av = pytest.importorskip("av")
    np = pytest.importorskip("numpy")
    import imageio_ffmpeg

    _, backend, _ = service
    clips = []
    for index, silent in enumerate([silent_first, not silent_first]):
        path = backend.root / (str(index) * 32 + ".mp4")
        command = [imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-v", "error", "-f", "lavfi", "-i",
                   "color=blue:s=80x64:r=12:d=1" if silent else "color=red:s=64x48:r=24:d=1"]
        if not silent:
            command += ["-f", "lavfi", "-i", "sine=frequency=440:sample_rate=32000:duration=1", "-c:a", "aac"]
        subprocess.run(command + ["-c:v", "libx264", "-pix_fmt", "yuv420p", str(path)],
                       check=True, capture_output=True, timeout=30)
        clips.append(backend.asset(path))
    film = backend.compose(clips, [], "", "d" * 32, preserve_audio=True)
    with av.open(str(backend.resolve(film))) as container:
        frames = list(container.decode(video=0))
        assert len(frames) == 48
        assert len({(frame.width, frame.height) for frame in frames}) == 1
        rgb = frames[36 if silent_first else 12].to_image().getpixel((32, 24))
        assert rgb[0] > 200 and rgb[2] < 30
    with av.open(str(backend.resolve(film))) as container:
        resampler = av.AudioResampler(format="fltp", layout="mono", rate=48000)
        samples = np.concatenate([chunk.to_ndarray().reshape(-1) for frame in container.decode(audio=0)
                                  for chunk in resampler.resample(frame)])
    for index, silent in enumerate([silent_first, not silent_first]):
        section = samples[48000 * index + 12000:48000 * index + 36000]
        assert (float(np.abs(section).max()) < 0.001) == silent
    assert not list(backend.root.glob("*_segment_*.mp4"))


def test_image_warmup_materializes_both_text_and_reference_paths_without_publishing(tmp_path, monkeypatch):
    calls = []
    generator = SimpleNamespace(manual_seed=lambda seed: ('warmup', seed))
    monkeypatch.setitem(sys.modules, 'torch', SimpleNamespace(Generator=lambda **kw: generator))
    backend = MediaBackend(tmp_path, 'image', None, 'http://localhost', image_backend='qwen-image-2.1')
    monkeypatch.setattr(backend, 'load', lambda family: lambda **kw: calls.append(kw))
    assert backend.execute('warmup', {'family': 'image', 'probe': True}, 'unused', lambda: False) == {'loaded': 'image'}
    assert len(calls) == 1 and calls[0]['num_inference_steps'] == 1
    assert calls[0]['image'][0].size == (256, 256)
    assert calls[0]['generator'] == ('warmup', 0)
    assert list(tmp_path.iterdir()) == []


async def test_image_warmup_job_is_idempotent_and_rejects_invalid_families(service):
    store, backend, app = service
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url='http://test') as client:
        headers = {'Idempotency-Key': 'warm-image'}
        request = {'family': 'image', 'probe': True}
        first = await client.post('/warmup', headers=headers, json=request)
        assert first.status_code == 200
        again = await client.post('/warmup', headers=headers, json=request)
        assert first.json() == again.json()
        assert store.get(first.json()['job_id'])['operation'] == 'warmup'
        invalid = await client.post('/warmup', headers={'Idempotency-Key': 'invalid'}, json={'family':'voice','probe':True})
        assert invalid.status_code == 422
        invalid = await client.post('/warmup', headers={'Idempotency-Key': 'invalid-type'}, json={'family':{}})
        assert invalid.status_code == 422
