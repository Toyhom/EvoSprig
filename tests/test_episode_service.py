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
    assert partition({'director': 'api', 'media_gpu': 0, 'comfy_gpu': 1}, ['GPU-a', 'GPU-b']) == {
        'media': 'GPU-a', 'comfy': 'GPU-b'}


def test_failed_preload_stops_startup_instead_of_waiting_for_the_deadline():
    import io
    import urllib.error
    from types import SimpleNamespace

    ready = module('launch').service_ready
    def unavailable(status):
        def open(*args, **kwargs):
            raise urllib.error.HTTPError('http://localhost/health', 503, 'Unavailable', {},
                                         io.BytesIO(json.dumps({'status': status}).encode()))
        return SimpleNamespace(open=open)
    assert not ready(unavailable('loading'), 'http://localhost/health', 'media')
    with pytest.raises(RuntimeError, match='preload failed'):
        ready(unavailable('failed'), 'http://localhost/health', 'media')


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
        assert 'voice_catalog' in project['spec']['graph']['nodes']
        assert 'voice_library' not in project['spec']['graph']['nodes']
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


async def test_api_deployment_routes_text_and_vision_without_local_model_options(tmp_path, monkeypatch):
    import runpy

    from evosprig.core.protocols import ModelRequest
    from evosprig.plugins.openai_compatible import Connection, OpenAICompatibleProvider

    root = ROOT / 'examples/episode-studio'
    monkeypatch.syspath_prepend(str(root))
    profile = runpy.run_path(str(root / 'configure.py'))['profile']
    main = {'base_url': 'https://writer.example/v1', 'model': 'writer', 'api_key_env': 'WRITER_KEY',
            'capabilities': ['text', 'structured_output'], 'json_mode': 'off'}
    vision = {'base_url': 'https://vision.example/v1', 'model': 'vision', 'api_key_env': 'VISION_KEY',
              'capabilities': ['text', 'structured_output', 'vision']}
    recipe = json.loads((ROOT / 'apps/episode-studio/render-recipe.json').read_text())
    kwargs = dict(model_url='http://127.0.0.1:18882/v1', model_name='unused',
                  media_url='http://127.0.0.1:18880', comfy_url='http://127.0.0.1:18884')
    deployment = profile(recipe, **kwargs, model_connections={'main': main, 'vision': vision})
    with pytest.raises(ValueError, match='missing capabilities'):
        profile(recipe, **kwargs, model_connections={'main': main})
    requests = []
    def handle(request):
        payload = json.loads(request.content)
        requests.append((str(request.url), request.headers['authorization'], payload))
        return httpx.Response(200, json={'choices': [{'message': {'content': '{"ok":true}'}, 'finish_reason': 'stop'}],
                                        'usage': {'prompt_tokens': 10, 'completion_tokens': 4}})
    for name, key in [('main', 'writer-key'), ('vision', 'vision-key')]:
        connection = Connection.model_validate(deployment['models'][name])
        monkeypatch.setenv(connection.api_key_env, key)
        adapter = OpenAICompatibleProvider(connection, transport=httpx.MockTransport(handle))
        request = ModelRequest(messages=[{'role': 'user', 'content': [{'type': 'text', 'text': 'Review this frame.'},
                    {'type': 'image_url', 'image_url': {'url': 'data:image/png;base64,cGl4ZWw='}}]}] if name == 'vision' else
                    [{'role': 'user', 'content': 'Write a shot.'}], max_output_tokens=64, json_output=True)
        assert json.loads((await adapter.complete(request)).text)['ok']
    assert requests[0][0] == 'https://writer.example/v1/chat/completions'
    assert requests[1][1] == 'Bearer vision-key'
    assert requests[1][2]['messages'][0]['content'][1]['type'] == 'image_url'
    assert all('chat_template_kwargs' not in row[2] for row in requests)
    assert 'response_format' not in requests[0][2]


def test_api_download_skips_director_and_optional_voice_weights(tmp_path, monkeypatch):
    import sys
    from types import SimpleNamespace

    launcher = module('launch')
    manifest = {'models': {role: {'repo': role, 'revision': 'pinned'}
                          for role in ('director', 'voice', 'image', 'speech')}, 'render_weights': []}
    (tmp_path / 'models.json').write_text(json.dumps(manifest))
    monkeypatch.setattr(launcher, 'APP', tmp_path)
    downloaded = []
    monkeypatch.setitem(sys.modules, 'huggingface_hub', SimpleNamespace(
        snapshot_download=lambda **kw: downloaded.append(kw['repo_id']), hf_hub_download=lambda **kw: None))
    launcher.download(SimpleNamespace(mirror=None, state=tmp_path, model_dir=tmp_path / 'weights',
                                      director='api', with_voice=False))
    assert downloaded == ['image', 'speech']


def test_low_vram_recipe_preserves_source_and_remains_a_valid_comfy_tool():
    from evosprig.plugins.comfy_tools import ComfyRecipeConfig, comfy_recipe_tool

    original = json.loads((ROOT / 'apps/episode-studio/render-recipe.json').read_text())
    lower = module('launch').memory_recipe(original, 'low-vram')
    by_kind = {node['type']: node for node in lower['workflow']['nodes']}
    assert by_kind['CLIPLoader']['widgets_values'][2] == 'cpu'
    assert by_kind['MiniMaxChunkFeedForward']['widgets_values'] == [4, 2048]
    assert by_kind['ResolutionSelector']['widgets_values'][1] == 0.5
    assert next(n for n in original['workflow']['nodes'] if n['type'] == 'CLIPLoader')['widgets_values'][2] == 'default'
    assert comfy_recipe_tool(ComfyRecipeConfig.model_validate(lower)).side_effect == "read_only"


def test_episode_restart_keeps_canvas_model_connections(tmp_path, monkeypatch):
    import subprocess
    import sys

    import yaml

    saved = tmp_path / 'saved.yaml'
    connection = {'base_url': 'http://127.0.0.1:8000/v1', 'model': 'my-vision',
                  'api_key_env': 'LOCAL_MODEL_API_KEY', 'local_service': 'vision-server',
                  'capabilities': ['text', 'structured_output', 'vision']}
    services = {'vision-server': {'health_url': 'http://127.0.0.1:8000/health'}}
    saved.write_text(yaml.safe_dump({'models': {'main': connection, 'reviewer': connection},
                                    'services': services, 'tools': {}}))
    stale_config = tmp_path / 'old-api.json'
    stale_config.write_text(json.dumps({'main': {**connection, 'api_key_env': 'REPLACED_MODEL_KEY'}}))
    monkeypatch.delenv('REPLACED_MODEL_KEY', raising=False)
    # Both default roles were replaced in Studio; the old API key must not block restart.
    data = yaml.safe_load(saved.read_text())
    data['models']['vision'] = connection
    saved.write_text(yaml.safe_dump(data))
    output = tmp_path / 'deployment.yaml'
    subprocess.run([sys.executable, str(ROOT / 'examples/episode-studio/configure.py'),
                    '--recipe', str(ROOT / 'apps/episode-studio/render-recipe.json'),
                    '--model-config', str(stale_config), '--check-model-keys',
                    '--reuse-connections', str(saved), '--out', str(output)], check=True)
    result = yaml.safe_load(output.read_text())
    assert result['models']['main'] == connection
    assert result['models']['reviewer'] == connection
    assert result['services'] == services
    assert 'film.render' in result['tools'] and 'media.generate_image' in result['tools']


def test_streaming_decode_preserves_recipe_inputs_and_other_nodes():
    recipe = json.loads((ROOT/'apps/episode-studio/render-recipe.json').read_text())
    changed = module('launch').memory_recipe(recipe, 'balanced', 'streaming')
    originals = {node['id']: node for node in recipe['workflow']['nodes']}
    replaced = []
    for node in changed['workflow']['nodes']:
        before = originals[node['id']]
        if before['type'] == 'VAEDecode':
            assert node['type'] == 'EvoSprigH3StreamingDecode'
            assert node['inputs'] == before['inputs']
            assert node['outputs'] == before['outputs']
            replaced.append(node)
        else:
            assert node == before
    assert replaced
    assert changed['workflow']['links'] == recipe['workflow']['links']
    assert {k:v for k,v in changed.items() if k not in {'workflow','object_info'}} == {k:v for k,v in recipe.items() if k not in {'workflow','object_info'}}
    assert module('launch').memory_recipe(recipe, 'balanced') == recipe
