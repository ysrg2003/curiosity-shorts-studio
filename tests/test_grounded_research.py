import pytest
from curiosity import grounded_research as research,router_ai


def test_grounded_route_requires_verified_free_account_before_engine(monkeypatch):
    monkeypatch.delenv('CURIOSITY_GEMINI_FREE_TIER_VERIFIED',raising=False)
    monkeypatch.setattr(router_ai,'engine',lambda:pytest.fail('Must block before keys or inference'))
    with pytest.raises(ValueError,match='not verified'):research.grounded_urls('Synthetic?','','')


def test_generated_urls_without_actual_search_metadata_are_not_grounding(monkeypatch):
    from types import SimpleNamespace
    from dataclasses import make_dataclass
    Policy=make_dataclass('Policy',[('max_attempts',int)])
    calls=[]
    class Router:
        _curiosity_failures=[]
        config=SimpleNamespace(policy=Policy(64),keys_for=lambda provider:['not-a-real-secret'])
        def complete_auto(self,**kwargs):
            calls.append(kwargs)
            return {'provider':'google_gemini','model':research.MODEL,'text':'https://synthetic.edu/article'}
    monkeypatch.setenv('CURIOSITY_GEMINI_FREE_TIER_VERIFIED','1')
    monkeypatch.setattr(router_ai,'engine',lambda:(Router(),None))
    with pytest.raises(research.ResearchUnavailable,match='not verified'):research.grounded_urls('Synthetic?','','')
    assert calls[0]['grounding']=='search' and calls[0]['model']==research.MODEL


def test_final_hop_error_does_not_poison_citation_gateway(monkeypatch):
    from urllib.error import HTTPError
    from curiosity import planner
    monkeypatch.setattr(planner,'public_url',lambda u:u)
    monkeypatch.setattr(planner,'_SOURCE_FAILURES',{})
    monkeypatch.setattr(planner,'_PROVIDER_STOPS',{})
    class Opener:
        def open(self,*a,**k):raise HTTPError('https://blocked.edu/article',403,'Forbidden',{},None)
    monkeypatch.setattr(planner,'build_opener',lambda *a:Opener())
    with pytest.raises(planner.SourceReadError) as exc:
        planner.source_bytes('https://vertexaisearch.cloud.google.com/grounding-api-redirect/synthetic')
    assert exc.value.metadata['provider']=='blocked.edu'
    assert 'blocked.edu' in planner._PROVIDER_STOPS
    assert 'vertexaisearch.cloud.google.com' not in planner._PROVIDER_STOPS
