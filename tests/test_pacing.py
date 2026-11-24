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


def _stub_adapter(monkeypatch,headers,status=429):
    import sys,types
    r_=r
    class Base:
        def __init__(self,*a,**k):pass
        def _body(self,response):return {'error':{'message':'limit','metadata':{}}}
        def _content_text(self,c):return ''
        def complete_json(self,**kw):
            class Resp:status_code=status;headers=None
            Resp.headers=headers
            self._body(Resp)
            class E(Exception):status_code=status;error_class='quota'
            raise E('{"error":{"message":"limit"}}')
    m=types.ModuleType('ai_router.providers.openai_compatible');m.OpenAICompatibleAdapter=Base
    for name in ('ai_router','ai_router.providers'):monkeypatch.setitem(sys.modules,name,types.ModuleType(name))
    monkeypatch.setitem(sys.modules,'ai_router.providers.openai_compatible',m)
    monkeypatch.setenv('OPENROUTER_API_KEY','x');monkeypatch.setattr(r_,'check_free_catalog',lambda:{r_.MODEL})
    monkeypatch.setattr(r_,'_log',[])


def _planner_stage(monkeypatch=None):
    return r.request('SECRET PROMPT TEXT','SECRET SYSTEM')


def test_failure_records_request_number_stage_and_rate_headers(clock,monkeypatch):
    _stub_adapter(monkeypatch,{'Retry-After':'1','X-RateLimit-Limit':'20','X-RateLimit-Remaining':'0','X-RateLimit-Reset':'1700000000000'})
    r._log.extend([{'request_number':1,'stage':'a','http_status':200},{'request_number':2,'stage':'b','http_status':200}])
    with pytest.raises(r.ModelRequestFailed) as e:_planner_stage()
    meta=e.value.metadata
    assert meta['request_number']==3
    assert meta['stage'].startswith('_planner_stage')
    assert (meta['rate_limit'],meta['rate_remaining'],meta['rate_reset_unix_ms'],meta['retry_after_seconds'])==(20,0,1700000000000,1)
    assert meta['requests_so_far']==3 and [x['request_number'] for x in meta['recent_requests']]==[1,2,3]
    assert meta['recent_requests'][-1]['http_status']==429


def test_diagnostics_hold_no_bodies_or_keys(clock,monkeypatch):
    import json
    _stub_adapter(monkeypatch,{'Retry-After':'abc','X-RateLimit-Remaining':'not-a-number','X-RateLimit-Limit':'99999999999'})
    with pytest.raises(r.ModelRequestFailed) as e:_planner_stage()
    text=json.dumps(e.value.metadata)
    assert 'SECRET' not in text and 'limit' not in json.dumps(e.value.metadata.get('error',''))
    assert 'rate_remaining' not in e.value.metadata and 'rate_limit' not in e.value.metadata and 'retry_after_seconds' not in e.value.metadata


def test_pause_and_single_call_unchanged_with_diagnostics(clock,monkeypatch):
    _stub_adapter(monkeypatch,{'Retry-After':'2'})
    with pytest.raises(r.ModelRequestFailed):_planner_stage()
    assert clock['sleeps']==[2] and len(r._log)==1
