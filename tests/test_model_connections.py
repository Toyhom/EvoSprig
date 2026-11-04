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
