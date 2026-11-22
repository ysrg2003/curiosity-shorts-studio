"""Synthetic acceptance tests. They never supply production topics or model weights."""
from copy import deepcopy
import hashlib
import io
import json
import pytest
from curiosity import entailment, generated_motion, readability, remote_ai, storyboard


def test_structure_schema_does_not_force_prose_boundaries_but_client_contract_stays():
    schema = {'type': 'object', 'properties': {'text': {'type': 'string', 'minLength': 10, 'maxLength': 20, 'pattern': '^test$'}, 'mode': {'type': 'string', 'enum': ['safe']}}}
    saved = deepcopy(schema)
    requested = storyboard.inference_schema(schema)
    assert requested['properties']['text'] == {'type': 'string'}
    assert requested['properties']['mode']['enum'] == ['safe'] and schema == saved


def test_local_structural_generation_still_rejects_original_prose_contract(monkeypatch):
    seen = []
    def response(request, **kwargs):
        seen.append(json.loads(request.data))
        return io.StringIO(json.dumps({'response': '{"text":"short"}', 'done': True, 'done_reason': 'stop'}))
    monkeypatch.setattr(storyboard, 'urlopen', response)
    monkeypatch.setenv('CURIOSITY_LLM_BACKEND', 'ollama')
    schema = {'type': 'object', 'properties': {'text': {'type': 'string', 'minLength': 12}}, 'required': ['text']}
    with pytest.raises(remote_ai.ModelOutputInvalid): storyboard.ask('synthetic', 'synthetic', {}, schema)
    assert seen[0]['format']['properties']['text'] == {'type': 'string'}


@pytest.mark.parametrize('text', ['These ordinary words end in an unfinished', 'These are ordinary words with joinedwordsthatdonotexist.'])
def test_malformed_narration_is_rejected_without_any_repair(text):
    obj = {'lines': [{'text': text}]}; saved = deepcopy(obj)
    with pytest.raises(ValueError): readability.validate_narration(obj, [])
    assert obj == saved


def test_source_vocabulary_is_allowed_without_silently_correcting_new_terms():
    obj = {'lines': [{'text': 'This fictional fixture mentions quizzacious objects in an imaginary source.'}]}
    saved = deepcopy(obj)
    report = readability.validate_narration(obj, [{'text': 'A fictional source uses the invented term quizzacious.'}])
    assert report['accepted'] and report['text_modified'] is False and obj == saved


def test_missing_direct_source_answer_never_starts_independent_inference(monkeypatch):
    def forbidden(*args): raise AssertionError('Missing evidence reached inference')
    monkeypatch.setattr(entailment, 'score_pairs', forbidden)
    assert not entailment.source_answer('Synthetic question?', {}, {})['accepted']


@pytest.mark.parametrize('accepted', [False, True])
def test_source_answer_must_pass_independent_entailment(monkeypatch, accepted):
    captured = []
    def scores(pairs): captured.extend(pairs); return {'accepted': accepted, 'pairs': []}
    monkeypatch.setattr(entailment, 'score_pairs', scores)
    verdict = {'answer': 'Synthetic objects move in this fictional fixture.', 'answer_quote_ids': ['S0Q0']}
    entries = {'S0Q0': {'quote': 'Synthetic objects move in this fictional fixture.'}}
    assert entailment.source_answer('Why do synthetic objects move?', verdict, entries)['accepted'] is accepted
    assert captured == [(entries['S0Q0']['quote'], verdict['answer'])]


def test_story_entailment_checks_spoken_sentences_and_uncertainty_metadata(monkeypatch):
    calls = []
    def scores(pairs):
        calls.append(pairs)
        accepted = len(calls) == 1
        return {'accepted': accepted, 'pairs': [{'accepted': accepted} for _ in pairs]}
    monkeypatch.setattr(entailment, 'score_pairs', scores)
    obj = {'lines': [{'speaker': 'RAY', 'text': 'Exactly. Synthetic objects move.', 'evidence': [{'quote': 'Synthetic objects move.'}]}], 'uncertainties': ['An unsupported limitation.']}
    assert not entailment.story(obj)['accepted']
    assert calls[0][0][1] == 'Synthetic objects move.' and calls[1][0][1] == obj['uncertainties'][0]


def test_model_cache_requires_exact_pinned_size_and_hash(monkeypatch, tmp_path):
    data = b'synthetic model bytes, not executable'; digest = hashlib.sha256(data).hexdigest()
    monkeypatch.setenv('HOME', str(tmp_path)); monkeypatch.setattr(entailment, 'FILES', {'fixture.bin': (digest, len(data))})
    monkeypatch.setattr(entailment, 'urlopen', lambda *a, **k: io.BytesIO(data))
    path = entailment.artifact('fixture.bin'); assert path.read_bytes() == data
    path.write_bytes(b'tampered')
    monkeypatch.setattr(entailment, 'urlopen', lambda *a, **k: io.BytesIO(b'incorrect replacement'))
    with pytest.raises(ValueError, match='size/hash'): entailment.artifact('fixture.bin')


def test_portrait_prompt_removes_legacy_example_instead_of_appending_contradictions():
    source = 'Rules. === SAFE AREA old max_w=11.0 === END SAFE AREA === More rules. Worked example of a SAFE scene structure max_w=11.0 Your output MUST follow this structure.'
    prompt = generated_motion.portrait_system(source)
    assert 'max_w=11' not in prompt and 'Worked example' not in prompt
    assert 'NATIVE PORTRAIT GEOMETRY' in prompt and 'More rules.' in prompt
    with pytest.raises(ValueError): generated_motion.portrait_system('Unknown upstream layout')


@pytest.mark.parametrize('code', ['obj.to_edge(DOWN)', 'obj.to_corner(UL)', 'fit(obj, max_w=11.0)', 'def fit(obj, max_w=11.0):\n    return obj'])
def test_portrait_lint_rejects_conflicting_geometry_before_render(code):
    assert generated_motion.portrait_lint(code)


def test_script_preflight_only_drafts_and_never_starts_media(monkeypatch, tmp_path):
    from curiosity import script_preflight
    import subprocess
    (tmp_path / 'studio.json').write_text(json.dumps({'draft_model': 'synthetic'}))
    monkeypatch.setattr(script_preflight, 'ROOT', tmp_path)
    monkeypatch.setattr(script_preflight, 'select_and_research', lambda model, previous: ('Synthetic fixture question?', [], {'synthetic': True}))
    calls = []
    monkeypatch.setattr(script_preflight, 'draft', lambda *args, **kwargs: calls.append((args, kwargs)))
    def forbidden(*args, **kwargs): raise AssertionError('Script-only experiment started a subprocess')
    monkeypatch.setattr(subprocess, 'run', forbidden)
    script_preflight.main()
    result = json.loads((tmp_path / 'drafts/preflight-result.json').read_text())
    assert len(calls) == 1 and not result['audio_created'] and not result['video_created'] and not result['upload_attempted']
    assert result['operator_topic_or_source_input'] is False


def test_script_preflight_research_failure_cannot_emit_success(monkeypatch, tmp_path):
    from curiosity import script_preflight
    (tmp_path / 'studio.json').write_text(json.dumps({'draft_model': 'synthetic'}))
    monkeypatch.setattr(script_preflight, 'ROOT', tmp_path)
    def reject(*args): raise script_preflight.ResearchUnavailable('Synthetic rejection', {'accepted': False})
    monkeypatch.setattr(script_preflight, 'select_and_research', reject)
    with pytest.raises(script_preflight.ResearchUnavailable): script_preflight.main()
    assert not (tmp_path / 'drafts/preflight-result.json').exists()


def test_portrait_lint_allows_explicit_safe_positions():
    assert not generated_motion.portrait_lint('obj.move_to(LEFT * 2 + UP * 1)\nfit(obj,max_w=3.5)')
