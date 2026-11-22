from copy import deepcopy
from types import SimpleNamespace
import io
import json
import pytest
from curiosity import evidence,remote_ai,storyboard


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
    lines=schema['properties']['lines'];assert lines['minItems']==lines['maxItems']==13
    item=lines['items']['properties']['evidence']['items']
    assert list(item['properties'])==['quote_id'] and item['properties']['quote_id']['enum']==list(entries)


def test_relevance_requires_true_boolean_and_observation_mechanism_two_sources(monkeypatch):
    mode=['valid']
    def ask(model,system,prompt,schema,endpoint,seed,effort):
        assert effort=='low'
        ids=list(prompt['sentence_catalog']);first=next(k for k in ids if k.startswith('S0'));second=next(k for k in ids if k.startswith('S1'))
        return {'supported':True if mode[0]!='string_false' else 'false','observable_quote_ids':[first],'mechanism_quote_ids':[second if mode[0]!='one_source' else first],'issues':[]},{'usage':{'cost':'0'}}
    monkeypatch.setattr(storyboard,'ask',ask)
    assert evidence.screen('Synthetic observation?',sources(),'synthetic')[0]
    mode[0]='one_source';assert not evidence.screen('Synthetic observation?',sources(),'synthetic')[0]
    mode[0]='string_false';assert not evidence.screen('Synthetic observation?',sources(),'synthetic')[0]


def test_relevance_rejection_moves_only_to_remaining_model_proposed_candidates(monkeypatch):
    from curiosity import autonomy
    candidates=[{'question':f'Why does synthetic fixture {i} move?','search_terms':'synthetic movement'} for i in range(3)]
    monkeypatch.setattr(autonomy,'questions',lambda *a,**k:(candidates,{}))
    calls=[]
    monkeypatch.setattr(autonomy,'research',lambda *a:(sources(),{'not_a_truth_guarantee':True}))
    def screen(question,*args):
        calls.append(question);return len(calls)==2,{'accepted':len(calls)==2}
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
