import io,json
import pytest
from curiosity import router_ai,storyboard,remote_ai


def test_router_requires_current_zero_pricing_and_capabilities(monkeypatch):
    entry={'id':router_ai.MODEL,'pricing':{'prompt':'0','completion':'0'},'supported_parameters':['response_format','reasoning_effort','structured_outputs']}
    monkeypatch.setattr(router_ai,'urlopen',lambda *a,**k:io.StringIO(json.dumps({'data':[entry]})))
    assert router_ai.verify_free_model()['no_paid_fallback']
    entry['pricing']['completion']='0.001'
    with pytest.raises(ValueError,match='zero'):router_ai.verify_free_model()


def test_prepared_backend_uses_existing_router_entry_and_preserves_schema(monkeypatch):
    monkeypatch.setenv('CURIOSITY_LLM_BACKEND','prepared-router')
    seen=[]
    def request(system,prompt,schema,effort):
        seen.append((schema,effort));return {'ok':True},{'synthetic':True}
    monkeypatch.setattr(router_ai,'request',request)
    schema={'type':'object','properties':{'ok':{'type':'boolean'}},'required':['ok']}
    assert storyboard.ask('ignored-local-model','fictional',{},schema,effort='low')[0]=={'ok':True}
    assert seen==[(schema,'low')]


def test_request_budget_blocks_before_any_key_or_network_access(monkeypatch):
    monkeypatch.setattr(router_ai,'_REQUESTS',router_ai.MAX_REQUESTS)
    with pytest.raises(ValueError,match='budget'):router_ai.request('fictional',{}, {})


def test_generated_motion_uses_prepared_router_not_local_model(monkeypatch):
    import importlib.util
    from pathlib import Path
    hook=importlib.util.spec_from_file_location('router_motion_probe',Path(__file__).parents[1]/'experiments/upstream_pipeline.py')
    adapter=importlib.util.module_from_spec(hook);hook.loader.exec_module(adapter)
    monkeypatch.setenv('CURIOSITY_LLM_BACKEND','prepared-router')
    seen=[]
    def request(system,prompt,schema):
        seen.append(schema)
        return {'response':'class MainScene: pass'}, {'backend':'prepared-ai-router','actual_model':router_ai.MODEL}
    monkeypatch.setattr(router_ai,'request',request)
    llm=adapter.LocalModel('must-not-call-local')
    assert llm.generate('Return fictional vector scene')=='class MainScene: pass'
    assert seen[0]['required']==['response']
    assert llm.calls[0]['actual_model']==router_ai.MODEL


def test_transport_failure_is_not_retried_as_schema_repair(monkeypatch):
    from curiosity import autonomy
    calls=[]
    def ask(*args,**kwargs):
        calls.append(1)
        raise remote_ai.ModelOutputInvalid({'transport_failure':True,'provider_failures':[{'http_status':429,'category':'rate_limit'}]})
    monkeypatch.setattr(autonomy,'ask',ask)
    with pytest.raises(autonomy.ResearchUnavailable) as e:autonomy.questions('fictional',[])
    assert len(calls)==1
    assert e.value.diagnostics['proposal_attempts'][0]['rejected']=='model_transport_unavailable'
