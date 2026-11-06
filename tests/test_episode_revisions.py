import copy
import importlib.util
from pathlib import Path

p = Path(__file__).parents[1]/'apps/episode-studio/revisions.py'
spec = importlib.util.spec_from_file_location('revisions', p)
r = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)


def test_changed_reference_invalidates_only_used_shots_and_continuations():
    plan = {'characters': [{'id': 'a'}, {'id': 'b'}], 'locations': [{'id': 'room'}],
            'shots': [{'id': str(i), 'characters': [c], 'location': 'room', 'transition': t, 'dialogue': []}
                      for i, (c, t) in enumerate([('a','cut'), ('b','continue'), ('b','cut'), ('a','cut')])]}
    before = r.production_manifest(plan, references=[{'id':'a','asset':'old'}])
    after = r.production_manifest(plan, references=[{'id':'a','asset':'new'}])
    result = r.plan_retake(before, after)
    assert [s['shot_id'] for s in result['render']] == ['0', '1', '3']
    assert result['reuse'] == ['2']
    assert result['render'][1]['reasons'] == ['Continues from 0']
    assert r.plan_retake(before, before)['render'] == []
    changed = copy.deepcopy(plan)
    changed['shots'][2]['dialogue'] = [{'speaker': 'b', 'text': 'Come in.'}]
    assert [s['shot_id'] for s in r.plan_retake(before, r.production_manifest(changed, references=[{'id':'a','asset':'old'}]))['render']] == ['2']
