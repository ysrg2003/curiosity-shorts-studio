from copy import deepcopy
from types import SimpleNamespace
import io
import json
import pytest
from curiosity import evidence,remote_ai,storyboard


@pytest.fixture(autouse=True)
def synthetic_entailment_scores(monkeypatch):
    from curiosity import entailment
    def scores(pairs):
        return {'accepted': True, 'pairs': [{'accepted': True, 'entailment_score': 1.0} for _ in pairs], 'synthetic': True}
    monkeypatch.setattr(entailment, 'score_pairs', scores)


def sources():
    return [
        {'url':'https://example.edu/a','text':'Dr. Example reports that synthetic test objects may move in this fictional experiment. A second synthetic sentence keeps its original commas, apostrophes, and other punctuation.'},
        {'url':'https://example.org/b','text':'Another fictional test source describes a bounded synthetic observation without asserting real scientific facts. This second sentence provides independent synthetic text for the unit test only.'},
    ]


def test_sentence_catalog_slices_unaltered_sources_including_abbreviations():
    packed=sources();entries=evidence.catalog(packed)
    assert len({v['source_index'] for v in entries.values()})==2
    assert any(v['quote'].startswith('Dr. Example reports') for v in entries.values())
    for value in entries.values():
        text=packed[value['source_index']]['text']
        assert value['quote']==text[value['start']:value['end']].strip()
        assert 8<=len(value['quote'].split())<=55


def test_binding_never_invents_repairs_or_edits_a_source_quote():
    entries=evidence.catalog(sources());key=next(iter(entries))
    obj={'lines':[{'evidence':[{'quote_id':key}]}]};saved=deepcopy(obj)
    bound=evidence.bind(obj,entries)
    assert obj==saved and bound['lines'][0]['evidence'][0]['quote']==entries[key]['quote']
    with pytest.raises(ValueError,match='Unknown evidence'):evidence.bind({'lines':[{'evidence':[{'quote_id':'invented'}]}]},entries)


def test_draft_uses_existing_ids_and_fixed_odd_line_count_without_authored_words():
    entries=evidence.catalog(sources());schema=evidence.drafting_schema(entries)
    slots=schema['properties']['slots'];assert len(slots['properties'])==13
    assert slots['required']==list(slots['properties']) and slots['additionalProperties'] is False
    item=slots['properties']['ray_setup']['properties']['evidence']['items']
    assert list(item['properties'])==['quote_id'] and item['properties']['quote_id']['enum']==list(entries)


def test_relevance_requires_true_boolean_and_observation_mechanism_two_sources(monkeypatch):
    mode=['valid']
    def ask(model,system,prompt,schema,endpoint,seed,effort):
        if 'complete_answer' in schema['properties']:return {'complete_answer':True,'qualifiers_preserved':True,'no_exclusive_or_universal_overclaim':True,'issues':[]},{}
        assert effort=='low'
        ids=list(prompt['sentence_catalog']);first=next(k for k in ids if k.startswith('S0'));second=next(k for k in ids if k.startswith('S1'))
        return {'topic_assessment':{'suitable':True,'reason':'fits_short_visual_science'},'source_assessments':[{'source_index':i,'usable':True,'reason':'current_observation_or_mechanism'} for i in range(2)],'answer':'Synthetic observations remain fictional in this bounded unit test.','answer_quote_ids':[first,second],'supported':True if mode[0]!='string_false' else 'false','observable_quote_ids':[first],'mechanism_quote_ids':[second if mode[0]!='one_source' else first],'issues':[]},{'usage':{'cost':'0'}}
    monkeypatch.setattr(storyboard,'ask',ask)
    assert evidence.screen('Synthetic observation?',sources(),'synthetic')[0]
    mode[0]='one_source';assert not evidence.screen('Synthetic observation?',sources(),'synthetic')[0]
    mode[0]='string_false';assert not evidence.screen('Synthetic observation?',sources(),'synthetic')[0]


def test_relevance_rejection_moves_only_to_remaining_model_proposed_candidates(monkeypatch):
    from curiosity import autonomy
    candidates=[{'question':f'Why does synthetic fixture {i} move?','search_terms':'synthetic movement'} for i in range(3)]
    monkeypatch.setattr(evidence,'plan_sources',lambda *args:(True,{'selected_original_paths':[],'synthetic':True}))
    monkeypatch.setattr(autonomy,'questions',lambda *a,**k:(candidates,{}))
    calls=[]
    monkeypatch.setattr(autonomy,'research',lambda *a:(sources(),{'not_a_truth_guarantee':True}))
    def screen(question,*args):
        calls.append(question);return len(calls)==2,{'accepted':len(calls)==2,'approved_source_indices':[0,1]}
    monkeypatch.setattr(evidence,'screen',screen)
    selected,_,audit=autonomy.select_and_research('synthetic',[])
    assert selected==candidates[1]['question'] and calls==[c['question'] for c in candidates[:2]]
    assert len(audit['rejections'])==1 and not audit['operator_topic_or_source_input']


def test_local_model_output_receives_the_same_typed_boolean_validation(monkeypatch):
    monkeypatch.setenv('CURIOSITY_LLM_BACKEND','ollama')
    monkeypatch.setattr(storyboard,'urlopen',lambda *a,**k:io.StringIO(json.dumps({'response':json.dumps({'supported':'false'})})))
    schema={'type':'object','properties':{'supported':{'type':'boolean'}},'required':['supported']}
    with pytest.raises(remote_ai.ModelOutputInvalid):storyboard.ask('synthetic','synthetic',{},schema)


def test_low_reasoning_profile_is_explicit_bounded_and_uses_existing_adapter(monkeypatch):
    adapter=pytest.importorskip('ai_router.providers.openai_compatible')
    monkeypatch.setenv('OPENROUTER_API_KEY','synthetic-unit-test-only')
    monkeypatch.setattr(remote_ai,'check_free_catalog',lambda:{remote_ai.MODEL})
    calls=[]
    def post(*a,**k):
        calls.append(k['json']);return SimpleNamespace(status_code=200,json=lambda:{'choices':[{'finish_reason':'stop','message':{'content':'{"supported":true}'}}],'usage':{'cost':0}})
    monkeypatch.setattr(adapter.requests,'post',post)
    _,stats=remote_ai.request('synthetic','synthetic',json_mode=True,effort='low')
    assert calls[0]['reasoning_effort']=='low' and calls[0]['max_tokens']==12000 and stats['reasoning_effort']=='low'
    with pytest.raises(ValueError,match='Unsupported controlled'):remote_ai.request('synthetic','synthetic',effort='high')
    assert len(calls)==1


def test_adjacent_short_sentences_are_bound_as_an_original_contiguous_span():
    packed=[{'text':'A fictional test starts. It describes synthetic objects without making a real scientific assertion.'},{'text':'Another fictional source contains enough original words to support this bounded unit test.'}]
    entries=evidence.catalog(packed)
    assert entries['S0Q0']['quote']==packed[0]['text']


def test_source_pack_preserves_contiguous_original_text_instead_of_splicing():
    text='Synthetic movement appears in this opening sentence for bounded extraction. '+('Neutral filler sentences preserve their original punctuation and exact source spacing. '*100)+' Synthetic movement appears again only after a long original gap.'
    packed=storyboard.source_pack('Synthetic movement',[{'url':'https://example.edu/a','text':text},{'url':'https://example.org/b','text':text}],budget=2400)
    for item in packed:
        assert item['text'] in text and len(item['text'])<=1200
    for entry in evidence.catalog(packed).values():assert entry['quote'] in text


def test_source_pack_keeps_document_origin_separate_within_same_budget():
    from curiosity.storyboard import source_pack
    opening='Historical account from an earlier scientific era. '
    text=opening+('Neutral background without the selected mechanism. '*50)+('Synthetic movement follows a clear observable causal process. '*15)
    source={'url':'https://example.edu/archive','title':'Archive','text':text}
    packed=source_pack('Synthetic movement',[source,source],budget=2400)
    for item in packed:
        assert item['document_opening']==text[:600]
        assert item['text'] in text and opening not in item['text']
        assert len(item['text'])+len(item['document_opening'])<=1200
    assert source['text']==text and 'document_opening' not in source


@pytest.mark.parametrize('mode',['flagged_source','duplicate_assessment','missing_assessment','string_usable','issues','unknown_quote'])
def test_relevance_rejects_inconsistent_source_assessments_and_selected_evidence(monkeypatch,mode):
    def ask(model,system,prompt,schema,*args,**kwargs):
        if 'complete_answer' in schema['properties']:return {'complete_answer':True,'qualifiers_preserved':True,'no_exclusive_or_universal_overclaim':True,'issues':[]},{}
        assert schema['properties']['source_assessments']['minItems']==2
        assessments=[{'source_index':0,'usable':True,'reason':'current_observation_or_mechanism'},{'source_index':1,'usable':True,'reason':'current_observation_or_mechanism'}]
        result={'topic_assessment':{'suitable':True,'reason':'fits_short_visual_science'},'source_assessments':assessments,'supported':True,'observable_quote_ids':['S0Q0'],'mechanism_quote_ids':['S1Q0'],'issues':[]}
        if mode=='flagged_source':assessments[1]['usable']=False
        if mode=='duplicate_assessment':assessments[1]['source_index']=0
        if mode=='missing_assessment':assessments.pop()
        if mode=='string_usable':assessments[1]['usable']='true'
        if mode=='issues':result['issues']=['Synthetic remaining issue']
        if mode=='unknown_quote':result['mechanism_quote_ids']=['unrecognized']
        return result,{}
    monkeypatch.setattr(storyboard,'ask',ask)
    accepted,audit=evidence.screen('Synthetic observation?',sources(),'synthetic')
    assert not accepted and audit['approved_source_indices']==[]


def test_valid_source_subset_excludes_unusable_pool_records_before_drafting(monkeypatch):
    from curiosity import autonomy
    pool=sources()+[{'url':'https://example.net/history','text':'A synthetic historical account describes an obsolete fictional theory without asserting current facts.'}]
    monkeypatch.setattr(evidence,'plan_sources',lambda *args:(True,{'selected_original_paths':[],'synthetic':True}))
    monkeypatch.setattr(autonomy,'questions',lambda *args:([{'question':'Synthetic observation?','search_terms':'synthetic mechanism'}],{}))
    monkeypatch.setattr(autonomy,'research',lambda *args:(pool,{}))
    def ask(model,system,prompt,schema,*args,**kwargs):
        if 'complete_answer' in schema['properties']:return {'complete_answer':True,'qualifiers_preserved':True,'no_exclusive_or_universal_overclaim':True,'issues':[]},{}
        return {'topic_assessment':{'suitable':True,'reason':'fits_short_visual_science'},'source_assessments':[{'source_index':i,'usable':i<2,'reason':'current_observation_or_mechanism' if i<2 else 'historical_or_obsolete'} for i in range(3)],'answer':'Synthetic observations remain fictional in this bounded unit test.','answer_quote_ids':['S0Q0','S1Q0'],'supported':True,'observable_quote_ids':['S0Q0'],'mechanism_quote_ids':['S1Q0'],'issues':[]},{}
    monkeypatch.setattr(storyboard,'ask',ask)
    selected,approved,audit=autonomy.select_and_research('synthetic',[])
    assert selected=='Synthetic observation?' and approved==pool[:2] and len(pool)==3
    assert audit['research']['relevance']['approved_source_indices']==[0,1]


@pytest.mark.parametrize('qualification',[False,True])
def test_entailed_answer_still_requires_full_passage_scope_audit(monkeypatch,qualification):
    def ask(model,system,prompt,shape,*args,**kwargs):
        if 'complete_answer' in shape['properties']:
            return {'complete_answer':qualification,'qualifiers_preserved':qualification,'no_exclusive_or_universal_overclaim':qualification,'issues':[] if qualification else ['answer_not_supported']},{}
        ids=list(prompt['sentence_catalog']);first=next(k for k in ids if k.startswith('S0'));second=next(k for k in ids if k.startswith('S1'))
        return {'topic_assessment':{'suitable':True,'reason':'fits_short_visual_science'},'source_assessments':[{'source_index':i,'usable':True,'reason':'current_observation_or_mechanism'} for i in range(2)],'answer':'Synthetic observations remain fictional in this bounded unit test.','answer_quote_ids':[first,second],'supported':True,'observable_quote_ids':[first],'mechanism_quote_ids':[second],'issues':[]},{}
    monkeypatch.setattr(storyboard,'ask',ask)
    accepted,audit=evidence.screen('Synthetic observation?',sources(),'synthetic')
    assert accepted is qualification and audit['independent_entailment']['qualification_audit']['accepted'] is qualification


def test_scope_retry_reuses_only_original_sources_not_generated_answer(monkeypatch):
    calls=[]
    def once(question,records,*args):
        calls.append(deepcopy(records))
        if len(calls)==1:return False,{'independent_entailment':{'qualification_audit':{'complete_answer':False,'qualifiers_preserved':False,'no_exclusive_or_universal_overclaim':False,'grounding':{'accepted':True},'findings':[{'problem':'missing_condition','explanation':'Synthetic condition applies only to this fixture.','source_claim':'Synthetic source proposition only.','quote_ids':['S0Q0']}]}},'verdict':{'answer':'Untrusted unsupported fictional prose.'}}
        return True,{'accepted':True}
    monkeypatch.setattr(evidence,'screen_once',once)
    original=sources();accepted,audit=evidence.screen('Synthetic?',original,'synthetic')
    assert accepted and len(calls)==2 and calls[0]==original
    assert all('scope_audit_feedback' in source for source in calls[1])
    assert all(source['text']==original[i]['text'] and 'answer' not in source for i,source in enumerate(calls[1]))
    assert audit['fresh_scope_assessments']==2 and 'scope_audit_feedback' not in original[0]


def test_unexplained_scope_rejection_cannot_trigger_blind_retry(monkeypatch):
    calls=[]
    def once(*args):
        calls.append(args);return False,{'independent_entailment':{'qualification_audit':{'complete_answer':False,'qualifiers_preserved':False,'no_exclusive_or_universal_overclaim':False,'findings':[]}}}
    monkeypatch.setattr(evidence,'screen_once',once)
    accepted,report=evidence.screen('Synthetic?',sources(),'synthetic')
    assert not accepted and len(calls)==1 and 'scope_retry_skipped' in report


def test_scope_audit_findings_require_original_ids_and_consistent_decision():
    entries=evidence.catalog(sources());key=next(iter(entries))
    audit={'findings':[],'complete_answer':False,'qualifiers_preserved':False,'no_exclusive_or_universal_overclaim':False,'issues':['answer_not_supported']}
    assert not evidence.validate_scope_findings(audit,entries)['accepted']
    audit['findings']=[{'problem':'missing_condition','explanation':'The synthetic fixture applies only under a stated condition.','quote_ids':[key]}]
    assert evidence.validate_scope_findings(audit,entries)['accepted']
    audit['findings'][0]['quote_ids']=['invented']
    assert not evidence.validate_scope_findings(audit,entries)['accepted']


def test_scope_plan_requires_original_source_citations():
    entries=evidence.catalog(sources());key=next(iter(entries))
    plan=[{'condition_or_alternative':'Only under the synthetic fixture conditions.','quote_ids':[key]}]
    assert evidence.validate_scope_plan(plan,entries)['accepted']
    plan[0]['quote_ids']=[]
    assert not evidence.validate_scope_plan(plan,entries)['accepted']


def test_scope_contract_failure_preserves_original_output_and_upstream_evidence(monkeypatch):
    calls=[]
    raw={'findings':[{'explanation':'Untrusted original scope explanation remains unchanged. '*40}]}
    def ask(model,system,prompt,shape,*args,**kwargs):
        calls.append(shape)
        if 'findings' in shape['properties']:
            assert shape['properties']['findings']['items']['properties']['explanation']['maxLength']==1600
            raise remote_ai.ModelOutputInvalid({'validation':'synthetic_contract_failure'},model_output=raw)
        ids=list(prompt['sentence_catalog']);first=next(k for k in ids if k.startswith('S0'));second=next(k for k in ids if k.startswith('S1'))
        return {'scope_constraints':[],'topic_assessment':{'suitable':True,'reason':'fits_short_visual_science'},'source_assessments':[{'source_index':i,'usable':True,'reason':'current_observation_or_mechanism'} for i in range(2)],'answer':'Synthetic observations remain fictional in this bounded unit test.','answer_quote_ids':[first,second],'supported':True,'observable_quote_ids':[first],'mechanism_quote_ids':[second],'issues':[]},{}
    monkeypatch.setattr(storyboard,'ask',ask)
    accepted,report=evidence.screen('Synthetic observation?',sources(),'synthetic')
    assert not accepted and len(calls)==2 and report['approved_source_indices']==[]
    assert report['packed_original_sources']==sources() and report['selected_original_evidence']
    qualification=report['independent_entailment']['qualification_audit']
    assert qualification['untrusted_original_output']==raw and qualification['failure_stage']=='scope_audit_contract_invalid'
    assert report['independent_entailment']['accepted'] is True


def test_scope_diagnostic_length_does_not_relax_source_or_decision_requirements():
    entries=evidence.catalog(sources());key=next(iter(entries))
    audit={'findings':[{'problem':'missing_condition','explanation':'Synthetic diagnostic condition. '*20,'quote_ids':[key]}],'complete_answer':False,'qualifiers_preserved':False,'no_exclusive_or_universal_overclaim':False,'issues':['answer_not_supported']}
    assert evidence.validate_scope_findings(audit,entries)['accepted']
    audit['findings'][0]['quote_ids']=['fabricated']
    assert not evidence.validate_scope_findings(audit,entries)['accepted']


def test_answer_serialization_preserves_original_sentence_bytes_and_derived_ids():
    original={'answer_claims':[{'sentence':'Synthetic gears move only in this fictional fixture.','quote_ids':['A','B']},{'sentence':'The fictional flag may rise under the stated condition.','quote_ids':['B','C']}]}
    saved=deepcopy(original);out=evidence.serialize_answer(original)
    assert original==saved and out['answer']==' '.join(item['sentence'] for item in original['answer_claims'])
    assert out['answer_quote_ids']==['A','B','C']
    assert evidence.serialize_answer({'answer_claims':[]})['answer']==''


def test_retry_receives_verified_propositions_not_unchecked_explanatory_prose(monkeypatch):
    calls=[]
    finding={'problem':'missing_condition','explanation':'UNVERIFIED explanatory inference must not guide generation.','source_claim':'The synthetic fixture may use another fictional input.','quote_ids':['S0Q0']}
    def once(question,records,*args):
        calls.append(deepcopy(records))
        if len(calls)==1:return False,{'independent_entailment':{'qualification_audit':{'complete_answer':False,'qualifiers_preserved':True,'no_exclusive_or_universal_overclaim':True,'grounding':{'accepted':True},'findings':[finding]}}}
        return False,{'accepted':False}
    monkeypatch.setattr(evidence,'screen_once',once)
    evidence.screen('Synthetic?',sources(),'synthetic')
    feedback=calls[1][0]['scope_audit_feedback']
    assert feedback['verified_source_propositions']==[{'source_claim':finding['source_claim'],'quote_ids':['S0Q0']}]
    assert 'UNVERIFIED' not in json.dumps(feedback)


def test_extractive_plan_keeps_distinct_generic_paths_before_any_answer(monkeypatch):
    records=[{'url':'https://example.edu/a','text':'A fictional gate opens when the blue lever moves in this synthetic fixture. A different fictional gate opens when the red switch closes in this synthetic fixture.'},{'url':'https://example.org/b','text':'The synthetic blue lever pathway applies only while the test power is on. The synthetic red switch pathway applies only while the backup power is on.'}]
    calls=[]
    def ask(model,system,prompt,shape,*args,**kwargs):
        calls.append(prompt)
        assert 'answer_claims' not in shape['properties'] and 'answer' not in shape['properties']
        if 'exact_question_supported' in shape['properties']:return {'exact_question_supported':True,'material_paths_covered':True,'unrelated_paths_excluded':True,'missing_or_unrelated_quote_ids':[]},{}
        entries=prompt['sentence_catalog'];blue=next(k for k,v in entries.items() if 'blue lever' in v['quote'] and v['source_index']==0);red=next(k for k,v in entries.items() if 'red switch' in v['quote'] and v['source_index']==0);condition=next(k for k,v in entries.items() if v['source_index']==1)
        return {'source_decisions':[{'source_index':i,'relevant_to_exact_question':True} for i in range(2)],'observation_quote_ids':[blue],'mechanism_quote_ids':[blue],'alternative_quote_ids':[red],'condition_quote_ids':[condition],'sufficient_for_exact_question':True},{}
    monkeypatch.setattr(storyboard,'ask',ask)
    accepted,plan=evidence.plan_sources('Why does the fictional gate open?',records,'synthetic')
    assert accepted and len(calls)==2 and plan['source_records_referenced']==2
    assert {'mechanism','alternative','condition'}.issubset({item['role'] for item in plan['selected_original_paths']})
    for item in plan['selected_original_paths']:
        for q in item['evidence']:assert q['quote'] in records[q['source_index']]['text']


@pytest.mark.parametrize('paths',[[],[{'role':'observation','quote_ids':['S0Q0']},{'role':'mechanism','quote_ids':['S0Q0']}],[{'role':'mechanism','quote_ids':['invented']} ]])
def test_extractive_plan_rejects_empty_single_source_or_invented_coverage(monkeypatch,paths):
    monkeypatch.setattr(storyboard,'ask',lambda *args,**kwargs:({'scope_paths':paths,'sufficient_for_exact_question':True},{}))
    assert not evidence.plan_sources('Synthetic?',sources(),'synthetic')[0]


def test_source_plan_failure_never_calls_answer_writer(monkeypatch):
    from curiosity import autonomy
    monkeypatch.setattr(autonomy,'questions',lambda *args:([{'question':'Synthetic?','search_terms':'synthetic'}],{}))
    monkeypatch.setattr(autonomy,'research',lambda *args:(sources(),{}))
    monkeypatch.setattr(evidence,'plan_sources',lambda *args:(False,{'selected_original_paths':[],'accepted':False}))
    def forbidden(*args):raise AssertionError('Answer writer ran before accepted source plan')
    monkeypatch.setattr(evidence,'screen',forbidden)
    with pytest.raises(autonomy.ResearchUnavailable):autonomy.select_and_research('synthetic',[])


def test_source_scope_plan_executes_before_answer_and_preserves_original_paths(monkeypatch):
    from curiosity import autonomy
    events=[];original=sources();saved=deepcopy(original)
    paths=[{'role':'mechanism','evidence':[{'quote_id':'S0Q0','quote':original[0]['text'],'source_index':0}]},{'role':'alternative','evidence':[{'quote_id':'S1Q0','quote':original[1]['text'],'source_index':1}]}]
    monkeypatch.setattr(autonomy,'questions',lambda *args:([{'question':'Synthetic?','search_terms':'synthetic'}],{}))
    monkeypatch.setattr(autonomy,'research',lambda *args:(original,{}))
    def plan(*args):events.append('plan');return True,{'selected_original_paths':deepcopy(paths),'accepted':True}
    def screen(question,records,*args):
        events.append('answer')
        assert events==['plan','answer']
        assert records[0]['source_scope_plan']==paths
        assert all('source_scope_plan' not in record for record in records[1:])
        return True,{'approved_source_indices':[0,1],'accepted':True}
    monkeypatch.setattr(evidence,'plan_sources',plan);monkeypatch.setattr(evidence,'screen',screen)
    autonomy.select_and_research('synthetic',[])
    assert original==saved and events==['plan','answer']


def test_named_plan_slots_and_source_decisions_are_required():
    entries=evidence.catalog(sources());first=next(k for k in entries if k.startswith('S0'));second=next(k for k in entries if k.startswith('S1'))
    plan={'source_decisions':[{'source_index':i,'relevant_to_exact_question':True} for i in range(2)],'observation_quote_ids':[first],'mechanism_quote_ids':[second],'condition_quote_ids':[],'alternative_quote_ids':[],'sufficient_for_exact_question':True}
    assert evidence.validate_source_plan(plan,entries,2)[0]
    for field in ['observation_quote_ids','mechanism_quote_ids']:
        bad=deepcopy(plan);bad[field]=[];assert not evidence.validate_source_plan(bad,entries,2)[0]
    bad=deepcopy(plan);bad['source_decisions'][1]['relevant_to_exact_question']=False
    assert not evidence.validate_source_plan(bad,entries,2)[0]
    bad=deepcopy(plan);del bad['alternative_quote_ids'];assert not evidence.validate_source_plan(bad,entries,2)[0]


def test_structurally_valid_plan_still_fails_exact_question_or_alternative_audit(monkeypatch):
    calls=[]
    def ask(model,system,prompt,shape,*args,**kwargs):
        calls.append(shape)
        if 'exact_question_supported' in shape['properties']:return {'exact_question_supported':True,'material_paths_covered':False,'unrelated_paths_excluded':True,'missing_or_unrelated_quote_ids':['S1Q0']},{}
        return {'source_decisions':[{'source_index':i,'relevant_to_exact_question':True} for i in range(2)],'observation_quote_ids':['S0Q0'],'mechanism_quote_ids':['S1Q0'],'condition_quote_ids':[],'alternative_quote_ids':[],'sufficient_for_exact_question':True},{}
    monkeypatch.setattr(storyboard,'ask',ask)
    accepted,report=evidence.plan_sources('Synthetic?',sources(),'synthetic')
    assert not accepted and len(calls)==2 and not report['pre_answer_plan_audit']['accepted']
