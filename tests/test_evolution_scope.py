import json

import pytest
from test_evaluation import suite, version
from test_evolution_methods import TaskModel

from evosprig.core.journal import Scope
from evosprig.core.protocols import ModelResponse, Usage
from evosprig.core.spec import AgentSpec
from evosprig.core.version import compile_snapshot
from evosprig.evolution.study import StudyConfig, execute_study
from evosprig.plugins.mock import MockProvider
from evosprig.plugins.sqlite_studies import StudyStore


def shared():
    base = version()
    raw = base.spec.model_dump()
    raw['graph']['nodes']['other'] = raw['graph']['nodes']['answer'].copy()
    raw['graph']['edges'] = [{'source': 'answer', 'target': 'other'}]
    return compile_snapshot(AgentSpec.model_validate(raw), base.resources)


def config(**kwargs):
    return StudyConfig(method='opro', target={'node': '/graph/nodes/answer', 'modules': ['prompt']},
                       gate={'min_samples': 1}, **kwargs)


@pytest.mark.parametrize('inline', [False, True])
async def test_scoped_prompt_stops_at_goal_then_validates_and_exports(tmp_path, inline):
    base = shared()
    if inline:
        raw = base.spec.model_dump()
        raw['graph']['nodes']['answer']['instructions'] = 'Answer accurately.'
        base = compile_snapshot(AgentSpec.model_validate(raw), base.resources)
    cfg = config(rounds=20, goal={'score': 1})
    prepared, allowed, _, mapping = cfg.prepare(base)
    assert prepared.spec.graph.nodes['other'] == base.spec.graph.nodes['other']
    proposer = MockProvider([ModelResponse(text=json.dumps({allowed[0]: 'Return the exact label ok.'}),
                                          usage=Usage(20, 20))])
    data = suite()
    for split in ('search', 'selection', 'release', 'test'):
        for sample in getattr(data, split):
            sample.expected = 'ok'
    store, scope = StudyStore(tmp_path / 'db.sqlite'), Scope(base.spec.id)
    result = await execute_study(base=base, suite=data, config=cfg, models={'main': TaskModel()},
                                 proposer=proposer, workspace=tmp_path, store=store, scope=scope,
                                 job_id='scoped')
    assert len(proposer.requests) == 1
    assert result['method']['stop_reason'] == 'target_score'
    assert result['gate']['passed']
    assert set(result['reports']) == {'release', 'test'}
    selected = store.get(scope, result['selected_version'])
    assert selected.spec.graph.nodes['other'] == base.spec.graph.nodes['other']
    assert selected.resources['prompt'] == base.resources['prompt']
    assert selected.resources[allowed[0]] == 'Return the exact label ok.'
    assert selected.spec.graph.nodes['answer'].instructions.resource == allowed[0]
    assert result['base_version'] == base.version_id
    assert result['resource_mapping'] == mapping
    assert all(c['base_version'] == base.version_id for c in result['candidates'])
    assert store.release(scope)['version_id'] is None
    assert 'sealed-secret' not in str(proposer.requests)


async def test_goal_at_baseline_keeps_original_identity(tmp_path):
    base, data = shared(), suite()
    for split in ('search', 'selection', 'release', 'test'):
        for sample in getattr(data, split):
            sample.expected = 'long wrong response'
    proposer = MockProvider()
    result = await execute_study(base=base, suite=data, config=config(goal={'score': 1}),
                                 models={'main': TaskModel()}, proposer=proposer, workspace=tmp_path,
                                 store=StudyStore(tmp_path / 'db'), scope=Scope(base.spec.id), job_id='base')
    assert result['selected_version'] == base.version_id
    assert not proposer.requests and not result['candidates']


async def test_partial_selection_does_not_trigger_goal_or_patience(tmp_path):
    from evosprig.evaluation.budget import BudgetMeter, ExperimentBudget
    from evosprig.evaluation.runner import Evaluator
    from evosprig.evolution.context import EvolutionContext
    from evosprig.evolution.goal import EvolutionGoal, GoalReached

    data = suite()
    data.selection.append(data.selection[0].model_copy(update={'id': 'second', 'input': {'question': 'another'}}))
    for sample in data.selection:
        sample.expected = 'ok'
    meter = BudgetMeter(ExperimentBudget())
    ctx = EvolutionContext(base=version(), allowed=['prompt'], view=data.optimization_view(),
                           metric=data.metric, evaluator=Evaluator(tmp_path, {'main': TaskModel()}, meter),
                           meter=meter, proposer=MockProvider(), store=StudyStore(tmp_path/'db'),
                           scope=Scope('eval-agent'), job_id='partial', method='opro',
                           goal=EvolutionGoal(score=1, patience=1))
    candidate = {'prompt': 'Return the exact label ok.'}
    await ctx.evaluate(candidate, 'selection', ctx.view['selection'][:1])
    assert not ctx.goal_seen
    with pytest.raises(GoalReached, match='target_score'):
        await ctx.evaluate(candidate, 'selection')


async def test_patience_selects_best_full_candidate_and_still_validates(tmp_path):
    base = version()
    proposer = MockProvider([ModelResponse(text=json.dumps({'prompt': 'Give a longer answer.'}))])
    result = await execute_study(base=base, suite=suite(), config=config(rounds=10, goal={'patience': 1}),
                                 models={'main': TaskModel()}, proposer=proposer, workspace=tmp_path,
                                 store=StudyStore(tmp_path/'db'), scope=Scope(base.spec.id), job_id='patience')
    assert result['method']['stop_reason'] == 'no_improvement'
    assert result['selected_version'] == base.version_id
    assert len(proposer.requests) == 1
    assert set(result['reports']) == {'release', 'test'}


def test_target_rejects_other_nodes_resources_and_unbounded_modules():
    base = shared()
    with pytest.raises(ValueError, match='selected node'):
        config(allowed_resources=['unrelated']).prepare(base)
    for path in ['/graph/nodes/other/model', '/graph/nodes/answer/model', '/graph']:
        with pytest.raises(ValueError, match='inside the selected'):
            config(search_space={'fields': {path: {'kind': 'choice', 'choices': ['main']}}}).prepare(base)
    with pytest.raises(ValueError, match='no editable'):
        StudyConfig(method='opro', target={'node': '/graph/nodes/answer', 'modules': ['skill']}).prepare(base)


def test_nested_target_isolated_and_harness_bounds_confined():
    from evosprig.sdk import Builder

    child = Builder('child', {}, {}).model('main', 'main').resource('prompt', 'p.md').node(
        'answer', 'model', model='main', instructions={'resource': 'prompt'}, output_schema={}).output(
            answer={'ref': 'nodes.answer.output'}).build_spec().graph
    spec = Builder('nested', {}, {}, spec_version='0.3').model('main', 'main').resource('prompt', 'p.md').node(
        'group', 'parallel', branches={'one': child.model_dump(), 'two': child.model_dump()}, output_schema={}).output(
            answer={'ref': 'nodes.group.output'}).build_spec()
    base = compile_snapshot(spec, {'prompt': 'Original'})
    cfg = StudyConfig(method='opro', target={'node': '/graph/nodes/group/branches/one/nodes/answer'})
    prepared, allowed, _, _ = cfg.prepare(base)
    assert prepared.spec.graph.nodes['group'].branches['two'] == base.spec.graph.nodes['group'].branches['two']
    assert prepared.spec.graph.nodes['group'].branches['one'].nodes['answer'].instructions.resource == allowed[0]


def test_inline_prompt_does_not_reuse_an_unrelated_resource_with_same_name():
    base = version()
    raw = base.spec.model_dump()
    raw['graph']['nodes']['answer']['instructions'] = 'The inline instruction.'
    raw['resources']['inline_prompt'] = {'path': 'unused.md', 'role': 'prompt'}
    source = compile_snapshot(AgentSpec.model_validate(raw), {**base.resources, 'inline_prompt': 'Unrelated'})
    prepared, names, _, _ = config().prepare(source)
    assert names != ['inline_prompt']
    assert prepared.resources[names[0]] == 'The inline instruction.'
    assert prepared.resources['inline_prompt'] == 'Unrelated'


async def test_api_scoped_comparison_and_explicit_proposer(tmp_path, monkeypatch):
    import asyncio

    import httpx

    from evosprig.server import evolution_api
    from evosprig.server.app import create_app

    class Edit(MockProvider):
        def __init__(self):
            super().__init__()
            self.model_id = 'editor-model'

        async def complete(self, request):
            payload = json.loads(request.messages[-1]['content'])
            return ModelResponse(text=json.dumps({name: 'Return the exact label ok.'
                                                 for name in payload['editable_resources']}), usage=Usage(20, 20))

    app = create_app(tmp_path)
    monkeypatch.setattr(evolution_api, 'make_models', lambda *args: {'main': TaskModel(), 'editor': Edit()})
    app.state.study_worker.model_factory = lambda bindings: {
        key: Edit() if item['model'] == 'editor-model' else TaskModel() for key, item in bindings.items()}
    base, data = shared(), suite()
    for split in ('search', 'selection', 'release', 'test'):
        for sample in getattr(data, split):
            sample.expected = 'ok'
    async with app.router.lifespan_context(app), httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://localhost') as client:
        assert (await client.post('/api/projects', json={'spec': base.spec.model_dump(), 'resources': base.resources})).status_code == 201
        endpoint = '/api/projects/' + base.spec.id
        suite_id = (await client.post(endpoint+'/suites', json=data.model_dump())).json()['suite_id']
        body = {'suite_id': suite_id, 'revision': 1, 'mock': False, 'proposer_binding': 'editor',
                'config': config(goal={'score': 1}).model_dump()}
        rejected = {**body, 'config': {**body['config'], 'target': {'node': '/graph/nodes/missing'}}}
        assert (await client.post(endpoint+'/studies', json=rejected)).status_code == 422
        response = await client.post(endpoint+'/studies', json=body)
        assert response.status_code == 202, response.text
        study_id = response.json()['id']
        for _ in range(300):
            study = (await client.get(endpoint+'/studies/'+study_id)).json()
            if study['status'] not in {'queued', 'running'}:
                break
            await asyncio.sleep(.02)
        assert study['status'] == 'completed', study
        assert study['bindings']['proposer']['model'] == 'editor-model'
        compared = await client.get(endpoint+'/studies/'+study_id+'/comparison')
        assert compared.status_code == 200, compared.text
        changes = list(compared.json()['resource_changes'].values())
        assert len(changes) == 1
        assert changes[0]['before'] == base.resources['prompt']
        assert changes[0]['after'] == 'Return the exact label ok.'
        # The editable project remains unchanged until the user adopts a version.
        assert (await client.get(endpoint)).json()['resources'] == base.resources
