import json
import pytest
from curiosity import resume_research as rr


def dossier(tmp_path):
    data={'schema_version':1,'operator_topic_or_source_input':False,'question':'A synthetic unchanged question?','packed_original_sources':[{'url':'https://one.edu/x','text':'Synthetic original one.'},{'url':'https://two.gov/x','text':'Synthetic original two.'}]}
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
