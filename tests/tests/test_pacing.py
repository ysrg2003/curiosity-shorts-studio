import pytest
from curiosity import remote_ai as r


@pytest.fixture
def clock(monkeypatch):
    state={'t':100.0,'sleeps':[]}
    monkeypatch.setattr(r,'_clock',lambda:state['t'])
    def sleep(n):state['sleeps'].append(n);state['t']+=n
    monkeypatch.setattr(r,'_sleep',sleep)
    monkeypatch.setitem(r._pacing,'last',None)
    return state


def test_first_request_not_delayed(clock):
    r.pace_before_request();assert clock['sleeps']==[]


def test_back_to_back_requests_are_spaced(clock):
    r.pace_before_request();clock['t']+=0.5;r.pace_before_request()
    assert clock['sleeps']==[pytest.approx(2.7)]


def test_spacing_stays_under_twenty_per_minute(clock):
    for _ in range(21):r.pace_before_request()
    assert clock['t']-100.0>=60-3.2


def test_no_extra_wait_when_already_spaced(clock):
    r.pace_before_request();clock['t']+=5;r.pace_before_request()
    assert clock['sleeps']==[]


def test_retry_after_is_a_bounded_pause(clock):
    r.pause_for_retry_after({'retry_after_seconds':1});r.pause_for_retry_after({'retry_after_seconds':604800})
    r.pause_for_retry_after({});r.pause_for_retry_after({'retry_after_seconds':0})
    assert clock['sleeps']==[1,r.RETRY_AFTER_PAUSE_CAP_SECONDS]


def test_429_pauses_then_still_stops_with_one_call(clock,monkeypatch):
    monkeypatch.setenv('OPENROUTER_API_KEY','x')
    monkeypatch.setattr(r,'check_free_catalog',lambda:{r.MODEL})
    import sys,types
    class Base:
        def __init__(self,*a,**k):pass
        def complete_json(self,**kw):pass
    m=types.ModuleType('ai_router.providers.openai_compatible');m.OpenAICompatibleAdapter=Base
    for name in ('ai_router','ai_router.providers'):monkeypatch.setitem(sys.modules,name,types.ModuleType(name))
    monkeypatch.setitem(sys.modules,'ai_router.providers.openai_compatible',m)
    calls=[]
    def boom(self,**kw):
        calls.append(1)
        class E(Exception):status_code=429;error_class='quota'
        raise E('{"error":{"message":"limit"}}')
    monkeypatch.setattr(m.OpenAICompatibleAdapter,'complete_json',boom)
    with pytest.raises(r.ModelRequestFailed) as e:r.request('p','s')
    assert len(calls)==1 and e.value.metadata['http_status']==429 and e.value.metadata['reason']=='rate_or_quota_limit'
