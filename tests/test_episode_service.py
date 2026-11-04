import importlib.util
import json
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).parents[1]


def module(name):
    spec = importlib.util.spec_from_file_location('episode_' + name, ROOT / 'apps/episode-studio' / (name + '.py'))
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


def test_service_gpu_partitions_follow_the_allocation():
    partition = module('launch').device_partition
    config = {'director_gpus': 4, 'media_gpu': 4, 'comfy_gpu': 5}
    assert partition(config, ['GPU-a', 'GPU-b', 'GPU-c', 'GPU-d', 'GPU-e', 'GPU-f']) == {
        'director': 'GPU-a,GPU-b,GPU-c,GPU-d', 'media': 'GPU-e', 'comfy': 'GPU-f'}
    with pytest.raises(ValueError, match='not enough'):
        partition(config, ['0', '1'])
    with pytest.raises(ValueError, match='disjoint'):
        partition({**config, 'media_gpu': 0}, ['0', '1', '2', '3', '4', '5'])


def test_shutdown_reaps_services_that_ignore_soft_stop():
    import signal
    import subprocess
    import sys

    child = subprocess.Popen([sys.executable, '-u', '-c',
        'import signal,time; signal.signal(signal.SIGTERM,signal.SIG_IGN); print("ready"); time.sleep(60)'],
        start_new_session=True, stdout=subprocess.PIPE, text=True)
    finished = subprocess.Popen([sys.executable, '-c', 'pass'], start_new_session=True)
    try:
        assert child.stdout.readline().strip() == 'ready'
        finished.wait(timeout=5)
        module('launch').stop_services([child, finished], timeout=0.05)
        assert child.returncode == -signal.SIGKILL
        assert finished.returncode == 0
    finally:
        if child.poll() is None:
            child.kill()
        child.wait(timeout=5)
        child.stdout.close()


async def test_episode_frontend_uses_the_native_project_and_protects_media(tmp_path):
    from evosprig.core.journal import Scope
    from evosprig.core.spec import load_spec
    from evosprig.core.version import compile_agent

    profile = tmp_path / 'profile.yaml'
    profile.write_text('models: {}\ntools: {}\n')
    assets = tmp_path / 'media'
    assets.mkdir()
    name = 'a' * 32 + '.mp4'
    (assets / name).write_bytes(b'video')
    app = module('app').application(tmp_path / 'workspace', profile, media_root=assets, token='test-local')
    spec = load_spec(ROOT / 'examples/episode-studio/agent.yaml')
    version = compile_agent(spec, ROOT / 'examples/episode-studio')
    app.state.journal.create('production', version, {'source_text': 'A robot grows a flower.'}, Scope('episode-studio'), {})
    app.state.journal.create('selected-stages', version,
        {'upstream': {'script_editor': {'title': 'The last seed'}}}, Scope('episode-studio'), {})
    app.state.journal.create('other-user', version, {}, Scope('episode-studio', user='another-user'), {})
    other = compile_agent(spec.model_copy(update={'id': 'elsewhere'}), ROOT / 'examples/episode-studio')
    app.state.journal.create('other-project', other, {}, Scope('elsewhere'), {})
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url='http://localhost') as client:
        page = await client.get('/episode/')
        assert page.status_code == 200 and 'Episode Studio' in page.text
        assert (await client.get('/api/projects/episode-studio')).status_code == 401
        assert (await client.get('/episode-media/' + name)).status_code == 401
        client.headers['Authorization'] = 'Bearer test-local'
        project = (await client.get('/api/projects/episode-studio')).json()
        assert project['spec']['input_schema']['required'] == ['source_text']
        assert 'voice_library' in project['spec']['graph']['nodes']
        assert (await client.get('/episode-media/' + name)).content == b'video'
        assert (await client.get('/episode-media/services.json')).status_code == 404
        assert (await client.get('/episode/app.js')).status_code == 200
        history = (await client.get('/api/projects/episode-studio/runs?summary=true')).json()
        assert {row['run_id']: row['title'] for row in history} == {
            'production': 'A robot grows a flower.', 'selected-stages': 'The last seed'}
        assert set(history[0]) == {'run_id', 'status', 'created_at', 'title'}
    pins = json.loads((ROOT / 'apps/episode-studio/models.json').read_text())
    assert all(len(value['revision']) == 40 for value in pins['models'].values())


def test_profile_cache_observes_edits_and_isolates_callers(tmp_path):
    from evosprig.config import read_profile

    path = tmp_path / "profile.yaml"
    path.write_text("models: {}\ntools:\n  render: {kind: http, version: '1'}\n")
    original = read_profile(path)
    original["tools"]["render"]["version"] = "mutated"
    assert read_profile(path)["tools"]["render"]["version"] == "1"
    path.write_text(path.read_text().replace("'1'", "'2'"))
    assert read_profile(path)["tools"]["render"]["version"] == "2"


def test_deployment_verifies_downloads_and_uses_its_cuda_libraries(tmp_path):
    import hashlib

    launcher = module("launch")
    weight = tmp_path / "weight"
    weight.write_bytes(b"checkpoint")
    expected = {"size": len(b"checkpoint"), "sha256": hashlib.sha256(b"checkpoint").hexdigest()}
    launcher.verify_weight(weight, expected)
    weight.write_bytes(b"Checkpoint")
    with pytest.raises(RuntimeError, match="checksum"):
        launcher.verify_weight(weight, expected)
    weight.write_bytes(b"partial")
    with pytest.raises(RuntimeError, match="incomplete"):
        launcher.verify_weight(weight, expected)
    site = tmp_path / "episode-director/lib/python3.12/site-packages"
    toolkit = site / "nvidia/cu13"
    (toolkit / "bin").mkdir(parents=True)
    (toolkit / "bin/nvcc").touch()
    (site / "nvidia/cudnn/lib").mkdir(parents=True)
    env = launcher.service_environment({"env_root": str(tmp_path)}, "director", tmp_path)
    assert env["CUDA_HOME"] == str(toolkit)
    assert env["PATH"].split(":")[0] == str(toolkit / "bin")
    assert str(site / "nvidia/cudnn/lib") in env["LD_LIBRARY_PATH"].split(":")


async def test_bundled_recipe_preserves_render_controls_and_all_reference_types():
    from evosprig.plugins.comfy_tools import ComfyRecipeConfig, comfy_recipe_tool

    config = ComfyRecipeConfig.model_validate_json((ROOT / "apps/episode-studio/render-recipe.json").read_text())
    tool = comfy_recipe_tool(config)
    base = await tool.invoke({"reference_images": ["character.png"]})
    action = await tool.invoke({"controls": {"action": True, "steps": 14, "duration": 12},
                               "reference_images": [f"frame-{i}.png" for i in range(6)],
                               "reference_audio": [f"voice-{i}.wav" for i in range(3)],
                               "reference_videos": ["previous-shot.mp4"]})
    classes = {node["class_type"] for node in action["prompt"].values()}
    assert {"MiniMaxChunkFeedForward", "BlockSparseAttention", "SelfLiftH3Sampler", "ModelAttentionBackend"} <= classes
    assert sum(n["class_type"] == "LoraLoaderModelOnly" for n in action["prompt"].values()) > sum(n["class_type"] == "LoraLoaderModelOnly" for n in base["prompt"].values())
    assert sum(n["class_type"] == "LoadAudio" for n in action["prompt"].values()) == 3
    assert sum(n["class_type"] == "LoadImage" for n in action["prompt"].values()) == 6
    assert any(n["class_type"] == "VHS_LoadVideo" for n in action["prompt"].values())
    assert next(n for n in action["prompt"].values() if n["class_type"] == "BasicScheduler")["inputs"]["steps"] == 14
