import json
import pytest
from curiosity import resume_research as rr


def dossier(tmp_path):
    data={'schema_version':1,'operator_topic_or_source_input':False,'question':'A synthetic unchanged question?','packed_original_sources':[{'url':'https://one.edu/x','text':'Synthetic original one.'},{'url':'https://two.gov/x','text':'Synthetic original two.'}]}
    from curiosity.provenance import begin,bind
    import os
    from unittest.mock import patch
    with patch.dict(os.environ,{'GITHUB_RUN_ID':'12345'}):begin(tmp_path)
    data['provenance']=bind(tmp_path,data['question'],data['packed_original_sources'])
    (tmp_path/'runtime.json').write_text((tmp_path/'drafts/runtime.json').read_text())
    p=tmp_path/'original.json';p.write_text(json.dumps(data));return p,data


def test_resume_rejects_operator_input_before_models(monkeypatch,tmp_path):
    p,d=dossier(tmp_path);d['operator_topic_or_source_input']=True;p.write_text(json.dumps(d))
    monkeypatch.setattr(rr,'plan_sources',lambda *a:pytest.fail('Must not invoke a model'))
    with pytest.raises(ValueError,match='autonomous'):rr.resume(p,'test')


def test_resume_rechecks_both_source_gates_and_preserves_originals(monkeypatch,tmp_path):
    p,d=dossier(tmp_path);monkeypatch.setattr(rr,'ROOT',tmp_path);calls=[]
    def plan(q,s,m):
        assert q==d['question'] and s==d['packed_original_sources'];calls.append('plan');return True,{'selected_original_paths':[]}
    def screen(q,s,m):calls.append('screen');return True,{'approved_source_indices':[0,1]}
    def draft(q,target,**kw):
        calls.append('draft');assert kw['source_records']==d['packed_original_sources']
    monkeypatch.setattr(rr,'plan_sources',plan);monkeypatch.setattr(rr,'screen',screen);monkeypatch.setattr(rr,'draft',draft)
    rr.resume(p,'test');assert calls==['plan','screen','draft'];assert json.loads(p.read_text())==d


def test_resume_failed_plan_never_screens_or_drafts(monkeypatch,tmp_path):
    p,d=dossier(tmp_path);monkeypatch.setattr(rr,'ROOT',tmp_path)
    monkeypatch.setattr(rr,'plan_sources',lambda *a:(False,{}))
    monkeypatch.setattr(rr,'screen',lambda *a:pytest.fail('Gate bypass'))
    monkeypatch.setattr(rr,'draft',lambda *a:pytest.fail('Gate bypass'))
    with pytest.raises(ValueError,match='planning'):rr.resume(p,'test')


def test_invalidated_trial_cannot_resume_even_with_plausible_runtime(monkeypatch,tmp_path):
    from curiosity.provenance import validate
    p,d=dossier(tmp_path);d['provenance']['github_run_id']='45111351142'
    with pytest.raises(ValueError,match='Invalidated'):validate(d,d['provenance'])


def test_dossier_mutation_cannot_resume(monkeypatch,tmp_path):
    from curiosity.provenance import validate
    p,d=dossier(tmp_path);d['packed_original_sources'][0]['text']='Changed after retrieval.'
    with pytest.raises(ValueError,match='integrity'):validate(d,d['provenance'])


def test_generic_autonomous_flag_is_not_runtime_provenance():
    from curiosity.provenance import validate
    with pytest.raises(ValueError,match='production provenance'):validate({'operator_topic_or_source_input':False},{})


def test_stale_dossiers_prevent_a_new_execution(tmp_path):
    from curiosity.provenance import begin
    (tmp_path/'drafts').mkdir();(tmp_path/'drafts/research-1.json').write_text('{}')
    with pytest.raises(ValueError,match='Stale'):begin(tmp_path)
