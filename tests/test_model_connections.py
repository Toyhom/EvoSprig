import httpx
import yaml

from evosprig.server.app import create_app
from evosprig.server.auth import Principal


async def test_model_connections_preserve_tools_link_services_and_keep_keys_in_environment(tmp_path, monkeypatch):
    profile = tmp_path / 'deployment.yaml'
    profile.write_text(yaml.safe_dump({'models': {}, 'tools': {'existing': {'kind': 'http'}},
                                      'services': {'vision-server': {'health_url': 'http://localhost:8000/health'}}}))
    monkeypatch.setenv('LOCAL_TEST_MODEL_KEY', 'private-test-value')
    app = create_app(tmp_path / 'workspace', profile=profile)
    payload = {'name': 'local-vision', 'connection': {'base_url': 'http://localhost:8000/v1',
        'model': 'vision-model', 'api_key_env': 'LOCAL_TEST_MODEL_KEY',
        'capabilities': ['text', 'structured_output', 'vision'], 'local_service': 'vision-server'}}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url='http://localhost') as client:
        response = await client.put('/api/models', json=payload)
        assert response.status_code == 200, response.text
        catalog = await client.get('/api/models')
        assert catalog.json()['models'][0]['local_service'] == 'vision-server'
        assert catalog.json()['models'][0]['key_configured']
        assert 'private-test-value' not in catalog.text
        saved = yaml.safe_load(profile.read_text())
        assert saved['tools'] == {'existing': {'kind': 'http'}}
        assert 'private-test-value' not in profile.read_text()
        payload['connection']['local_service'] = 'missing'
        assert (await client.put('/api/models', json=payload)).status_code == 422
        payload['connection']['local_service'] = 'vision-server'
        payload['connection']['base_url'] = 'https://provider.example/v1'
        assert (await client.put('/api/models', json=payload)).status_code == 422


async def test_shared_deployment_connections_are_operator_managed(tmp_path):
    profile = tmp_path / 'deployment.yaml'
    profile.write_text('models: {}\n')
    app = create_app(tmp_path / 'workspace', profile=profile,
                     principals={'test-token': Principal('viewer')})
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url='http://localhost',
                                 headers={'Authorization': 'Bearer test-token'}) as client:
        assert not (await client.get('/api/models')).json()['editable']
        response = await client.put('/api/models', json={'name': 'writer', 'connection': {
            'base_url': 'https://provider.example/v1', 'model': 'writer', 'api_key_env': 'MODEL_KEY'}})
        assert response.status_code == 403


async def test_service_placement_is_saved_and_respects_the_parent_allocation(tmp_path, monkeypatch):
    import socket

    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    profile = tmp_path / 'deployment.yaml'
    profile.write_text(yaml.safe_dump({'models': {}, 'services': {'writer': {
        'health_url': f'http://127.0.0.1:{port}/health', 'autostart': False}}}))
    monkeypatch.setenv('CUDA_VISIBLE_DEVICES', '3,7')
    app = create_app(tmp_path / 'workspace', profile=profile)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url='http://localhost') as client:
        assert (await client.put('/api/services/writer/placement', json={'gpu_devices': [1]})).status_code == 200
        assert yaml.safe_load(profile.read_text())['services']['writer']['gpu_devices'] == [1]
        assert (await client.put('/api/services/writer/placement', json={'gpu_devices': [2]})).status_code == 422
        assert (await client.put('/api/services/writer/placement', json={'gpu_devices': [-1]})).status_code == 422


async def test_no_key_connection_roundtrips_without_inventing_credentials(tmp_path):
    profile = tmp_path / 'deployment.yaml'
    profile.write_text('models: {}\n')
    app = create_app(tmp_path / 'workspace', profile=profile)
    payload = {'name': 'self-hosted', 'connection': {'base_url': 'http://inference.example:8000/v1',
        'model': 'my-model', 'api_key_env': None, 'allow_http': True}}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url='http://localhost') as client:
        assert (await client.put('/api/models', json=payload)).status_code == 200
        saved = (await client.get('/api/models')).json()['models'][0]
        assert saved['api_key_env'] is None
        assert saved['allow_http']
        assert not saved['key_configured']
        assert yaml.safe_load(profile.read_text())['models']['self-hosted']['api_key_env'] is None
