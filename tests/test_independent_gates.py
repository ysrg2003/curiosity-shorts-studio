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


def test_removed_string_limits_are_visible_in_prompt_and_failure_fields(monkeypatch):
    captured = []
    def response(request, **kwargs):
        captured.append(json.loads(request.data))
        return io.StringIO(json.dumps({'response': '{"answer":"Synthetic response is too long."}',
                                      'eval_count': 12, 'prompt_eval_count': 30,
                                      'total_duration': 1000000000, 'done_reason': 'stop'}))
    monkeypatch.setenv('CURIOSITY_LLM_BACKEND', 'ollama')
    monkeypatch.setattr(storyboard, 'urlopen', response)
    schema = {'type': 'object', 'properties': {'answer': {'type': 'string', 'maxLength': 10}}, 'required': ['answer']}
    saved = deepcopy(schema)
    with pytest.raises(remote_ai.ModelOutputInvalid) as found:
        storyboard.ask('synthetic', 'synthetic fixture only', {'synthetic': True}, schema)
    failure = found.value.metadata
    assert failure['violations'] == [{'path': ['answer'], 'rule': 'maxLength', 'characters': 31,
                                       'words': 5, 'required': 10}]
    assert 'Synthetic response' not in str(failure)
    assert failure['generation']['output_tokens'] == 12
    assert found.value.model_output == {'answer': 'Synthetic response is too long.'}
    payload = captured[0]
    assert payload['format']['properties']['answer'] == {'type': 'string'}
    prompt = json.loads(payload['prompt'])
    assert prompt['prose_output_contract'] == [{'paths': ['answer'], 'maxLength': 10}]
    assert prompt['request'] == {'synthetic': True} and schema == saved


def test_string_contract_compacts_identical_bounds_without_dropping_any_path():
    schema = {'type': 'object', 'properties': {
        'one': {'type': 'string', 'maxLength': 5},
        'two': {'type': 'array', 'items': {'type': 'string', 'maxLength': 5}},
        'three': {'type': 'string', 'pattern': '^test$'}}}
    assert storyboard.string_contract(schema) == [
        {'paths': ['one', 'two[]'], 'maxLength': 5},
        {'paths': ['three'], 'pattern': '^test$'}]


def test_remote_path_preserves_same_full_contract_and_specific_diagnostics(monkeypatch):
    captured = []
    def request(prompt, system, **kwargs):
        captured.append(json.loads(prompt))
        return {'answer': 'long synthetic fixture'}, {'synthetic': True}
    monkeypatch.setenv('CURIOSITY_LLM_BACKEND', 'openrouter-free')
    monkeypatch.setattr(remote_ai, 'request', request)
    schema = {'type': 'object', 'properties': {'answer': {'type': 'string', 'maxLength': 2}}}
    with pytest.raises(remote_ai.ModelOutputInvalid) as found:
        storyboard.ask('synthetic', 'synthetic', {}, schema)
    assert found.value.metadata['violations'][0]['path'] == ['answer']
    assert captured[0]['prose_output_contract'][0]['maxLength'] == 2


def source_contract_fixture():
    sources = [{'url': 'https://example.org/fixture', 'text': 'Synthetic objects move inside this fictional bounded test fixture.'},
               {'url': 'https://example.net/fixture', 'text': 'This fictional fixture describes synthetic objects moving inside a bounded test.'}]
    verdict = {'answer_claims':[{'sentence':sources[0]['text'],'quote_ids':['S0Q0','S1Q0']}], 'scope_constraints':[], 'topic_assessment': {'suitable': True, 'reason': 'fits_short_visual_science'},
               'source_assessments': [{'source_index': i, 'usable': True, 'reason': 'current_observation_or_mechanism'} for i in range(2)],
               'answer': sources[0]['text'], 'answer_quote_ids': ['S0Q0', 'S1Q0'], 'supported': True,
               'observable_quote_ids': ['S0Q0'], 'mechanism_quote_ids': ['S1Q0'], 'issues': []}
    failure = {'validation': 'schema_invalid', 'violations': [{'path': ['answer'], 'rule': 'maxLength', 'required': 500, 'characters': 501}]}
    return sources, verdict, failure


def test_source_contract_retry_is_bounded_specific_and_still_requires_independent_gate(monkeypatch):
    from curiosity import evidence
    sources, verdict, failure = source_contract_fixture(); saved = deepcopy(sources)
    calls = []; independent = []
    def ask(model, system, prompt, schema, endpoint, seed, **kwargs):
        calls.append(deepcopy(prompt))
        assert schema['properties']['answer']['maxLength'] == 500
        assert schema['properties']['source_assessments']['items']['properties']['reason']['enum'][0] == 'current_observation_or_mechanism'
        if len(calls) == 1: raise remote_ai.ModelOutputInvalid(failure)
        return deepcopy(verdict), {'synthetic': True}
    def score(pairs): independent.extend(pairs); return {'accepted': False, 'pairs': []}
    monkeypatch.setattr(storyboard, 'ask', ask)
    monkeypatch.setattr(entailment, 'score_pairs', score)
    accepted, audit = evidence.screen('Why do synthetic objects move?', sources, 'synthetic')
    assert len(calls) == 2 and not accepted and independent
    assert calls[1]['revision_feedback']['previous_contract_failure']['violations'][0]['characters'] == 501
    assert audit['assessment_attempts'][0]['contract_accepted'] is False
    assert audit['assessment_attempts'][1]['contract_accepted'] is True
    assert audit['approved_source_indices'] == [] and sources == saved


def test_two_invalid_source_contract_attempts_do_not_reach_science_or_draft(monkeypatch):
    from curiosity import evidence
    sources, verdict, failure = source_contract_fixture(); calls = []
    def reject(*args, **kwargs): calls.append(1); raise remote_ai.ModelOutputInvalid(failure)
    def forbidden(*args): raise AssertionError('Invalid source assessment reached independent science inference')
    monkeypatch.setattr(storyboard, 'ask', reject)
    monkeypatch.setattr(entailment, 'score_pairs', forbidden)
    with pytest.raises(remote_ai.ModelOutputInvalid) as found:
        evidence.screen('Why do synthetic objects move?', sources, 'synthetic')
    assert len(calls) == 2 and len(found.value.metadata['source_assessment_attempts']) == 2


def test_source_contract_failure_preserves_actual_retrieval_provenance(monkeypatch):
    from curiosity import autonomy, evidence
    sources, verdict, failure = source_contract_fixture()
    candidates = [{'question': 'Synthetic fixture question?', 'search_terms': 'synthetic fixture'}]
    research = {'retrieval_attempts': [{'requested_url': 'https://example.org/fixture', 'status': 'retrieved'}]}
    monkeypatch.setattr(autonomy, 'questions', lambda *a, **k: (candidates, {}))
    monkeypatch.setattr(autonomy, 'research', lambda *a, **k: (sources, deepcopy(research)))
    def reject(*args, **kwargs): raise remote_ai.ModelOutputInvalid(failure)
    monkeypatch.setattr(evidence, 'screen', reject)
    with pytest.raises(autonomy.ResearchUnavailable) as found:
        autonomy.select_and_research('synthetic', [])
    audit = found.value.diagnostics['rejections'][0]
    assert audit['status'] == 'source_assessment_contract_invalid'
    assert audit['details']['research'] == research
    assert audit['details']['model_contract']['violations'][0]['path'] == ['answer']


def test_contract_diagnostics_are_bounded_and_do_not_copy_generated_values():
    schema = {'type': 'object', 'properties': {f'field{i}': {'type': 'string', 'maxLength': 1} for i in range(15)}}
    obj = {f'field{i}': 'synthetic generated prose' for i in range(15)}
    report = storyboard.schema_failures(obj, schema)
    assert len(report['violations']) == 12 and report['more_violations']
    assert 'synthetic generated prose' not in json.dumps(report)
    feedback = storyboard.revision_feedback({'validation': 'schema_invalid', **report, 'unrelated_raw_value': 'not allowed'})
    assert 'not allowed' not in json.dumps(feedback)


def test_valid_negative_source_verdict_is_not_retried_into_approval(monkeypatch):
    from curiosity import evidence
    sources, verdict, failure = source_contract_fixture(); verdict['supported'] = False; calls = []
    def ask(*args, **kwargs): calls.append(1); return deepcopy(verdict), {'synthetic': True}
    def forbidden(*args): raise AssertionError('Negative source verdict reached independent inference')
    monkeypatch.setattr(storyboard, 'ask', ask)
    monkeypatch.setattr(entailment, 'score_pairs', forbidden)
    accepted, audit = evidence.screen('Why do synthetic objects move?', sources, 'synthetic')
    assert len(calls) == 1 and not accepted and audit['approved_source_indices'] == []


def test_negative_empty_answer_is_valid_data_and_does_not_trigger_rewrite_or_science(monkeypatch):
    from curiosity import evidence
    from jsonschema import Draft202012Validator
    sources, verdict, failure = source_contract_fixture(); calls = []
    verdict.update(supported=False, answer='', answer_quote_ids=[], answer_claims=[], issues=['answer_not_supported'])
    def ask(model, system, prompt, schema, *args, **kwargs):
        calls.append(1)
        assert Draft202012Validator(schema).is_valid(verdict)
        assert prompt['audit_contract']['negative_answer_may_be_empty'] is True
        return deepcopy(verdict), {'synthetic': True}
    def forbidden(*args): raise AssertionError('Negative verdict reached science inference')
    monkeypatch.setattr(storyboard, 'ask', ask)
    monkeypatch.setattr(entailment, 'score_pairs', forbidden)
    accepted, audit = evidence.screen('Why do synthetic objects move?', sources, 'synthetic')
    assert not accepted and len(calls) == 1 and audit['verdict']['answer'] == ''


def test_positive_empty_answer_cannot_pass_or_start_independent_inference(monkeypatch):
    from curiosity import evidence
    sources, verdict, failure = source_contract_fixture(); verdict['answer'] = ''
    monkeypatch.setattr(storyboard, 'ask', lambda *a, **k: (deepcopy(verdict), {'synthetic': True}))
    def forbidden(*args): raise AssertionError('Empty positive answer reached inference')
    monkeypatch.setattr(entailment, 'score_pairs', forbidden)
    accepted, audit = evidence.screen('Why do synthetic objects move?', sources, 'synthetic')
    assert not accepted and audit['independent_entailment']['accepted'] is False


@pytest.mark.parametrize('inconsistent', ['topic', 'source'])
def test_reason_codes_cannot_contradict_positive_decision_flags(monkeypatch, inconsistent):
    from curiosity import evidence
    sources, verdict, failure = source_contract_fixture()
    if inconsistent == 'topic': verdict['topic_assessment']['reason'] = 'medical_or_disease'
    else: verdict['source_assessments'][0]['reason'] = 'historical_or_obsolete'
    monkeypatch.setattr(storyboard, 'ask', lambda *a, **k: (deepcopy(verdict), {'synthetic': True}))
    def forbidden(*args): raise AssertionError('Inconsistent decisions reached inference')
    monkeypatch.setattr(entailment, 'score_pairs', forbidden)
    accepted, audit = evidence.screen('Why do synthetic objects move?', sources, 'synthetic')
    assert not accepted and audit['approved_source_indices'] == []


def test_source_audit_reasons_are_closed_codes_and_positive_answer_gate_is_unchanged(monkeypatch):
    from curiosity import evidence
    from jsonschema import Draft202012Validator
    sources, verdict, failure = source_contract_fixture(); calls = []
    def ask(model, system, prompt, schema, *args, **kwargs):
        validator = Draft202012Validator(schema)
        assert validator.is_valid(verdict)
        assert schema['additionalProperties'] is False
        assert schema['properties']['answer']['maxLength'] == 500
        reason = schema['properties']['source_assessments']['items']['properties']['reason']
        assert 'enum' in reason and 'maxLength' not in reason
        bad = deepcopy(verdict); bad['source_assessments'][0]['reason'] = 'unbounded generated audit prose'
        assert not validator.is_valid(bad)
        return deepcopy(verdict), {'synthetic': True}
    def scores(pairs): calls.extend(pairs); return {'accepted': False, 'pairs': []}
    monkeypatch.setattr(storyboard, 'ask', ask)
    monkeypatch.setattr(entailment, 'score_pairs', scores)
    accepted, audit = evidence.screen('Why do synthetic objects move?', sources, 'synthetic')
    assert calls and not accepted and audit['approved_source_indices'] == []


def test_source_catalog_does_not_offer_truncated_sentence_fragments():
    from curiosity import evidence
    good = 'Synthetic objects move inside this fictional bounded test fixture.'
    fragment = ' An unfinished source fragment has enough words but no ending'
    sources = [{'text': good + fragment}, {'text': good}]; saved = deepcopy(sources)
    entries = evidence.catalog(sources)
    assert len(entries) == 2 and all(item['quote'] == good for item in entries.values())
    assert sources == saved


def test_rejected_source_answer_keeps_exact_selected_evidence_and_source_hashes(monkeypatch):
    from curiosity import evidence
    sources,verdict,_=source_contract_fixture();saved=deepcopy(sources)
    monkeypatch.setattr(storyboard,'ask',lambda *args,**kwargs:(deepcopy(verdict),{'synthetic':True}))
    monkeypatch.setattr(entailment,'score_pairs',lambda pairs:{'accepted':False,'pairs':[]})
    accepted,audit=evidence.screen('Why do synthetic objects move?',sources,'synthetic')
    assert not accepted and sources==saved
    selected={row['quote_id']:row for row in audit['selected_original_evidence']}
    assert set(selected)=={'S0Q0','S1Q0'}
    for key,row in selected.items():
        index=row['source_index']
        assert row['quote'] in sources[index]['text']
        assert audit['source_snapshot'][index]['excerpt_sha256']==hashlib.sha256(sources[index]['text'].encode()).hexdigest()
        assert audit['source_snapshot'][index]['url']==sources[index]['url']


def test_semantic_reranker_pin_validation_rejects_corrupted_download(monkeypatch,tmp_path):
    data=b'Synthetic relevance model fixture, never executable.'
    monkeypatch.setenv('HOME',str(tmp_path))
    monkeypatch.setattr(entailment,'RERANK_FILES',{'fixture.bin':(hashlib.sha256(data).hexdigest(),len(data))})
    monkeypatch.setattr(entailment,'urlopen',lambda *args,**kwargs:io.BytesIO(data))
    path=entailment.rerank_artifact('fixture.bin');assert path.read_bytes()==data
    path.write_bytes(b'corrupt')
    monkeypatch.setattr(entailment,'urlopen',lambda *args,**kwargs:io.BytesIO(b'incorrect replacement'))
    with pytest.raises(ValueError,match='size/hash'):entailment.rerank_artifact('fixture.bin')


def test_semantic_reranker_batches_and_marks_its_own_window_not_nli_acceptance(monkeypatch):
    import numpy as np
    calls=[]
    class Encoding:
        def __init__(self):self.ids=list(range(600));self.attention_mask=[1]*600;self.type_ids=[0]*600
        def truncate(self,size):self.ids=self.ids[:size];self.attention_mask=self.attention_mask[:size];self.type_ids=self.type_ids[:size]
    class Tokenizer:
        def encode_batch(self,pairs):return [Encoding() for pair in pairs]
    class Session:
        def run(self,outputs,inputs):
            calls.append(inputs)
            assert inputs['input_ids'].shape[1]==512
            return [np.ones((len(inputs['input_ids']),1))]
    monkeypatch.setattr(entailment,'rerank_engine',lambda:(Tokenizer(),Session()))
    result=entailment.relevance_scores('Synthetic retrieval query?',['Fictional passage.']*33)
    assert result==[1.0]*33 and [len(call['input_ids']) for call in calls]==[16,16,1]
    assert entailment.THRESHOLD==0.90 and entailment.relevance_scores('Synthetic?',[])==[]
    with pytest.raises(ValueError):entailment.relevance_scores('Synthetic?',['Fictional.']*501)
    with pytest.raises(ValueError):entailment.relevance_scores('Synthetic?',[''])


def test_semantic_discovery_never_deletes_a_page_for_sparse_word_overlap(monkeypatch):
    from curiosity import autonomy
    seen=[]
    monkeypatch.setattr(autonomy,'public_url',lambda url:url)
    def pages(query):return [
        {'pageid':1,'title':'Fictional Album','extract':'A fictional music album with the same metaphorical words. '*15,'fullurl':'https://en.wikipedia.org/wiki/Album'},
        {'pageid':2,'title':'Inclined plane','extract':'An inclined plane allows a fictional glass bead to roll under gravity. '*15,'fullurl':'https://en.wikipedia.org/wiki/Incline'}]
    monkeypatch.setattr(autonomy,'wiki_pages',pages)
    def scores(question,texts):return [10.0 if 'inclined' in text.lower() else -10.0 for text in texts]
    monkeypatch.setattr(entailment,'relevance_scores',scores)
    def links(index):seen.append(index);return [{'url':'https://fixture.edu/article','context':'Inclined plane and fictional glass bead.'}]
    monkeypatch.setattr(autonomy,'wiki_links',links)
    monkeypatch.setattr(autonomy,'article',lambda url:{'url':url,'title':'Fictional inclined plane','text':'An inclined plane explains a fictional fixture. '*30})
    sources,audit=autonomy.research('Why does a fictional glass bead roll?','gravity','fictional glass bead')
    assert sources[0]['title']=='Inclined plane' and set(seen)=={1,2}
    assert audit['retrieval_logits_are_not_probabilities'] and audit['retrieval_window_tokens']==512
    assert all(row['status']!='subject_mismatch_skipped' for row in audit['discovery'])


def test_sentence_specific_answer_evidence_covers_every_original_sentence(monkeypatch):
    entries={'A':{'quote':'Synthetic gears turn only when the fictional lever is pressed.'},'B':{'quote':'Synthetic flags rise only when their fictional rope is pulled.'}}
    calls=[]
    def scores(pairs):calls.extend(pairs);return {'accepted':True,'pairs':[{'accepted':True} for _ in pairs]}
    monkeypatch.setattr(entailment,'score_pairs',scores)
    one='Synthetic gears turn when the fictional lever is pressed.';two='Synthetic flags rise when their fictional rope is pulled.'
    verdict={'answer':one+' '+two,'answer_quote_ids':['A','B'],'answer_claims':[{'sentence':one,'quote_ids':['A']},{'sentence':two,'quote_ids':['B']}]}
    assert entailment.source_answer('Why do synthetic gears turn?',verdict,entries)['accepted']
    assert calls==[(entries['A']['quote'],one),(entries['B']['quote'],two)]
    verdict['answer_claims'][1]['sentence']='Modified invented sentence.'
    assert not entailment.source_answer('Why do synthetic gears turn?',verdict,entries)['accepted']


def test_scope_critic_factual_basis_requires_independent_entailment(monkeypatch):
    entries={'A':{'quote':'Synthetic fixtures usually turn in this fictional test.'}};calls=[]
    def scores(pairs):calls.extend(pairs);return {'accepted':False,'pairs':[{'accepted':False}]}
    monkeypatch.setattr(entailment,'score_pairs',scores)
    finding={'source_claim':'Synthetic fixtures cannot turn without this fictional test.','quote_ids':['A']}
    assert not entailment.scope_findings([finding],entries)['accepted']
    assert calls==[(entries['A']['quote'],finding['source_claim'])]
