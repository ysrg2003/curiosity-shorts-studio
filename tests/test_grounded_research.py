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
        config=SimpleNamespace(policy=Policy(64),keys_for=lambda provider:['not-a-real-secret'])
        def complete_auto(self,**kwargs):
            calls.append(kwargs)
            return {'provider':'google_gemini','model':research.MODEL,'text':'https://synthetic.edu/article'}
    monkeypatch.setenv('CURIOSITY_GEMINI_FREE_TIER_VERIFIED','1')
    monkeypatch.setattr(router_ai,'engine',lambda:(Router(),None))
    with pytest.raises(research.ResearchUnavailable,match='not verified'):research.grounded_urls('Synthetic?','','')
    assert calls[0]['grounding']=='search' and calls[0]['model']==research.MODEL
