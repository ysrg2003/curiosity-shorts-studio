from urllib.parse import parse_qs,urlparse
import pytest
from curiosity import autonomy


def test_search_and_rendered_citations_use_one_bounded_read_each(monkeypatch):
    seen=[]
    def fetch(url):
        query=parse_qs(urlparse(url).query);seen.append(query)
        assert query['maxlag']==['5']
        if query.get('generator')==['search']:
            assert query['prop']==['extracts|info'] and query['gsrlimit']==['3']
            return {'query':{'pages':{'1':{'pageid':1,'title':'Synthetic page','index':1}}}}
        assert query['action']==['parse'] and query['pageid']==['1'] and query['prop']==['text']
        return {'parse':{'text':'<ol><li id="cite_note-1">Fictional synthetic citation <a href="https://first.edu/article">Full text</a></li><li id="cite_note-2">Another fixture <a href="https://second.edu/article">Article</a></li></ol>'}}
    monkeypatch.setattr(autonomy,'fetch',fetch)
    assert autonomy.wiki_pages('synthetic')[0]['pageid']==1
    links=autonomy.wiki_links(1)
    assert len(links)==2 and len(seen)==2 and 'Fictional' in links[0]['context']


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
    assert len(reads)==10 and searches==['synthetic mechanism','Synthetic question?']
    assert len(error.value.diagnostics['retrieval_attempts'])==10


def test_backup_mechanism_query_is_used_when_reference_budget_remains(monkeypatch):
    searches=[]
    monkeypatch.setattr(autonomy,'public_url',lambda url:url)
    def pages(query):searches.append(query);return [] if len(searches)==1 else [page()]
    monkeypatch.setattr(autonomy,'wiki_pages',pages)
    monkeypatch.setattr(autonomy,'wiki_links',lambda index:[{'*':'https://example.edu/article'}])
    monkeypatch.setattr(autonomy,'article',lambda url:{'url':url,'text':'Synthetic evidence. '*50})
    sources,audit=autonomy.research('Synthetic question?','synthetic mechanism')
    assert len(sources)==2 and searches==['synthetic mechanism','Synthetic question?']


def test_both_query_pools_are_discovered_before_reference_budget_and_reads_are_interleaved(monkeypatch):
    monkeypatch.setattr(autonomy, 'public_url', lambda url: url)
    searches = []; reads = []
    def pages(query):
        searches.append(query)
        offset = 10 if query == 'synthetic mechanism' else 20
        return [page(offset + i) for i in range(3)]
    monkeypatch.setattr(autonomy, 'wiki_pages', pages)
    monkeypatch.setattr(autonomy, 'wiki_links', lambda index: [{'*': f'https://host{index}-{i}.edu/article'} for i in range(8)])
    def article(url):
        assert searches == ['synthetic mechanism', 'Synthetic question?']
        reads.append(url)
        raise OSError('Synthetic unavailable source fixture')
    monkeypatch.setattr(autonomy, 'article', article)
    with pytest.raises(autonomy.ResearchUnavailable) as found:
        autonomy.research('Synthetic question?', 'synthetic mechanism')
    assert len(reads) == 10
    assert reads[:4] == ['https://host10-0.edu/article', 'https://host20-0.edu/article',
                         'https://host11-0.edu/article', 'https://host21-0.edu/article']
    audit = found.value.diagnostics
    assert audit['all_query_discovery_precedes_reference_reads']
    assert {r['discovery_query'] for r in audit['retrieval_attempts']} == set(searches)


def test_unavailable_mechanism_search_does_not_prevent_exact_question_discovery(monkeypatch):
    searches = []
    monkeypatch.setattr(autonomy, 'public_url', lambda url: url)
    def pages(query):
        searches.append(query)
        if query == 'synthetic mechanism': raise OSError('Synthetic unavailable discovery')
        return [page()]
    monkeypatch.setattr(autonomy, 'wiki_pages', pages)
    monkeypatch.setattr(autonomy, 'wiki_links', lambda index: [{'*': 'https://example.edu/fixture'}])
    monkeypatch.setattr(autonomy, 'article', lambda url: {'url': url, 'text': 'Synthetic source fixture. ' * 40})
    sources, audit = autonomy.research('Synthetic question?', 'synthetic mechanism')
    assert len(sources) == 2 and searches == ['synthetic mechanism', 'Synthetic question?']
    assert audit['discovery'][0]['status'] == 'unavailable'


"""Synthetic transport/citation checks. No production topics, publisher text or live HTTP."""
import io
import json
from email.message import Message
from urllib.error import HTTPError
import pytest
from curiosity import autonomy, planner


@pytest.fixture(autouse=True)
def isolated_transport(monkeypatch):
    monkeypatch.setattr(planner,'_SOURCE_CACHE',{})
    monkeypatch.setattr(planner,'_SOURCE_FAILURES',{})
    monkeypatch.setattr(planner,'_PROVIDER_STOPS',{})
    monkeypatch.setattr(planner,'_LAST_WIKIMEDIA_REQUEST',None)
    monkeypatch.setattr(planner,'public_url',lambda url:url)


class Response(io.BytesIO):
    def __init__(self,url,body=b'{"query":{}}',content_type='application/json'):
        super().__init__(body);self.url=url;self.headers=Message();self.headers['Content-Type']=content_type


def install_opener(monkeypatch,handler):
    class Opener:
        def open(self,request,timeout):return handler(request,timeout)
    monkeypatch.setattr(planner,'build_opener',lambda *args:Opener())


def test_stable_identified_agent_has_public_contact_and_no_browser_impersonation():
    assert 'https://github.com/ysrg2003/curiosity-shorts-studio' in planner.USER_AGENT
    assert 'bot' in planner.USER_AGENT and 'Mozilla' not in planner.USER_AGENT


def test_serial_wikimedia_spacing_and_success_cache_avoid_duplicate_http(monkeypatch):
    clock=[100.0];sleeps=[];seen=[]
    monkeypatch.setattr(planner.time,'monotonic',lambda:clock[0])
    def sleep(seconds):sleeps.append(seconds);clock[0]+=seconds
    monkeypatch.setattr(planner.time,'sleep',sleep)
    def response(request,timeout):
        seen.append((request.full_url,request.get_header('User-agent'),timeout));clock[0]+=0.25
        return Response(request.full_url)
    install_opener(monkeypatch,response)
    first='https://en.wikipedia.org/w/api.php?fixture=1'
    second='https://en.wikipedia.org/w/api.php?fixture=2'
    planner.source_bytes(first);planner.source_bytes(first);planner.source_bytes(second)
    assert len(seen)==2 and sleeps==[6.75]
    assert all(entry[1]==planner.USER_AGENT and entry[2]==25 for entry in seen)


@pytest.mark.parametrize('status',[401,403,429,503])
def test_provider_stop_preserves_status_and_retry_after_without_retrying(status,monkeypatch):
    calls=[]
    def denied(request,timeout):
        calls.append(request.full_url)
        headers=Message();headers['Retry-After']='123'
        raise HTTPError(request.full_url,status,'Synthetic error',headers,io.BytesIO(b'Synthetic body must not enter diagnostics'))
    install_opener(monkeypatch,denied)
    with pytest.raises(planner.SourceReadError) as found:planner.source_bytes('https://en.wikipedia.org/w/api.php?fixture=1')
    assert found.value.metadata['http_status']==status and found.value.metadata['retry_after_seconds']==123
    assert found.value.metadata['provider_stop'] and found.value.metadata['network_attempted']
    with pytest.raises(planner.SourceReadError) as again:planner.source_bytes('https://en.wikipedia.org/w/api.php?fixture=2')
    assert len(calls)==1 and again.value.metadata['network_attempted'] is False
    assert 'Synthetic body' not in json.dumps(found.value.metadata)


def test_nonprovider_404_is_cached_by_url_but_does_not_block_other_articles(monkeypatch):
    calls=[]
    def response(request,timeout):
        calls.append(request.full_url)
        if request.full_url.endswith('/missing'):raise HTTPError(request.full_url,404,'Synthetic missing',Message(),None)
        return Response(request.full_url,b'<p>Synthetic public fixture.</p>','text/html')
    install_opener(monkeypatch,response)
    for _ in range(2):
        with pytest.raises(planner.SourceReadError) as found:planner.source_bytes('https://example.edu/missing')
        assert found.value.metadata['http_status']==404 and not found.value.metadata['provider_stop']
    assert planner.source_bytes('https://example.edu/article')[1].startswith(b'<p>')
    assert len(calls)==2


def test_http_200_api_maxlag_is_a_provider_stop_and_drops_server_prose(monkeypatch):
    install_opener(monkeypatch,lambda request,timeout:Response(request.full_url,b'{"error":{"code":"maxlag","info":"Synthetic prose must not enter logs"}}'))
    with pytest.raises(planner.SourceReadError) as found:planner.fetch('https://en.wikipedia.org/w/api.php?fixture=maxlag')
    assert found.value.metadata['api_code']=='maxlag' and found.value.metadata['provider_stop']
    assert 'Synthetic prose' not in json.dumps(found.value.metadata)


@pytest.mark.parametrize('value,expected',[('42',42),('invalid',None),(None,None),('-7',None)])
def test_retry_after_numeric_or_invalid_values(value,expected):
    assert planner.retry_after_seconds(value)==expected


def test_retry_after_http_date(monkeypatch):
    monkeypatch.setattr(planner.time,'time',lambda:0)
    assert planner.retry_after_seconds('Thu, 01 Jan 1970 00:02:00 GMT')==120


def test_citation_context_ranking_ignores_bare_url_order_and_search_hubs():
    parser=autonomy.CitationLinks()
    parser.feed('<a href="https://unrelated.edu/navigation">navigation</a><ol><li id="cite_note-a"><span>Historical fixture</span><a href="https://first.edu/old">Title</a></li><li id="cite_note-b">Synthetic motion mechanism<a href="https://second.edu/current">Full text</a><a href="https://third.edu/search?q=synthetic">Search</a></li></ol>')
    urls=autonomy.rank_references(parser.items,'Why synthetic motion?','synthetic motion mechanism')
    assert urls==['https://second.edu/current','https://first.edu/old']
    assert all('navigation' not in link['url'] for link in parser.items)


def test_discovery_stop_aborts_other_queries_and_candidate_topics(monkeypatch):
    calls=[]
    monkeypatch.setattr(autonomy,'questions',lambda *args:([{'question':'Synthetic first question?','search_terms':'synthetic mechanism'},{'question':'Synthetic second question?','search_terms':'another mechanism'}],{}))
    def unavailable(query):
        calls.append(query)
        raise planner.SourceReadError({'kind':'http_error','provider':'wikimedia','http_status':429,'provider_stop':True,'network_attempted':True})
    monkeypatch.setattr(autonomy,'wiki_pages',unavailable)
    with pytest.raises(autonomy.ResearchUnavailable) as found:autonomy.select_and_research('synthetic',[])
    assert calls==['synthetic mechanism']
    assert found.value.diagnostics['provider_pause']['http_status']==429
    assert len(found.value.diagnostics['rejections'])==1


def test_reference_api_stop_aborts_before_articles(monkeypatch):
    monkeypatch.setattr(autonomy,'public_url',lambda url:url)
    monkeypatch.setattr(autonomy,'wiki_pages',lambda query:[{'pageid':1,'fullurl':'https://en.wikipedia.org/wiki/Fixture','extract':'Synthetic fixture text. '*30}])
    def unavailable(index):raise planner.SourceReadError({'provider':'wikimedia','http_status':403,'provider_stop':True})
    monkeypatch.setattr(autonomy,'wiki_links',unavailable)
    monkeypatch.setattr(autonomy,'article',lambda url:pytest.fail('Provider stop reached an article'))
    with pytest.raises(autonomy.ResearchUnavailable) as found:autonomy.research('Synthetic question?','synthetic mechanism')
    assert found.value.diagnostics['provider_pause']['http_status']==403
