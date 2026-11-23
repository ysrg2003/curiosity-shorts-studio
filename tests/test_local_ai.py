import io
import json
import pytest
from curiosity import local_ai,storyboard,remote_ai


def test_local_preflight_verifies_manifest_and_explicit_non_thinking_metadata(monkeypatch):
    digest=[local_ai.MANIFEST];values=[[False]];requests=[]
    def read(request,**kwargs):
        requests.append(request)
        data={'models':[{'name':local_ai.MODEL,'digest':digest[0]}]} if isinstance(request,str) else {'thinking':{'values':values[0]},'capabilities':['completion']}
        return io.StringIO(json.dumps(data))
    monkeypatch.setattr(local_ai,'urlopen',read)
    monkeypatch.setattr(local_ai,'probe',lambda:{'accepted':True})
    assert local_ai.verify()['reasoning_off_probe_passed'] and len(requests)==2
    digest[0]='changed-synthetic-manifest'
    with pytest.raises(ValueError,match='manifest'):local_ai.verify()
    digest[0]=local_ai.MANIFEST;values[0]=[True]
    with pytest.raises(ValueError,match='non-thinking-only'):local_ai.verify()
    values[0]=None
    with pytest.raises(ValueError,match='non-thinking-only'):local_ai.verify()


def test_local_json_rejects_thinking_and_retries_only_complete_schema_valid_output(monkeypatch):
    monkeypatch.setenv('CURIOSITY_LLM_BACKEND','ollama');result=[{'response':'{"answer":true}','thinking':'synthetic disallowed private reasoning'}]
    monkeypatch.setattr(storyboard,'urlopen',lambda *a,**k:io.StringIO(json.dumps(result[0])))
    schema={'type':'object','properties':{'answer':{'type':'boolean'}},'required':['answer']}
    with pytest.raises(remote_ai.ModelOutputInvalid) as failure:storyboard.ask(local_ai.MODEL,'synthetic',{},schema)
    assert 'synthetic disallowed' not in str(failure.value) and failure.value.metadata['validation']=='unexpected_thinking_output'
    result[0]={'response':'{"answer":'}
    with pytest.raises(remote_ai.ModelOutputInvalid):storyboard.ask(local_ai.MODEL,'synthetic',{},schema)
    result[0]={'response':'{"answer":true}'}
    assert storyboard.ask(local_ai.MODEL,'synthetic',{},schema)[0]=={'answer':True}


def test_default_config_and_workflow_pull_the_pinned_local_model():
    from curiosity.spec import ROOT
    assert json.loads((ROOT/'studio.json').read_text())['draft_model']==local_ai.MODEL
    workflow=(ROOT/'.github/workflows/generate.yml').read_text()
    assert 'ollama pull '+local_ai.MODEL in workflow and 'python -m curiosity.local_ai' in workflow


def test_only_pinned_manifest_and_a_live_probe_can_cover_legacy_metadata_absence(monkeypatch):
    shown=[{'capabilities':['completion','thinking']}];digest=[local_ai.MANIFEST];accepted=[True];calls=[]
    def read(request,**kwargs):
        data={'models':[{'name':local_ai.MODEL,'digest':digest[0]}]} if isinstance(request,str) else shown[0]
        return io.StringIO(json.dumps(data))
    def probe():calls.append(True);return {'accepted':accepted[0]}
    monkeypatch.setattr(local_ai,'urlopen',read);monkeypatch.setattr(local_ai,'probe',probe)
    assert local_ai.verify()['reasoning_off_probe_passed'] and len(calls)==1
    accepted[0]=False
    with pytest.raises(ValueError,match='probe failed'):local_ai.verify()
    assert len(calls)==2
    shown[0]={}
    with pytest.raises(ValueError,match='capability'):local_ai.verify()
    shown[0]={'capabilities':['completion'],'thinking':{'values':[True]}}
    with pytest.raises(ValueError,match='metadata'):local_ai.verify()
    shown[0]={'capabilities':['completion']};digest[0]='different-instruct-tag-is-not-permission'
    with pytest.raises(ValueError,match='manifest'):local_ai.verify()
    assert len(calls)==2


def test_local_scene_adapter_also_rejects_unexpected_thinking(monkeypatch):
    import importlib.util
    from curiosity.spec import ROOT
    spec=importlib.util.spec_from_file_location('local_scene_model_test',ROOT/'experiments/upstream_pipeline.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    monkeypatch.setenv('CURIOSITY_LLM_BACKEND','ollama')
    monkeypatch.setattr(module,'urlopen',lambda *a,**k:io.StringIO(json.dumps({'thinking':'synthetic disallowed reasoning','response':'synthetic scene code'})))
    with pytest.raises(remote_ai.ModelOutputInvalid):module.LocalModel(local_ai.MODEL).generate('synthetic')


def test_metadata_inspection_emits_only_controlled_public_shape():
    raw={'capabilities':['completion','synthetic-secret-that-must-not-be-logged'], 'thinking':{'values':[False,'high','synthetic-private-value']},'template':'synthetic-private-template','extra':'synthetic-private-account-data'}
    result=local_ai.snapshot({'digest':local_ai.MANIFEST},raw)
    assert result['manifest_matches'] and result['known_capabilities']==['completion']
    assert result['known_thinking_values']==[False,'high'] and not result['inference_performed']
    assert 'synthetic-' not in json.dumps(result)


def test_metadata_workflow_has_no_inference_or_service_key():
    from curiosity.spec import ROOT
    text=(ROOT/'.github/workflows/check-local-model.yml').read_text()
    assert '--inspect-only' in text and 'contents: read' in text and 'persist-credentials: false' in text
    assert 'secrets.' not in text and 'curiosity.batch' not in text and 'schedule:' not in text


def test_response_probe_is_bounded_non_episode_content_and_rejects_thinking(monkeypatch):
    monkeypatch.setattr(local_ai,'read_metadata',lambda:({'digest':local_ai.MANIFEST},{'capabilities':['completion','thinking']}))
    response=[{'response':'{"ready":true}','done':True,'done_reason':'stop','eval_count':6}];calls=[]
    def read(request,**kwargs):
        payload=json.loads(request.data);calls.append(payload)
        assert payload['think'] is False and payload['options']['num_predict']==64 and kwargs['timeout']==120
        return io.StringIO(json.dumps(response[0]))
    monkeypatch.setattr(local_ai,'urlopen',read)
    assert local_ai.probe()['accepted'] and len(calls)==1
    response[0]['thinking']='synthetic content never retained'
    result=local_ai.probe();assert not result['accepted'] and 'synthetic content' not in json.dumps(result)
    response[0]={'response':'{"ready":','done':True}
    assert not local_ai.probe()['accepted']
    monkeypatch.setattr(local_ai,'read_metadata',lambda:({'digest':'changed'},{}))
    with pytest.raises(ValueError,match='manifest'):local_ai.probe()
    assert len(calls)==3


def test_response_probe_does_not_accept_truthy_non_booleans_or_length_finish(monkeypatch):
    monkeypatch.setattr(local_ai,'read_metadata',lambda:({'digest':local_ai.MANIFEST},{}))
    response=[{'response':'{"ready":1}','done':True,'done_reason':'stop'}]
    monkeypatch.setattr(local_ai,'urlopen',lambda *a,**k:io.StringIO(json.dumps(response[0])))
    assert not local_ai.probe()['accepted']
    response[0]={'response':'{"ready":true}','done':True,'done_reason':'length'}
    assert not local_ai.probe()['accepted']


def test_experimental_nine_is_explicit_and_does_not_change_generation_default():
    from curiosity.spec import ROOT
    assert local_ai.EXPERIMENTAL_MODEL=='qwen3.5:9b'
    assert len(local_ai.EXPERIMENTAL_MANIFEST)==64
    assert json.loads((ROOT/'studio.json').read_text())['draft_model']==local_ai.MODEL
    text=(ROOT/'.github/workflows/check-script.yml').read_text()
    assert 'default: false' in text and 'ollama pull qwen3.5:9b' in text
    assert 'python -m curiosity.local_ai --experimental-nine' in text
    assert 'python -m curiosity.script_preflight --experimental-nine' in text
    assert 'secrets.' not in text and 'schedule:' not in text
