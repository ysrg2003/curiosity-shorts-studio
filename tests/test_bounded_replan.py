import pytest
from curiosity import evidence, storyboard

SRC=[{'url':'https://one.example.edu/a','title':'A','text':'The effect is seen daily. It happens through a main mechanism. A key condition applies to the observer. Another idea is popular but hedged.'},
     {'url':'https://two.example.gov/b','title':'B','text':'The effect is seen daily. The same mechanism is described again. The condition depends on viewing position.'}]

def ids(entries):
    return list(entries)

def run(monkeypatch,script):
    calls=[]
    entries=evidence.catalog(SRC)
    def fake(model,system,payload,schema,endpoint='x',seed=43,effort='none'):
        calls.append((seed,payload))
        return script[len(calls)-1](entries,payload),{'usage':{'total_tokens':1}}
    monkeypatch.setattr(storyboard,'ask',fake)
    ok,report=evidence.plan_sources('Why?',SRC,'m')
    return ok,report,calls,entries

def plan(entries,cond=()):
    by={}
    for key,e in entries.items():by.setdefault(e['source_index'],[]).append(key)
    a,b=by[0],by[1]
    return {'source_decisions':[{'source_index':0,'relevant_to_exact_question':True},{'source_index':1,'relevant_to_exact_question':True}],'observation_quote_ids':[a[0]],'mechanism_quote_ids':[a[1],b[1]],'condition_quote_ids':list(cond),'alternative_quote_ids':[],'sufficient_for_exact_question':True}

def audit(ok,missing=()):
    return {'exact_question_supported':True,'material_paths_covered':ok,'unrelated_paths_excluded':True,'missing_or_unrelated_quote_ids':list(missing)}

def test_first_plan_accepted_makes_no_replan(monkeypatch):
    ok,report,calls,_=run(monkeypatch,[lambda e,p:plan(e),lambda e,p:audit(True)])
    assert ok and len(calls)==2 and 'replan' not in report

def test_failed_audit_gets_one_replan_then_unchanged_audit_passes(monkeypatch):
    flagged=lambda e:['S0Q2']
    ok,report,calls,e=run(monkeypatch,[lambda e,p:plan(e),lambda e,p:audit(False,flagged(e)),lambda e,p:plan(e,flagged(e)),lambda e,p:audit(True)])
    assert ok and len(calls)==4
    assert calls[2][1]['audit_flagged_quote_ids']==flagged(e)
    assert report['replan']['attempted'] and report['accepted']

def test_replan_still_failing_stays_failed_and_no_third_plan(monkeypatch):
    flagged=lambda e:['S0Q2']
    ok,report,calls,e=run(monkeypatch,[lambda e,p:plan(e),lambda e,p:audit(False,flagged(e)),lambda e,p:plan(e),lambda e,p:audit(False,flagged(e))])
    assert not ok and len(calls)==4 and report['accepted'] is False

def test_unsupported_question_is_not_replanned(monkeypatch):
    bad=lambda e,p:{**audit(False),'exact_question_supported':False,'missing_or_unrelated_quote_ids':['S0Q0']}
    ok,report,calls,_=run(monkeypatch,[lambda e,p:plan(e),bad])
    assert not ok and len(calls)==2

def test_invalid_replan_contract_fails_without_audit(monkeypatch):
    flagged=lambda e:['S0Q2']
    ok,report,calls,e=run(monkeypatch,[lambda e,p:plan(e),lambda e,p:audit(False,flagged(e)),lambda e,p:{**plan(e),'sufficient_for_exact_question':False}])
    assert not ok and len(calls)==3 and report['replan']['attempted']

def test_transport_error_in_replan_propagates(monkeypatch):
    flagged=lambda e:['S0Q2']
    def boom(e,p):raise RuntimeError('provider stop')
    with pytest.raises(RuntimeError):
        run(monkeypatch,[lambda e,p:plan(e),lambda e,p:audit(False,flagged(e)),boom])
