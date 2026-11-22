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


def test_reuses_owner_adapter_with_only_free_router(monkeypatch):
    OpenAICompatibleAdapter=pytest.importorskip('ai_router.providers.openai_compatible').OpenAICompatibleAdapter
    monkeypatch.setenv('OPENROUTER_API_KEY','synthetic-unit-test-only')
    monkeypatch.setattr(remote_ai,'check_free_catalog',lambda:True)
    seen={}
    def call(self,**kwargs):seen.update(kwargs);return SimpleNamespace(payload={'answer':'test'},usage={'cost':0,'total_tokens':5})
    monkeypatch.setattr(OpenAICompatibleAdapter,'complete_json',call)
    output,stats=remote_ai.request('synthetic prompt','synthetic system',json_mode=True)
    assert output=={'answer':'test'} and seen['model']=='openrouter/free'
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
    assert all(kwargs['json']['model']=='openrouter/free' and 'tools' not in kwargs['json'] and 'models' not in kwargs['json'] for _,kwargs in calls)
    assert calls[1][1]['json']['response_format']['json_schema']['schema']['additionalProperties'] is False


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
