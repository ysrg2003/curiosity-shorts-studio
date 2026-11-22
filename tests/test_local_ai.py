import io
import json
import pytest
from curiosity import local_ai,storyboard,remote_ai


def test_local_preflight_verifies_manifest_and_explicit_non_thinking_metadata(monkeypatch):
    digest=[local_ai.MANIFEST];values=[[False]];requests=[]
    def read(request,**kwargs):
        requests.append(request)
        data={'models':[{'name':local_ai.MODEL,'digest':digest[0]}]} if isinstance(request,str) else {'thinking':{'values':values[0]}}
        return io.StringIO(json.dumps(data))
    monkeypatch.setattr(local_ai,'urlopen',read)
    assert local_ai.verify()['non_thinking_only'] and len(requests)==2
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
