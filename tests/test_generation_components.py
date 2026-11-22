from copy import deepcopy
from types import SimpleNamespace
import pytest
from curiosity.staging import stage_story
from curiosity.autonomy import duplicate,eligible_reference,publisher
from curiosity import remote_ai


def sample():
    return {'lines':[{'speaker':'PIP' if i%2==0 else 'RAY','beat':'dialogue' if i%2==0 else 'explain','text':f'Synthetic test narration number{i}.','diagram':['Step A','Step B'],'evidence':[{'source_index':0,'quote':'Synthetic evidence only.'}]} for i in range(13)]}


def test_staging_changes_only_camera_assignment():
    original=sample();saved=deepcopy(original);result,audit=stage_story(original)
    assert original==saved and audit['raw_explanation_beats']==6 and audit['staged_explanation_beats']==4
    for old,new in zip(original['lines'],result['lines']):
        assert {k:v for k,v in old.items() if k!='beat'}=={k:v for k,v in new.items() if k!='beat'}
    again,report=stage_story(result);assert again==result and not report['changed_line_indices']


def test_staging_does_not_invent_scientific_diagrams():
    original=sample()
    for line in original['lines']:line['diagram']=[]
    result,audit=stage_story(original)
    assert result==original and audit['staged_explanation_beats']==6


def test_publisher_groups_and_safe_reference_filter():
    assert publisher('https://physics.harvard.edu/example')=='harvard.edu'
    assert publisher('https://www.metoffice.gov.uk/example')=='metoffice.gov.uk'
    assert not eligible_reference('https://nasa.gov.example.invalid/path')
    assert not eligible_reference('http://example.edu/path')
    assert eligible_reference('https://science.nasa.gov/example')


def test_duplicate_questions():
    assert duplicate('Why does the sky look blue?', ['Why does the sky look blue?'])
    assert not duplicate('How do magnets attract iron?', ['Why is the sky blue?'])


def test_remote_missing_secret_stops_before_network(monkeypatch):
    monkeypatch.delenv('OPENROUTER_API_KEY',raising=False)
    monkeypatch.setattr(remote_ai,'check_free_catalog',lambda:pytest.fail('Network must not be called'))
    with pytest.raises(ValueError,match='Missing'):remote_ai.request('synthetic prompt','synthetic system')


def test_reuses_owner_adapter_with_only_explicit_free_model(monkeypatch):
    OpenAICompatibleAdapter=pytest.importorskip('ai_router.providers.openai_compatible').OpenAICompatibleAdapter
    monkeypatch.setenv('OPENROUTER_API_KEY','synthetic-unit-test-only')
    monkeypatch.setattr(remote_ai,'check_free_catalog',lambda:True)
    seen={}
    def call(self,**kwargs):seen.update(kwargs);return SimpleNamespace(payload={'answer':'test'},usage={'cost':0,'total_tokens':5})
    monkeypatch.setattr(OpenAICompatibleAdapter,'complete_json',call)
    output,stats=remote_ai.request('synthetic prompt','synthetic system',json_mode=True)
    assert output=={'answer':'test'} and seen['model']==remote_ai.MODEL
    assert not stats['paid_fallback_allowed'] and 'models' not in seen and 'tools' not in seen


def test_unexpected_cost_stops(monkeypatch):
    OpenAICompatibleAdapter=pytest.importorskip('ai_router.providers.openai_compatible').OpenAICompatibleAdapter
    monkeypatch.setenv('OPENROUTER_API_KEY','synthetic-unit-test-only')
    monkeypatch.setattr(remote_ai,'check_free_catalog',lambda:True)
    monkeypatch.setattr(OpenAICompatibleAdapter,'complete_json',lambda *a,**k:SimpleNamespace(payload={},usage={'cost':0.01}))
    with pytest.raises(RuntimeError,match='nonzero'):remote_ai.request('synthetic prompt','synthetic system',json_mode=True)


def test_real_owner_http_adapter_plaintext_and_json(monkeypatch):
    adapter=pytest.importorskip('ai_router.providers.openai_compatible')
    monkeypatch.setenv('OPENROUTER_API_KEY','synthetic-unit-test-only')
    monkeypatch.setattr(remote_ai,'check_free_catalog',lambda:True)
    calls=[]
    def post(url,**kwargs):
        calls.append((url,kwargs))
        text='{"answer":"test"}' if 'response_format' in kwargs['json'] else 'from manim import *\nclass MainScene(Scene): pass'
        return SimpleNamespace(status_code=200,json=lambda:{'choices':[{'message':{'content':text}}],'usage':{'cost':0,'total_tokens':12,'arbitrary':'must not enter logs'}})
    monkeypatch.setattr(adapter.requests,'post',post)
    text,stats=remote_ai.request('synthetic','synthetic')
    assert text.startswith('from manim') and 'arbitrary' not in stats['usage']
    obj,_=remote_ai.request('synthetic','synthetic',schema={'type':'object','properties':{'answer':{'type':'string'}},'required':['answer']})
    assert obj=={'answer':'test'}
    assert all(url=='https://openrouter.ai/api/v1/chat/completions' for url,_ in calls)
    assert all(kwargs['json']['model']==remote_ai.MODEL and 'tools' not in kwargs['json'] and 'models' not in kwargs['json'] for _,kwargs in calls)
    assert calls[1][1]['json']['response_format']['json_schema']['schema']['additionalProperties'] is False
    assert all(kwargs['json']['reasoning_effort']=='none' for _,kwargs in calls)


def test_real_child_never_inherits_model_or_repository_secrets(monkeypatch):
    import json,os,subprocess,sys
    from curiosity.process_safety import scrubbed_subprocesses
    monkeypatch.setenv('OPENROUTER_API_KEY','synthetic-not-a-real-key')
    monkeypatch.setenv('GITHUB_TOKEN','synthetic-not-a-real-token')
    monkeypatch.setenv('UNKNOWN_SENSITIVE_NAME','synthetic-private-value')
    with scrubbed_subprocesses():
        child=subprocess.run([sys.executable,'-c','import os,json;print(json.dumps(dict(os.environ)))'],capture_output=True,text=True,check=True)
    env=json.loads(child.stdout)
    assert 'OPENROUTER_API_KEY' not in env and 'GITHUB_TOKEN' not in env and 'UNKNOWN_SENSITIVE_NAME' not in env
    assert os.environ['OPENROUTER_API_KEY']=='synthetic-not-a-real-key' and env.get('PATH')


def test_isolated_generated_code_has_no_network_repository_or_credential_mounts(monkeypatch,tmp_path):
    import importlib.util,subprocess
    from curiosity.spec import ROOT
    spec=importlib.util.spec_from_file_location('benchmark_under_test',ROOT/'experiments/upstream_pipeline.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    code=tmp_path/'scene.py';code.write_text('# synthetic scene')
    seen=[]
    def run(command,**kwargs):seen.append(command);return SimpleNamespace(returncode=1,stdout='',stderr='synthetic rendering failure')
    monkeypatch.setattr(subprocess,'run',run)
    assert module.isolated_manim(code,tmp_path/'media')[0]==1
    command=seen[0]
    assert command[command.index('--network')+1]=='none'
    assert '--read-only' in command and '--cap-drop' in command and 'ALL' in command
    mounts=[command[i+1] for i,value in enumerate(command) if value=='--mount']
    assert len(mounts)==2 and all('.git' not in value and 'secrets' not in value for value in mounts)
    assert not any('TOKEN=' in value or 'API_KEY=' in value for value in command)


def test_prepared_motion_is_hash_bound_and_has_no_preset_fallback(tmp_path):
    import json
    from curiosity.generated_motion import prepared
    from curiosity.spec import digest
    folder=tmp_path/'generated';folder.mkdir();clip=folder/'beat-02.mp4';clip.write_bytes(b'synthetic media fixture')
    (tmp_path/'episode.json').write_text('{}');(tmp_path/'timeline.json').write_text('{}')
    (folder/'prepared.json').write_text(json.dumps({'episode_sha256':digest(tmp_path/'episode.json'),'timeline_sha256':digest(tmp_path/'timeline.json'),'clips':{'2':{'file':clip.name,'sha256':digest(clip)}}}))
    timeline={'lines':[{'idx':2,'beat':'explain'}]}
    assert prepared({},timeline,tmp_path)=={2:clip}
    clip.write_bytes(b'tampered synthetic media fixture')
    with pytest.raises(ValueError,match='changed'):prepared({},timeline,tmp_path)
    (folder/'prepared.json').unlink()
    with pytest.raises(FileNotFoundError):prepared({},timeline,tmp_path)


def test_automatic_batch_ignores_operator_topics_and_scrubs_both_workers(monkeypatch,tmp_path):
    import json,os,subprocess
    from curiosity import batch,autonomy,planner,generated_motion
    monkeypatch.setattr(remote_ai,'free_quota_status',lambda **kwargs:{'http_status':200,'request_budget':'sufficient_for_bounded_attempt','daily_counter':'has_remaining','inference_performed':False})
    (tmp_path/'episodes').mkdir();(tmp_path/'studio.json').write_text(json.dumps({'video_count':1,'max_videos_per_run':20,'draft_model':'synthetic'}))
    monkeypatch.setattr(batch,'ROOT',tmp_path)
    for key,value in {'MODE':'automatic','VIDEO_COUNT':'1','TOPIC':'must not reach research','SOURCE_URLS':'must not reach research','OPENROUTER_API_KEY':'synthetic-private-value'}.items():monkeypatch.setenv(key,value)
    monkeypatch.delenv('GITHUB_STEP_SUMMARY',raising=False)
    sources=[{'url':'https://example.edu/a','text':'synthetic source'}]
    monkeypatch.setattr(autonomy,'select_and_research',lambda *a,**k:('Autonomous synthetic question?',sources,{'operator_topic_or_source_input':False}))
    seen={}
    def draft(question,path,urls,model,**kwargs):
        seen.update(question=question,urls=urls,records=kwargs['source_records'])
        obj={'id':'synthetic-episode','title':question};path.write_text(json.dumps(obj));return obj
    monkeypatch.setattr(planner,'draft',draft)
    calls=[]
    def worker(command,**kwargs):
        calls.append((command,kwargs))
        bundle=tmp_path/'output/synthetic-episode';bundle.mkdir(parents=True,exist_ok=True)
        (bundle/'timeline.json').write_text(json.dumps({'lines':[],'total':1}))
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(subprocess,'run',worker)
    monkeypatch.setattr(generated_motion,'prepare',lambda *a,**k:{})
    batch.main()
    assert seen=={'question':'Autonomous synthetic question?','urls':None,'records':sources}
    assert [command[3] for command,_ in calls]==['audio','video']
    assert all('OPENROUTER_API_KEY' not in kwargs['env'] for _,kwargs in calls)
    assert json.loads((tmp_path/'output/generation.json').read_text())['operator_topic_or_source_input'] is False


def test_provider_errors_keep_numeric_status_but_never_raw_messages(monkeypatch):
    adapter=pytest.importorskip('ai_router.providers.openai_compatible')
    from ai_router.providers.base import ProviderError
    monkeypatch.setenv('OPENROUTER_API_KEY','synthetic-unit-test-only')
    monkeypatch.setattr(remote_ai,'check_free_catalog',lambda:True)
    def fail(*a,**k):raise ProviderError('synthetic-sensitive-response-must-not-leak',error_class='rate_limit',status_code=429)
    monkeypatch.setattr(adapter.OpenAICompatibleAdapter,'complete_json',fail)
    with pytest.raises(RuntimeError) as found:remote_ai.request('synthetic','synthetic')
    assert '429' in str(found.value) and 'rate_limit' in str(found.value)
    assert 'synthetic-sensitive' not in str(found.value) and 'synthetic-unit-test-only' not in str(found.value)


def test_generic_generated_scene_contract_rejects_unsupplied_assets():
    import importlib.util
    from curiosity.spec import ROOT
    spec=importlib.util.spec_from_file_location('asset_contract_test',ROOT/'experiments/upstream_pipeline.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    assert module.extra_lint('from manim import *\nx=SVGMobject("synthetic-fixture.svg")')
    assert not module.extra_lint('from manim import *\nx=Circle(radius=0.7)')
    assert module.extra_lint('class MainScene(:')


def test_complete_json_extraction_does_not_repair_truncation_or_accept_inner_objects():
    assert remote_ai.object_from_text('Preface\n```json\n{"ok":true}\n```')=={'ok':True}
    with pytest.raises(ValueError):remote_ai.object_from_text('{"lines":[{"text":"unfinished"}')

def test_local_schema_rejects_string_boolean_instead_of_trusting_truthiness(monkeypatch):
    adapter=pytest.importorskip('ai_router.providers.openai_compatible')
    monkeypatch.setenv('OPENROUTER_API_KEY','synthetic-unit-test-only')
    monkeypatch.setattr(remote_ai,'check_free_catalog',lambda:True)
    monkeypatch.setattr(adapter.OpenAICompatibleAdapter,'complete_json',lambda *a,**k:SimpleNamespace(payload={'supported':'false'},usage={'cost':0}))
    with pytest.raises(remote_ai.ModelOutputInvalid):remote_ai.request('synthetic','synthetic',schema={'type':'object','properties':{'supported':{'type':'boolean'}},'required':['supported']})

def test_http_shape_reports_truncation_without_content_or_credentials(monkeypatch):
    adapter=pytest.importorskip('ai_router.providers.openai_compatible')
    monkeypatch.setenv('OPENROUTER_API_KEY','synthetic-unit-test-only')
    monkeypatch.setattr(remote_ai,'check_free_catalog',lambda:True)
    response=SimpleNamespace(status_code=200,json=lambda:{'choices':[{'finish_reason':'length','message':{'content':'{"private_fragment":"synthetic'}}],'usage':{'cost':0,'completion_tokens':12000}})
    monkeypatch.setattr(adapter.requests,'post',lambda *a,**k:response)
    with pytest.raises(remote_ai.ModelOutputInvalid) as found:remote_ai.request('synthetic','synthetic',json_mode=True)
    assert found.value.metadata['finish_reason']=='length' and found.value.metadata['http_status']==200
    assert 'private_fragment' not in str(found.value) and 'synthetic-unit-test-only' not in str(found.value)

def test_cost_checked_even_if_model_json_is_incomplete(monkeypatch):
    adapter=pytest.importorskip('ai_router.providers.openai_compatible')
    monkeypatch.setenv('OPENROUTER_API_KEY','synthetic-unit-test-only')
    monkeypatch.setattr(remote_ai,'check_free_catalog',lambda:True)
    response=SimpleNamespace(status_code=200,json=lambda:{'choices':[{'message':{'content':'incomplete synthetic output'}}],'usage':{'cost':0.01}})
    monkeypatch.setattr(adapter.requests,'post',lambda *a,**k:response)
    with pytest.raises(remote_ai.UnexpectedModelCost,match='nonzero'):remote_ai.request('synthetic','synthetic',json_mode=True)


def test_http_errors_retain_only_safe_shape_and_do_not_retry(monkeypatch):
    adapter=pytest.importorskip('ai_router.providers.openai_compatible')
    monkeypatch.setenv('OPENROUTER_API_KEY','synthetic-unit-test-only')
    monkeypatch.setattr(remote_ai,'check_free_catalog',lambda:True)
    calls=[]
    def post(*a,**k):
        calls.append(True)
        return SimpleNamespace(status_code=429,json=lambda:{'error':{'message':'synthetic private text must not be retained'}})
    monkeypatch.setattr(adapter.requests,'post',post)
    with pytest.raises(remote_ai.ModelRequestFailed) as found:remote_ai.request('synthetic','synthetic',json_mode=True)
    assert found.value.metadata['http_status']==429 and len(calls)==1
    assert 'private text' not in str(found.value) and 'synthetic-unit-test-only' not in str(found.value)

def test_draft_only_retries_output_invalid_not_account_errors(monkeypatch,tmp_path):
    from curiosity import planner,storyboard
    import json
    sources=[{'url':'https://example.edu/a','text':'This synthetic source sentence contains enough words for a bounded evidence test.'},{'url':'https://example.org/b','text':'Another synthetic source sentence contains enough words for a bounded evidence test.'}]
    monkeypatch.setattr(storyboard,'source_pack',lambda topic,sources:sources)
    calls=[]
    def invalid(*a,**k):
        calls.append(True);raise remote_ai.ModelOutputInvalid({'finish_reason':'length'})
    monkeypatch.setattr(storyboard,'ask',invalid)
    with pytest.raises(ValueError,match='after 3 attempts'):planner.draft('Synthetic?',tmp_path/'test.json',source_records=sources)
    audit=json.loads((tmp_path/'test.audit.json').read_text())
    assert len(calls)==3 and len(audit['attempts'])==3 and not audit['accepted']
    calls.clear()
    def account_error(*a,**k):
        calls.append(True);raise remote_ai.ModelRequestFailed({'http_status':401,'category':'auth','reason':'authentication_rejected'})
    monkeypatch.setattr(storyboard,'ask',account_error)
    with pytest.raises(remote_ai.ModelRequestFailed):planner.draft('Synthetic?',tmp_path/'second.json',source_records=sources)
    assert len(calls)==1


def test_only_public_catalog_model_id_and_numeric_reasoning_count_enter_diagnostics(monkeypatch):
    adapter=pytest.importorskip('ai_router.providers.openai_compatible')
    monkeypatch.setenv('OPENROUTER_API_KEY','synthetic-unit-test-only')
    monkeypatch.setattr(remote_ai,'check_free_catalog',lambda:{'synthetic/public-free'})
    model=['synthetic/public-free']
    monkeypatch.setattr(adapter.requests,'post',lambda *a,**k:SimpleNamespace(status_code=200,json=lambda:{'model':model[0],'choices':[{'finish_reason':'stop','message':{'content':'{"ok":true}'}}],'usage':{'cost':0,'completion_tokens_details':{'reasoning_tokens':123,'arbitrary':'must not be retained'}}}))
    _,stats=remote_ai.request('synthetic','synthetic',json_mode=True)
    assert stats['response_shape']['resolved_public_model']=='synthetic/public-free' and stats['usage']['reasoning_tokens']==123
    assert 'arbitrary' not in str(stats)
    model[0]='synthetic private value'
    _,stats=remote_ai.request('synthetic','synthetic',json_mode=True)
    assert stats['response_shape']['resolved_public_model']=='unlisted' and 'private value' not in str(stats)


def test_live_catalog_guard_requires_zero_price_and_explicit_reasoning_off_support(monkeypatch):
    import io,json
    model={'id':remote_ai.MODEL,'pricing':{'prompt':'0','completion':'0'},'supported_parameters':['response_format','structured_outputs','reasoning_effort'],'reasoning':{'mandatory':False,'supported_efforts':['none','low']}}
    monkeypatch.setattr(remote_ai,'urlopen',lambda *a,**k:io.StringIO(json.dumps({'data':[model]})))
    assert remote_ai.MODEL in remote_ai.check_free_catalog()
    model['pricing']['completion']='0.000001'
    with pytest.raises(ValueError,match='pricing'):remote_ai.check_free_catalog()
    model['pricing']['completion']='0';model['reasoning']['mandatory']=True
    with pytest.raises(ValueError,match='reasoning-off'):remote_ai.check_free_catalog()
    model['reasoning']['mandatory']=False;model['supported_parameters']=[]
    with pytest.raises(ValueError,match='structured output'):remote_ai.check_free_catalog()


def test_quota_read_never_infers_or_exposes_key_labels_counts_or_account_details(monkeypatch):
    import requests
    monkeypatch.setenv('OPENROUTER_API_KEY','synthetic-private-secret')
    monkeypatch.setattr(requests,'post',lambda *a,**k:pytest.fail('Quota check must never infer'))
    counter={'remaining':0}
    calls=[]
    def get(url,**kwargs):
        calls.append((url,kwargs))
        return SimpleNamespace(status_code=200,json=lambda:{'data':{'label':'synthetic-private-label','organization_id':'synthetic-private-org','free_model_daily_requests':counter,'usage_daily':91.23}})
    monkeypatch.setattr(requests,'get',get)
    result=remote_ai.free_quota_status()
    assert result=={'http_status':200,'daily_counter':'at_limit','request_budget':'below_conservative_reserve','inference_performed':False}
    counter['remaining']=12
    assert remote_ai.free_quota_status()['daily_counter']=='has_remaining'
    counter['remaining']=True
    assert remote_ai.free_quota_status()['daily_counter']=='unknown'
    assert all(url=='https://openrouter.ai/api/v1/key' and kwargs['allow_redirects'] is False for url,kwargs in calls)
    assert not any(value in str(result) for value in ['synthetic-private', '91.23', 'remaining'])

def test_quota_read_failure_is_sanitized_and_never_retried(monkeypatch):
    import requests
    monkeypatch.setenv('OPENROUTER_API_KEY','synthetic-private-secret')
    calls=[]
    def fail(*a,**k):
        calls.append(True);raise RuntimeError('synthetic-private-sensitive-error')
    monkeypatch.setattr(requests,'get',fail)
    assert remote_ai.free_quota_status()=={'http_status':'unavailable','daily_counter':'unknown','request_budget':'unknown','inference_performed':False}
    assert len(calls)==1


def test_safe_rate_limit_metadata_never_retains_raw_header_or_provider_text(monkeypatch):
    adapter=pytest.importorskip('ai_router.providers.openai_compatible')
    monkeypatch.setenv('OPENROUTER_API_KEY','synthetic-private-secret')
    monkeypatch.setattr(remote_ai,'check_free_catalog',lambda:{remote_ai.MODEL})
    headers={'Retry-After':'60','X-RateLimit-Reset':'1795430000000','X-Private':'synthetic-private-text'}
    monkeypatch.setattr(adapter.requests,'post',lambda *a,**k:SimpleNamespace(status_code=429,headers=headers,json=lambda:{'error':{'message':'synthetic-private-text','metadata':{'provider_code':'synthetic-private-text'}}}))
    with pytest.raises(remote_ai.ModelRequestFailed) as found:remote_ai.request('synthetic','synthetic')
    assert found.value.metadata['retry_after_seconds']==60 and found.value.metadata['rate_reset_unix_ms']==1795430000000 and found.value.metadata['provider_code_present']
    assert 'synthetic-private' not in str(found.value.metadata)
    headers['Retry-After']='synthetic-private-text'
    with pytest.raises(remote_ai.ModelRequestFailed) as found:remote_ai.request('synthetic','synthetic')
    assert 'retry_after_seconds' not in found.value.metadata

def test_quota_reserve_covers_connection_and_bounded_count1_calls(monkeypatch):
    import requests
    monkeypatch.setenv('OPENROUTER_API_KEY','synthetic-private-secret')
    remaining=[27]
    monkeypatch.setattr(requests,'get',lambda *a,**k:SimpleNamespace(status_code=200,json=lambda:{'data':{'free_model_daily_requests':{'remaining':remaining[0]}}}))
    assert remote_ai.free_quota_status()['request_budget']=='below_conservative_reserve'
    remaining[0]=28
    assert remote_ai.free_quota_status()['request_budget']=='sufficient_for_bounded_attempt'


def test_topic_proposal_bounds_reject_and_audit_without_inventing_candidates(monkeypatch):
    from curiosity import autonomy
    calls=[]
    def ask(*args):
        calls.append(args);return {'candidates':[{'question':'','search_terms':''} for _ in range(3)]},{'usage':{'cost':'0'}}
    monkeypatch.setattr(autonomy,'ask',ask)
    with pytest.raises(autonomy.ResearchUnavailable) as found:autonomy.questions('synthetic',[])
    assert len(calls)==2 and len(found.value.diagnostics['proposal_attempts'])==2
    assert not found.value.diagnostics['operator_topic_or_source_input']
    assert calls[0][3]['properties']['candidates']['items']['properties']['question']['minLength']==10
    assert all(not c['accepted'] for c in found.value.diagnostics['proposal_attempts'][0]['candidate_checks'])

def test_topic_proposal_retry_recovers_only_from_model_supplied_valid_candidates(monkeypatch):
    from curiosity import autonomy
    calls=[]
    candidates=[{'question':f'What moves synthetic fixture {i}?','search_terms':'synthetic vector motion'} for i in range(3)]
    def ask(*args):
        calls.append(True)
        if len(calls)==1:raise remote_ai.ModelOutputInvalid({'finish_reason':'length'})
        return {'candidates':candidates},{'usage':{'cost':'0'}}
    monkeypatch.setattr(autonomy,'ask',ask)
    result,stats=autonomy.questions('synthetic',[])
    assert result==candidates and len(calls)==2 and len(stats['proposal_attempts'])==2

def test_topic_proposals_never_retry_account_errors(monkeypatch):
    from curiosity import autonomy
    calls=[]
    def ask(*a,**k):
        calls.append(True);raise remote_ai.ModelRequestFailed({'http_status':429,'category':'quota','reason':'rate_or_quota_limit','retry_after_seconds':60})
    monkeypatch.setattr(autonomy,'ask',ask)
    with pytest.raises(remote_ai.ModelRequestFailed):autonomy.questions('synthetic',[])
    assert len(calls)==1

def test_batch_retains_safe_early_model_failure_metadata(monkeypatch,tmp_path):
    from curiosity import batch
    import json
    monkeypatch.setattr(batch,'ROOT',tmp_path)
    def fail():raise remote_ai.ModelRequestFailed({'http_status':429,'category':'quota','reason':'rate_or_quota_limit','retry_after_seconds':60})
    monkeypatch.setattr(batch,'generate',fail)
    with pytest.raises(remote_ai.ModelRequestFailed):batch.main()
    record=json.loads((tmp_path/'drafts/model-failure.json').read_text())
    assert record['response_shape']['retry_after_seconds']==60 and not record['complete_video']


def test_batch_checks_configured_request_reserve_before_any_topic_inference(monkeypatch,tmp_path):
    from curiosity import batch,autonomy
    import json
    monkeypatch.setattr(batch,'ROOT',tmp_path)
    (tmp_path/'studio.json').write_text(json.dumps({'video_count':1,'max_videos_per_run':20,'draft_model':'synthetic'}))
    for key,value in {'MODE':'automatic','VIDEO_COUNT':'2','CURIOSITY_LLM_BACKEND':'openrouter-free'}.items():monkeypatch.setenv(key,value)
    seen=[]
    def budget(minimum_requests):
        seen.append(minimum_requests);return {'http_status':200,'daily_counter':'has_remaining','request_budget':'below_conservative_reserve','inference_performed':False}
    monkeypatch.setattr(remote_ai,'free_quota_status',budget)
    monkeypatch.setattr(autonomy,'select_and_research',lambda *a,**k:pytest.fail('No inference without a verified request reserve'))
    with pytest.raises(RuntimeError,match='No inference attempted'):batch.main()
    assert seen==[52]
    audit=json.loads((tmp_path/'drafts/quota-budget.json').read_text())
    assert audit['video_count']==2 and not audit['inference_performed']
