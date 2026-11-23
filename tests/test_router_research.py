import pytest
from curiosity import router_research as research


def test_generated_url_is_only_a_lead_and_unreadable_sources_never_count(monkeypatch):
    leads=['https://one.edu/missing','https://one.edu/article','https://two.gov/article','https://one.edu/article']
    monkeypatch.setattr(research,'ask',lambda *a,**k:({'candidates':[{'url':u} for u in leads]},{'synthetic':True}))
    calls=[]
    def article(url):
        calls.append(url)
        if 'missing' in url:raise ValueError('not an article')
        return {'url':url,'text':'Fictional evidence. '*80,'title':'Synthetic'}
    monkeypatch.setattr(research,'article',article)
    monkeypatch.setattr(research,'passage_rank',lambda *a:1)
    sources,report=research.discover('Fictional question?','synthetic mechanism','synthetic subject','fake','unused')
    assert len(sources)==2 and len(calls)==3
    assert report['retrieval_attempts'][0]['status']=='unreadable'
    assert report['generated_urls_are_not_facts']


def test_model_leads_cannot_supply_query_credentials_or_unapproved_domain(monkeypatch):
    urls=['https://user:pass@one.edu/article','https://one.edu/search?q=fictional','https://random.example/article','http://one.edu/article']
    monkeypatch.setattr(research,'ask',lambda *a,**k:({'candidates':[{'url':u} for u in urls]},{}))
    monkeypatch.setattr(research,'article',lambda url:pytest.fail('Should not read invalid lead'))
    with pytest.raises(research.ResearchUnavailable):research.discover('Synthetic?','','','fake','unused')
