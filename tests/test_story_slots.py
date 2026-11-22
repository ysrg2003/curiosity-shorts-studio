from copy import deepcopy
import io
import json
import re
import pytest
from curiosity import evidence, local_ai, story_slots as slots
from curiosity.storyboard import validate_story


def records():
    return [{'url': 'https://example.edu/a', 'text': 'This fictional source says synthetic test objects may move in a bounded imaginary experiment.'},
            {'url': 'https://example.org/b', 'text': 'Another fictional source describes a synthetic observation without making actual scientific claims about the world.'}]


def fixture(low=True):
    entries = evidence.catalog(records())
    ids = list(entries)
    raw = {'title': 'Synthetic unit test only', 'description': 'Not production content.',
           'tags': [f'fixture{i}' for i in range(8)], 'uncertainties': [], 'slots': {}}
    for i, (name, speaker, beat) in enumerate(slots.LAYOUT):
        count = (8 if low else 12) if speaker == 'PIP' else (20 if low else 24)
        item = {'text': ' '.join(['may'] + ['word'] * (count - 1)),
                'expression': 'curious', 'visual_title': 'Synthetic fixture'}
        if speaker == 'RAY':
            item['evidence'] = [{'quote_id': ids[(i // 2) % len(ids)]}]
        if beat == 'explain':
            item.update(visual_direction='Synthetic unit-test visual direction only. ' * 3,
                        diagram=['Synthetic start', 'Synthetic change'])
        raw['slots'][name] = item
    return raw, entries


@pytest.mark.parametrize('low,total', [(True, 176), (False, 228)])
def test_fixed_generic_slots_preserve_all_content_and_existing_gates(low, total):
    raw, entries = fixture(low)
    raw['slots'] = dict(reversed(list(raw['slots'].items())))
    saved = deepcopy(raw)
    obj = slots.materialize(raw, entries)
    assert raw == saved
    assert [x['speaker'] for x in obj['lines']] == ['PIP', 'RAY'] * 6 + ['PIP']
    assert sum(x['beat'] == 'explain' for x in obj['lines']) == 3
    for (name, speaker, beat), line in zip(slots.LAYOUT, obj['lines']):
        original = raw['slots'][name]
        assert line['text'] == original['text']
        assert line['evidence'] == original.get('evidence', [])
        assert line['diagram'] == original.get('diagram', [])
        assert line['visual_direction'] == original.get('visual_direction', '')
        assert (line['speaker'], line['beat'], line['visual_type']) == (speaker, beat, 'generated')
    bound = evidence.bind(obj, entries)
    assert validate_story(bound, records()) == {'words': total, 'explanation_beats': 3, 'source_records_used': 2}
    for old, new in zip(obj['lines'], bound['lines']):
        assert old['text'] == new['text']
        for selected, quote in zip(old['evidence'], new['evidence']):
            assert quote['quote'] == entries[selected['quote_id']]['quote']


@pytest.mark.parametrize('kind', ['missing', 'extra', 'speaker', 'beat', 'short', 'long', 'newline', 'unknown_id', 'short_visual', 'no_diagram'])
def test_bad_slots_are_rejected_without_padding_or_repair(kind):
    raw, entries = fixture()
    first = raw['slots']['pip_open']
    if kind == 'missing': del raw['slots']['pip_open']
    elif kind == 'extra': raw['slots']['extra_slot'] = deepcopy(first)
    elif kind in {'speaker', 'beat'}: first[kind] = 'RAY' if kind == 'speaker' else 'explain'
    elif kind in {'short', 'long'}: first['text'] = ' '.join(['word'] * (7 if kind == 'short' else 13))
    elif kind == 'newline': first['text'] += '\n'
    elif kind == 'unknown_id': raw['slots']['ray_setup']['evidence'] = [{'quote_id': 'not-in-catalog'}]
    elif kind == 'short_visual': raw['slots']['ray_explain_a']['visual_direction'] = 'too short'
    elif kind == 'no_diagram': raw['slots']['ray_explain_a']['diagram'] = []
    saved = deepcopy(raw)
    with pytest.raises(ValueError): slots.materialize(raw, entries)
    assert raw == saved


def test_word_pattern_accepts_contractions_and_rejects_punctuation_padding():
    assert re.fullmatch(slots.word_pattern('PIP'), "Wait, why can't these 2.5 balloons stay here?")
    assert not re.fullmatch(slots.word_pattern('PIP'), 'word word word word word word word ...')
    assert not re.fullmatch(slots.word_pattern('PIP'), 'word  word word word word word word word')
    assert not re.fullmatch(slots.word_pattern('PIP'), 'x' * 25 + ' word' * 7)


def test_materialized_layout_does_not_replace_two_source_or_length_checks():
    raw, entries = fixture()
    obj = evidence.bind(slots.materialize(raw, entries), entries)
    single = deepcopy(obj)
    for line in single['lines']:
        for item in line['evidence']:
            item.update(source_index=0, quote=records()[0]['text'])
    with pytest.raises(ValueError, match='at least 2'): validate_story(single, records())
    for amount in (154, 256):
        changed = deepcopy(obj)
        for line in changed['lines'][1:]:
            line['text'] = ' '.join(['word'] * 10)
        other = sum(len(x['text'].split()) for x in changed['lines'][1:])
        changed['lines'][0]['text'] = ' '.join(['word'] * (amount - other))
        with pytest.raises(ValueError, match='needs 155 to 255'): validate_story(changed, records())


def test_factual_rejection_still_stops_and_keeps_unreviewed_diagnostics(monkeypatch, tmp_path):
    from curiosity import planner, storyboard
    raw, _ = fixture()
    monkeypatch.setattr(storyboard, 'source_pack', lambda topic, sources: sources)
    calls = []
    def ask(model, system, prompt, schema, endpoint, seed, **kwargs):
        calls.append(schema)
        if 'slots' in schema['properties']:
            assert prompt['layout'] == slots.prompt_layout()
            return deepcopy(raw), {'synthetic': True}
        return {'supported': False, 'issues': ['Synthetic unsupported assertion']}, {'synthetic': True}
    monkeypatch.setattr(storyboard, 'ask', ask)
    target = tmp_path / 'test.json'
    with pytest.raises(ValueError, match='after 3 attempts'):
        planner.draft('Synthetic unit-test question?', target, source_records=records())
    assert not target.exists() and len(calls) == 6
    assert json.loads(target.with_suffix('.audit.json').read_text())['accepted'] is False
    for i in range(1, 4):
        diagnostic = json.loads(target.with_suffix(f'.attempt-{i}.json').read_text())
        assert diagnostic == {'diagnostic_only': True, 'not_a_verified_episode': True, 'model_output': raw}


@pytest.mark.parametrize('mode,accepted', [('valid', True), ('short', False), ('thinking', False), ('length', False)])
def test_real_endpoint_probe_checks_complete_output_not_just_request_success(monkeypatch, mode, accepted):
    monkeypatch.setattr(local_ai, 'read_metadata', lambda: ({'digest': local_ai.MANIFEST}, {}))
    obj = {'pip': ' '.join(['word'] * (7 if mode == 'short' else 8)), 'ray': ' '.join(['word'] * 20)}
    result = {'response': json.dumps(obj), 'thinking': 'not accepted' if mode == 'thinking' else '',
              'done': True, 'done_reason': 'length' if mode == 'length' else 'stop', 'eval_count': 80}
    def open_request(request, timeout):
        payload = json.loads(request.data)
        assert payload['think'] is False and payload['options']['num_predict'] == 1024
        assert 'exactly one word' in payload['prompt']
        assert set(payload['format']['properties']) == {'pip', 'ray'}
        assert payload['format']['additionalProperties'] is False
        return io.StringIO(json.dumps(result))
    monkeypatch.setattr(slots, 'urlopen', open_request)
    checked = slots.probe()
    assert checked['accepted'] is accepted
    assert checked['synthetic_response_sample'] == json.dumps(obj)
    assert checked['done_reason'] == result['done_reason']
