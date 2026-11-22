"""Synthetic enforcement tests. No real topic, sources, model or media execution."""
from copy import deepcopy
import json
import pytest
from curiosity import autonomy, batch, evidence, planner, spec, storyboard, story_slots
from test_story_slots import fixture, records


@pytest.fixture(autouse=True)
def synthetic_entailment_scores(monkeypatch):
    from curiosity import entailment
    def scores(pairs):
        return {'accepted': True, 'pairs': [{'accepted': True, 'entailment_score': 1.0} for _ in pairs], 'synthetic': True}
    monkeypatch.setattr(entailment, 'score_pairs', scores)


@pytest.mark.parametrize('decision,accepted', [('missing', False), (False, False), ('true', False), (True, True)])
def test_topic_acceptance_must_be_explicit_literal_true(monkeypatch, decision, accepted):
    def ask(*args, **kwargs):
        if 'complete_answer' in args[3]['properties']:return {'complete_answer':True,'qualifiers_preserved':True,'no_exclusive_or_universal_overclaim':True,'issues':[]},{}
        result = {'answer': 'Synthetic fixture observations remain fictional in this bounded unit test.',
                  'answer_quote_ids': ['S0Q0', 'S1Q0'],
                  'supported': True, 'source_assessments': [
            {'source_index': i, 'usable': True, 'reason': 'current_observation_or_mechanism'} for i in range(2)],
            'observable_quote_ids': ['S0Q0'], 'mechanism_quote_ids': ['S1Q0'], 'issues': []}
        if decision != 'missing':
            result['topic_assessment'] = {'suitable': decision, 'reason': 'fits_short_visual_science'}
        return result, {}
    monkeypatch.setattr(storyboard, 'ask', ask)
    ok, report = evidence.screen('Synthetic fixture question?', records(), 'synthetic')
    assert ok is accepted and report['topic_suitability_accepted'] is accepted
    if not accepted: assert report['approved_source_indices'] == []


@pytest.mark.parametrize('broken', ['layout', 'bounds', 'source_catalog'])
def test_inconsistent_specification_is_rejected_before_a_draft_call(monkeypatch, tmp_path, broken):
    _, entries = fixture()
    if broken == 'layout': monkeypatch.setattr(story_slots, 'LAYOUT', story_slots.LAYOUT[:-1])
    elif broken == 'bounds': monkeypatch.setattr(story_slots, 'WORD_BOUNDS', {'PIP': (40, 44), 'RAY': (40, 44)})
    else: entries = {next(iter(entries)): next(iter(entries.values()))}
    monkeypatch.setattr(evidence, 'catalog', lambda sources: entries)
    monkeypatch.setattr(storyboard, 'source_pack', lambda topic, sources: sources)
    def forbidden(*args, **kwargs): raise AssertionError('Draft inference started before specification validation')
    monkeypatch.setattr(storyboard, 'ask', forbidden)
    target = tmp_path / 'test.json'
    with pytest.raises(ValueError): planner.draft('Synthetic fixture question?', target, source_records=records())
    assert not target.exists()


def test_failed_topic_gate_never_starts_script_audio_or_video(monkeypatch, tmp_path):
    (tmp_path / 'studio.json').write_text(json.dumps({'video_count': 1, 'max_videos_per_run': 20, 'draft_model': 'synthetic'}))
    monkeypatch.setattr(batch, 'ROOT', tmp_path)
    monkeypatch.setenv('MODE', 'automatic')
    monkeypatch.setenv('VIDEO_COUNT', '1')
    monkeypatch.setenv('CURIOSITY_LLM_BACKEND', 'ollama')
    candidates = [{'question': f'Why does synthetic fixture {i} move?', 'search_terms': 'synthetic test'} for i in range(3)]
    monkeypatch.setattr(autonomy, 'questions', lambda *a, **k: (candidates, {}))
    monkeypatch.setattr(autonomy, 'research', lambda *a, **k: (records(), {}))
    def assess(*args, **kwargs):
        return {'topic_assessment': {'suitable': False, 'reason': 'Synthetic unsuitable-topic fixture'},
                'source_assessments': [{'source_index': i, 'usable': True, 'reason': 'current_observation_or_mechanism'} for i in range(2)],
                'supported': True, 'observable_quote_ids': ['S0Q0'], 'mechanism_quote_ids': ['S1Q0'], 'issues': []}, {}
    monkeypatch.setattr(storyboard, 'ask', assess)
    def forbidden(*args, **kwargs): raise AssertionError('A downstream stage started despite failed upstream acceptance')
    monkeypatch.setattr(planner, 'draft', forbidden)
    monkeypatch.setattr(batch.subprocess, 'run', forbidden)
    with pytest.raises(autonomy.ResearchUnavailable): batch.generate()
    audit = json.loads((tmp_path / 'drafts/episode-1.selection.json').read_text())
    assert len(audit['rejections']) == 3 and not (tmp_path / 'output').exists()
    assert all(not item['details']['research']['relevance']['topic_suitability_accepted'] for item in audit['rejections'])


def patch_valid_draft(monkeypatch):
    raw, _ = fixture()
    monkeypatch.setattr(storyboard, 'source_pack', lambda topic, sources: sources)
    def ask(model, system, prompt, schema, *args, **kwargs):
        if 'slots' in schema['properties']: return deepcopy(raw), {'synthetic': True}
        return {'supported': True, 'story_compliant': True, 'issues': []}, {'synthetic': True}
    monkeypatch.setattr(storyboard, 'ask', ask)
    return raw


@pytest.mark.parametrize('decision', ['missing', False, 'true'])
def test_word_compliance_without_explicit_story_acceptance_cannot_pass(monkeypatch, tmp_path, decision):
    raw, _ = fixture()
    monkeypatch.setattr(storyboard, 'source_pack', lambda topic, sources: sources)
    def ask(model, system, prompt, schema, *args, **kwargs):
        if 'slots' in schema['properties']:
            return deepcopy(raw), {'synthetic': True}
        assert 'story_compliant' in schema['required']
        verdict = {'supported': True, 'issues': []}
        if decision != 'missing': verdict['story_compliant'] = decision
        return verdict, {'synthetic': True}
    monkeypatch.setattr(storyboard, 'ask', ask)
    target = tmp_path / 'rejected.json'
    with pytest.raises(ValueError, match='source/story checks'):
        planner.draft('Synthetic fixture question?', target, source_records=records())
    assert not target.exists()
    report = json.loads(target.with_suffix('.audit.json').read_text())
    assert report['accepted'] is False
    assert all(item['source_check'].get('story_compliant') is not True for item in report['attempts'] if 'source_check' in item)


def test_explicit_source_mode_checks_topic_before_script_inference(monkeypatch, tmp_path):
    monkeypatch.setattr(planner, 'fetch', lambda url: 'Synthetic fixture text. It is not evidence for a real topic.')
    monkeypatch.setattr(storyboard, 'source_pack', lambda topic, sources: sources)
    calls = []
    def reject(topic, sources, model, endpoint):
        calls.append((topic, len(sources)))
        return False, {'accepted': False, 'topic_suitability_accepted': False}
    monkeypatch.setattr(evidence, 'screen', reject)
    def forbidden(*args, **kwargs): raise AssertionError('Script inference started before source acceptance')
    monkeypatch.setattr(storyboard, 'ask', forbidden)
    target = tmp_path / 'rejected.json'
    with pytest.raises(ValueError, match='Topic/source acceptance failed'):
        planner.draft('Synthetic fixture question?', target, source_urls=['https://example.org/one', 'https://example.org/two'])
    assert calls == [('Synthetic fixture question?', 2)] and not target.exists()
    assert json.loads(target.with_suffix('.source-acceptance.json').read_text())['accepted'] is False


def test_independent_evidence_rejection_cannot_be_overridden_by_binary_review(monkeypatch, tmp_path):
    from curiosity import entailment
    raw = patch_valid_draft(monkeypatch)
    def ask(model, system, prompt, schema, *args, **kwargs):
        if 'slots' in schema['properties']: return deepcopy(raw), {'synthetic': True}
        raise AssertionError('Binary review ran after independent evidence rejection')
    monkeypatch.setattr(storyboard, 'ask', ask)
    monkeypatch.setattr(entailment, 'story', lambda obj: {'accepted': False, 'pairs': [{'line': 2, 'accepted': False}]})
    target = tmp_path / 'rejected.json'
    with pytest.raises(ValueError, match='source/story checks'):
        planner.draft('Synthetic fixture question?', target, source_records=records())
    report = json.loads(target.with_suffix('.audit.json').read_text())
    assert not target.exists() and report['accepted'] is False
    assert all(item['independent_entailment']['accepted'] is False for item in report['attempts'])


def test_final_specification_cannot_be_marked_accepted_before_validation(monkeypatch, tmp_path):
    patch_valid_draft(monkeypatch)
    def reject(obj): raise ValueError('Synthetic invalid final specification')
    monkeypatch.setattr(spec, 'validate_spec', reject)
    target = tmp_path / 'test.json'
    with pytest.raises(ValueError, match='Synthetic invalid'): planner.draft('Synthetic fixture question?', target, source_records=records())
    report = json.loads(target.with_suffix('.audit.json').read_text())
    assert report['accepted'] is False and report['failure_stage'] == 'episode_specification'
    assert not target.exists()


def test_accepted_draft_uses_generation_contract_not_posthoc_beat_repair(monkeypatch, tmp_path):
    from curiosity import staging
    raw = patch_valid_draft(monkeypatch)
    def forbidden(*args, **kwargs): raise AssertionError('Post-generation beat repair is not allowed in this path')
    monkeypatch.setattr(staging, 'stage_story', forbidden)
    target = tmp_path / 'test.json'
    obj = planner.draft('Synthetic fixture question?', target, source_records=records())
    report = json.loads(target.with_suffix('.audit.json').read_text())
    preflight = json.loads(target.with_suffix('.specification.json').read_text())
    assert report['accepted'] and report['episode_specification_accepted']
    assert preflight['spoken_word_bounds'] == [176, 228] and preflight['post_generation_narration_repair'] is False
    assert [x['text'] for x in obj['lines']] == [raw['slots'][name]['text'] for name, _, _ in story_slots.LAYOUT]
    assert obj['science_reviewed'] is False


def test_failed_contract_preserves_untrusted_draft_for_inspection_without_starting_media(monkeypatch, tmp_path):
    from curiosity.remote_ai import ModelOutputInvalid
    raw, _ = fixture(); saved = deepcopy(raw)
    monkeypatch.setattr(storyboard, 'source_pack', lambda topic, sources: sources)
    calls = []
    def reject(*args, **kwargs):
        calls.append(args[2])
        raise ModelOutputInvalid({'validation': 'schema_invalid', 'violations': [
            {'path': ['slots', 'pip_open', 'text'], 'rule': 'pattern', 'words': 7}]}, model_output=deepcopy(raw))
    monkeypatch.setattr(storyboard, 'ask', reject)
    target = tmp_path / 'test.json'
    with pytest.raises(ValueError, match='source/story checks'):
        planner.draft('Synthetic fixture question?', target, source_records=records())
    assert len(calls) == 3 and not target.exists() and raw == saved
    diagnostics = sorted(tmp_path.glob('test.invalid-contract-*.json'))
    assert len(diagnostics) == 3
    for path in diagnostics:
        record = json.loads(path.read_text())
        assert record['diagnostic_only'] and record['untrusted_model_output'] and record['not_a_verified_episode']
        assert record['model_output'] == raw
    assert calls[1]['revision_feedback'][0]['previous_contract_failure']['violations'][0]['words'] == 7
