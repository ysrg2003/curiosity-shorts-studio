from urllib.parse import parse_qs,urlparse
import pytest
from curiosity import autonomy


def test_search_and_reference_limits_are_separate_and_continuation_is_bounded(monkeypatch):
    seen=[]
    def fetch(url):
        query=parse_qs(urlparse(url).query);seen.append(query)
        if query.get('generator')==['search']:
            assert query['prop']==['extracts|info'] and query['gsrlimit']==['3']
            return {'query':{'pages':{'1':{'pageid':1,'title':'Synthetic page','index':1}}}}
        assert query['pageids']==['1'] and query['ellimit']==['100']
        if 'elcontinue' not in query:return {'query':{'pages':{'1':{'extlinks':[{'*':'https://first.edu/article'}]}}},'continue':{'continue':'||','elcontinue':'opaque token|1','unrelated':'not forwarded'}}
        assert query['elcontinue']==['opaque token|1'] and 'unrelated' not in query
        return {'query':{'pages':{'1':{'extlinks':[{'*':'https://second.edu/article'}]}}},'continue':{'elcontinue':'another token'}}
    monkeypatch.setattr(autonomy,'fetch',fetch)
    assert autonomy.wiki_pages('synthetic')[0]['pageid']==1
    assert len(autonomy.wiki_links(1))==2 and len(seen)==3


def test_document_resolution_does_not_accept_homepage_or_pdf_to_html_substitution():
    with pytest.raises(ValueError,match='generic'):autonomy.document_resolution('https://example.edu/old-article','https://example.edu/',False)
    with pytest.raises(ValueError,match='non-PDF'):autonomy.document_resolution('https://example.edu/paper.pdf','https://example.edu/department',False)
    autonomy.document_resolution('https://example.edu/old-article','https://example.edu/news/new-article',False)
    autonomy.document_resolution('https://example.edu/paper.pdf','https://example.edu/download/paper',True)


def page(index=1):
    return {'pageid':index,'index':index,'title':'Synthetic source','fullurl':'https://en.wikipedia.org/wiki/Synthetic','extract':'Synthetic test source. '*30}


def test_research_skips_stale_resolution_and_collects_four_publisher_candidates(monkeypatch):
    monkeypatch.setattr(autonomy,'public_url',lambda url:url)
    monkeypatch.setattr(autonomy,'wiki_pages',lambda query:[page()])
    urls=['https://old.edu/paper.pdf','https://first.edu/article','https://second.edu/article','https://science.nasa.gov/article']
    monkeypatch.setattr(autonomy,'wiki_links',lambda index:[{'*':url} for url in urls])
    def article(url):
        if 'old.edu' in url:autonomy.document_resolution(url,'https://old.edu/',False)
        return {'url':url,'text':'Synthetic test source. '*40,'publisher':autonomy.publisher(url)}
    monkeypatch.setattr(autonomy,'article',article)
    sources,audit=autonomy.research('Synthetic question?','synthetic mechanism')
    assert len(sources)==4 and len(audit['publishers'])==4 and len(audit['retrieval_attempts'])==4
    assert audit['retrieval_attempts'][0]['status']=='unreadable'
    assert all('old.edu' not in source['url'] for source in sources)


def test_failed_reference_retrieval_is_bounded_across_both_queries(monkeypatch):
    monkeypatch.setattr(autonomy,'public_url',lambda url:url)
    searches=[];reads=[]
    def pages(query):searches.append(query);return [page(i) for i in range(3)]
    monkeypatch.setattr(autonomy,'wiki_pages',pages)
    monkeypatch.setattr(autonomy,'wiki_links',lambda index:[{'*':f'https://host{index}-{i}.edu/article'} for i in range(8)])
    def article(url):reads.append(url);raise OSError('synthetic unavailable reference')
    monkeypatch.setattr(autonomy,'article',article)
    with pytest.raises(autonomy.ResearchUnavailable) as error:autonomy.research('Synthetic question?','synthetic mechanism')
    assert len(reads)==10 and searches==['synthetic mechanism']
    assert len(error.value.diagnostics['retrieval_attempts'])==10


def test_backup_question_query_is_used_when_reference_budget_remains(monkeypatch):
    searches=[]
    monkeypatch.setattr(autonomy,'public_url',lambda url:url)
    def pages(query):searches.append(query);return [] if len(searches)==1 else [page()]
    monkeypatch.setattr(autonomy,'wiki_pages',pages)
    monkeypatch.setattr(autonomy,'wiki_links',lambda index:[{'*':'https://example.edu/article'}])
    monkeypatch.setattr(autonomy,'article',lambda url:{'url':url,'text':'Synthetic evidence. '*50})
    sources,audit=autonomy.research('Synthetic question?','synthetic mechanism')
    assert len(sources)==2 and searches==['synthetic mechanism','Synthetic question?']
