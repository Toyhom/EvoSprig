from evosprig.core.protocols import ModelResponse, ToolRegistry
from evosprig.core.runtime import Runtime
from evosprig.core.version import compile_snapshot
from evosprig.plugins.mock import MockProvider
from evosprig.sdk import Builder


class NamedModel(MockProvider):
    def __init__(self, name):
        super().__init__()
        self.name = name

    async def complete(self, request):
        return ModelResponse(text=self.name)


async def test_default_model_is_shared_by_nested_nodes_and_overrides_stay_independent():
    b = Builder('shared-model', {'type': 'object'}, {'type': 'object'}, spec_version='0.3')
    b.default_model('writer').model('review', 'vision')
    b.node('draft', 'model', inputs={}, output_schema={'type': 'object'})
    b.map('items', items={'value': [1]}, output_schema={'type': 'object'}, body={
        'entry': 'write', 'nodes': {'write': {'type': 'model', 'inputs': {}, 'output_schema': {'type': 'object'}}},
        'edges': [], 'output': {'text': {'ref': 'nodes.write.output.text'}}})
    b.node('review', 'model', model='review', inputs={}, output_schema={'type': 'object'})
    b.edge('draft', 'items').edge('items', 'review')
    b.output(draft={'ref': 'nodes.draft.output.text'}, items={'ref': 'nodes.items.output.items'},
             review={'ref': 'nodes.review.output.text'})
    original = b.build_spec()
    b.default_model('new-writer')
    changed = b.build_spec()
    assert original.models['main'].binding == 'writer'
    assert changed.graph.nodes['items'].body.nodes['write'].model == 'main'
    assert changed.graph.nodes['review'].model == 'review'
    result = await Runtime({'new-writer': NamedModel('new'), 'vision': NamedModel('vision')},
                           ToolRegistry()).run(compile_snapshot(changed, {}), {})
    assert result.status == 'succeeded', result.error
    assert result.output == {'draft': 'new', 'items': [{'text': 'new'}], 'review': 'vision'}
