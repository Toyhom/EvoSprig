"""Plan shot revisions from changed production inputs without rendering new media."""
import hashlib
import json


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()


def production_manifest(plan, *, references=(), voices=(), style='', render_profile=None):
    shots = plan['shots']
    ids = [shot['id'] for shot in shots]
    if len(ids) != len(set(ids)):
        raise ValueError('shot IDs must be unique')
    cast = {item['id']: item for item in plan.get('characters', [])}
    locations = {item['id']: item for item in plan.get('locations', [])}
    refs = {item['id']: item for item in references}
    voice = {item['id']: item for item in voices}
    result = {}
    for index, shot in enumerate(shots):
        speakers = {line['speaker'] for line in shot.get('dialogue', [])}
        if shot.get('narration'):
            speakers.add('narrator')
        assets = set(shot.get('characters', [])) | {shot.get('location')}
        inputs = {'shot': shot, 'style': style, 'render_profile': render_profile,
                  'cast': {k: cast.get(k) for k in shot.get('characters', [])},
                  'location': locations.get(shot.get('location')),
                  'references': {k: refs.get(k) for k in sorted(assets - {None})},
                  'voices': {k: voice.get(k) for k in sorted(speakers)}}
        result[shot['id']] = {'fingerprint': fingerprint(inputs),
                             'components': {k: fingerprint(v) for k, v in inputs.items()},
                             'depends_on': [ids[index-1]] if index and shot.get('transition') == 'continue' else []}
    return {'format': 'evosprig.shots.v1', 'order': ids, 'shots': result}


def plan_retake(before, after, *, selected_shots=None):
    """Invalidate changed shots and their continuing successors; cut boundaries stop propagation."""
    if before.get('format') != 'evosprig.shots.v1' or after.get('format') != 'evosprig.shots.v1':
        raise ValueError('unsupported production manifest')
    selected = set(before['shots'] if selected_shots is None else selected_shots)
    affected, reuse = {}, []
    for identifier in after['order']:
        current = after['shots'][identifier]
        previous = before['shots'].get(identifier)
        reasons = []
        if not previous or identifier not in selected:
            reasons.append('No selected take')
        elif previous['fingerprint'] != current['fingerprint']:
            reasons.extend('Changed ' + key for key, value in current['components'].items() if previous['components'].get(key) != value)
        if previous and previous['depends_on'] != current['depends_on']:
            reasons.append('Changed preceding shot')
        reasons.extend('Continues from ' + parent for parent in current['depends_on'] if parent in affected)
        if reasons:
            affected[identifier] = reasons
        else:
            reuse.append(identifier)
    return {'render': [{'shot_id': k, 'reasons': v} for k, v in affected.items()], 'reuse': reuse,
            'removed': [k for k in before['order'] if k not in after['shots']]}
