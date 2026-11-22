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


def test_all_query_pools_precede_globally_ranked_reference_reads_with_per_page_caps(monkeypatch):
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
    from collections import Counter
    assert max(Counter(urlparse(url).hostname.rsplit('-',1)[0] for url in reads).values())<=6
    audit = found.value.diagnostics
    assert audit['all_query_discovery_precedes_reference_reads']
    assert all(r['discovery_query'] in searches for r in audit['retrieval_attempts'])


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
def isolated_transport(monkeypatch,request):
    if request.node.name!='test_full_extract_has_explicit_limit_matching_identity_and_scope':
        monkeypatch.setattr(autonomy,'wiki_article',lambda page_id:(_ for _ in ()).throw(OSError('Fictional no full extract fixture')))
    monkeypatch.setattr(planner,'_SOURCE_CACHE',{})
    monkeypatch.setattr(planner,'_SOURCE_FAILURES',{})
    monkeypatch.setattr(planner,'_PROVIDER_STOPS',{})
    monkeypatch.setattr(planner,'_LAST_WIKIMEDIA_REQUEST',None)
    monkeypatch.setattr(planner,'public_url',lambda url:url)
    from curiosity import entailment
    monkeypatch.setattr(entailment,'relevance_scores',lambda question,texts:autonomy.rank_texts(question,texts))


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


def test_subject_query_is_model_supplied_and_precedes_mechanism_and_full_question(monkeypatch):
    searched=[]
    monkeypatch.setattr(autonomy,'public_url',lambda url:url)
    def pages(query):
        searched.append(query)
        return [{'pageid':len(searched),'fullurl':'https://en.wikipedia.org/wiki/Synthetic','title':query,'extract':'Synthetic observable fixture. '*30}]
    monkeypatch.setattr(autonomy,'wiki_pages',pages)
    monkeypatch.setattr(autonomy,'wiki_links',lambda index:[{'url':'https://fixture.edu/article','context':'Synthetic fixture motion'}])
    monkeypatch.setattr(autonomy,'article',lambda url:{'url':url,'title':'Synthetic fixture motion','text':'Synthetic fixture motion. '*40})
    sources,audit=autonomy.research('Why does a synthetic fixture move?','synthetic vector motion','synthetic fixture')
    assert searched==['synthetic fixture','synthetic vector motion','Why does a synthetic fixture move?']
    assert 'synthetic' in sources[0]['title'].lower() and audit['subject_query_is_not_fact']


def test_later_more_relevant_document_is_not_suppressed_by_same_publisher(monkeypatch):
    monkeypatch.setattr(autonomy,'public_url',lambda url:url)
    monkeypatch.setattr(autonomy,'wiki_pages',lambda query:[page()])
    monkeypatch.setattr(autonomy,'wiki_links',lambda index:[{'url':'https://fixture.edu/early'},{'url':'https://fixture.edu/later'}])
    reads=[]
    def article(url):
        reads.append(url)
        return {'url':url,'title':'Synthetic fixture motion' if url.endswith('later') else 'Unrelated fictional biography','text':'Synthetic fixture motion. '*40 if url.endswith('later') else 'Unrelated fictional account. '*40}
    monkeypatch.setattr(autonomy,'article',article)
    sources,audit=autonomy.research('Why does a synthetic fixture move?','synthetic mechanism')
    assert len(reads)==2 and sources[1]['url'].endswith('later')
    assert len(audit['document_candidates'])==2 and len(audit['retrieval_attempts'])==2


def test_document_collection_finishes_bounded_queue_before_four_source_selection(monkeypatch):
    monkeypatch.setattr(autonomy,'public_url',lambda url:url)
    monkeypatch.setattr(autonomy,'wiki_pages',lambda query:[page()])
    monkeypatch.setattr(autonomy,'wiki_links',lambda index:[{'url':f'https://host{i}.edu/article'} for i in range(7)])
    monkeypatch.setattr(autonomy,'article',lambda url:{'url':url,'title':'Synthetic fixture motion' if 'host5.' in url else 'Fictional record','text':'Fictional source text. '*40})
    sources,audit=autonomy.research('Why does a synthetic fixture move?','synthetic mechanism')
    assert len(audit['retrieval_attempts'])==6 and len(sources)==4
    assert any('host5.' in source['url'] for source in sources)
    assert len({autonomy.publisher(source['url']) for source in sources})==4


def abstract_record(text=None):
    return {'hitCount':1,'result':{'id':'123','pmid':'123','source':'MED','title':'Fictional synthetic abstract','pubYear':'2001',
            'abstractText':text if text is not None else 'This fictional abstract describes only a synthetic fixture used in a unit test. '*14,
            'affiliation':'This metadata is not source evidence and must not be propagated.'}}


def test_pubmed_uses_matching_structured_public_record_and_explicit_abstract_scope(monkeypatch):
    seen=[]
    monkeypatch.setattr(autonomy,'public_url',lambda url:url)
    def fetch(url):seen.append(url);return abstract_record()
    monkeypatch.setattr(autonomy,'fetch',fetch)
    source=autonomy.article('https://pubmed.ncbi.nlm.nih.gov/123')
    assert '/article/MED/123?' in seen[0] and 'resultType=core' in seen[0]
    assert source['pmid']=='123' and source['source_scope']=='abstract_only' and source['publication_year']=='2001'
    assert source['text']==abstract_record()['result']['abstractText'].strip()
    assert 'affiliation' not in source and 'metadata is not source evidence' not in source['text']


@pytest.mark.parametrize('change,code',[
    ('wrong_id','abstract_identity_mismatch'),('wrong_source','abstract_identity_mismatch'),
    ('wrong_pmid','abstract_identity_mismatch'),('missing','abstract_missing'),('short','abstract_too_short')])
def test_structured_abstract_cannot_mismatch_identity_or_pad_short_text(monkeypatch,change,code):
    data=abstract_record()
    if change=='wrong_id':data['result']['id']='456'
    if change=='wrong_source':data['result']['source']='OTHER'
    if change=='wrong_pmid':data['result']['pmid']='456'
    if change=='missing':data['result'].pop('abstractText')
    if change=='short':data['result'].update(abstractText='A tiny fictional abstract.',title='Fictional metadata. '*1000)
    monkeypatch.setattr(autonomy,'public_url',lambda url:url)
    monkeypatch.setattr(autonomy,'fetch',lambda url:data)
    with pytest.raises(planner.SourceValidationError) as found:autonomy.article('https://pubmed.ncbi.nlm.nih.gov/123')
    assert found.value.metadata['reason_code']==code


def test_abstract_scope_is_preserved_in_model_source_pack():
    from curiosity.storyboard import source_pack
    source={'url':'https://example.edu/fixture','title':'Fictional abstract','text':'A fictional synthetic abstract supports only this fixture sentence. '*15,
            'source_scope':'abstract_only','publication_year':'2001','pmid':'123','retrieval_url':'https://example.edu/api/fixture'}
    packed=source_pack('Synthetic fixture?', [source])[0]
    assert all(packed[key]==source[key] for key in ('source_scope','publication_year','pmid','retrieval_url'))


def test_subject_query_cannot_be_missing_unrelated_or_question_filler(monkeypatch):
    for phrase in ('','unrelated planets','why does'):
        calls=[]
        def ask(*args):
            calls.append(args)
            return {'candidates':[{'question':'Why does a synthetic fixture move?','search_terms':'synthetic mechanism','subject_query':phrase} for _ in range(3)]},{}
        monkeypatch.setattr(autonomy,'ask',ask)
        with pytest.raises(autonomy.ResearchUnavailable):autonomy.questions('synthetic',[])
        assert len(calls)==2 and 'subject_query' in calls[0][3]['properties']['candidates']['items']['required']


def test_europepmc_reads_are_serial_paced_and_cached(monkeypatch):
    clock=[100.0];sleeps=[];calls=[]
    monkeypatch.setattr(planner,'_LAST_EUROPEPMC_REQUEST',None)
    monkeypatch.setattr(planner.time,'monotonic',lambda:clock[0])
    def sleep(seconds):sleeps.append(seconds);clock[0]+=seconds
    monkeypatch.setattr(planner.time,'sleep',sleep)
    def response(request,timeout):calls.append(request.full_url);clock[0]+=0.25;return Response(request.full_url)
    install_opener(monkeypatch,response)
    first='https://www.ebi.ac.uk/europepmc/webservices/rest/article/MED/123?fixture=1'
    second='https://www.ebi.ac.uk/europepmc/webservices/rest/article/MED/456?fixture=2'
    planner.source_bytes(first);planner.source_bytes(first);planner.source_bytes(second)
    assert len(calls)==2 and sleeps==[0.75]


def test_semantic_shortlist_keeps_lexically_sparse_pages_without_hard_overlap(monkeypatch):
    reads=[];citation_pages=[]
    monkeypatch.setattr(autonomy,'public_url',lambda url:url)
    def pages(query):return [
        {'pageid':1,'title':'Synthetic fixture','extract':'Synthetic fixture moves in this fictional scenario. '*30,'fullurl':'https://en.wikipedia.org/wiki/Fixture'},
        {'pageid':2,'title':'Fictional performer','extract':'An unrelated imaginary biography. '*30,'fullurl':'https://en.wikipedia.org/wiki/Performer'}]
    monkeypatch.setattr(autonomy,'wiki_pages',pages)
    def links(index):
        citation_pages.append(index)
        return [{'url':'https://first.edu/fixture','context':'Synthetic fixture movement in a fictional experiment.'},
                {'url':'https://second.edu/biography','context':'Fictional performer biography.'}]
    monkeypatch.setattr(autonomy,'wiki_links',links)
    def article(url):reads.append(url);return {'url':url,'title':'Synthetic fixture movement','text':'Synthetic fixture motion. '*40}
    monkeypatch.setattr(autonomy,'article',article)
    sources,audit=autonomy.research('Why does a synthetic fixture move?','synthetic motion','synthetic fixture')
    assert set(citation_pages)=={1,2} and 'https://first.edu/fixture' in reads and len(sources)==3
    assert all(row.get('status')!='subject_mismatch_skipped' for row in audit['discovery'])


def test_reused_bm25_stemming_matches_inflections_and_ignores_question_filler():
    from curiosity.autonomy import rank_texts,tokens,subject_overlap
    assert tokens('clouds')==tokens('cloud') and tokens('why does the')==()
    scores=rank_texts('synthetic moving fixture',['Fictional actor biography.','Synthetic fixtures move in an imaginary experiment.'])
    assert scores[1]>scores[0] and subject_overlap('synthetic fixture','Synthetic fixtures move.')==1
    assert rank_texts('fixture',['',''])==[0,0] and rank_texts('fixture',[])==[]


def test_globally_ranked_citations_prefer_exact_subject_over_pool_turns(monkeypatch):
    monkeypatch.setattr(autonomy,'public_url',lambda url:url)
    monkeypatch.setattr(autonomy,'wiki_pages',lambda query:[page(1),page(2)])
    def links(index):return [{'url':f'https://host{index}-{i}.edu/fixture','context':('synthetic fixture movement' if index==2 else 'synthetic general notes')} for i in range(8)]
    monkeypatch.setattr(autonomy,'wiki_links',links)
    reads=[]
    def article(url):reads.append(url);raise OSError('Synthetic fixture unavailable')
    monkeypatch.setattr(autonomy,'article',article)
    with pytest.raises(autonomy.ResearchUnavailable):autonomy.research('Why does a synthetic fixture move?','synthetic motion','synthetic fixture')
    assert len(reads)==10 and all('host2-' in url for url in reads[:6])
    assert sum('host2-' in url for url in reads)==6


"""Fictional source controls, never inputs for automatic production."""
from curiosity import autonomy,storyboard,entailment


def test_citation_uses_body_context_and_keeps_title_separate():
    parser=autonomy.CitationLinks()
    parser.feed('<p>The fictional vane moves because a tiny motor turns its axle. <sup><a href="#cite_note-opaque-1">[1]</a></sup></p><p>Another unrelated paragraph.</p><ol><li id="cite_note-opaque-1">Opaque experiment title <a href="https://example.edu/opaque">Read</a></li></ol>')
    item=parser.items[0]
    assert 'motor turns its axle' in item['body_context']
    assert 'Opaque experiment title' in item['citation_context']
    assert 'unrelated' not in item['context']


def test_repeated_citation_context_is_bounded_and_preserves_qualifier():
    parser=autonomy.CitationLinks()
    parser.feed(''.join('<p>In the fictional laboratory only, a motor moves the vane. <a href="#cite_note-demo">[1]</a></p>' for _ in range(8))+'<li id="cite_note-demo"><a href="https://example.edu/demo">Paper</a></li>')
    assert parser.items[0]['body_context'].count('laboratory only')==1


def test_semantic_source_pack_preserves_original_contiguous_passage_and_budget(monkeypatch):
    opening='Historical fictional context for a demonstration. '*20
    middle='An unrelated fictional biography fills this introductory section. '*35
    target='In this fictional experiment, the motor turns the axle and moves the vane. This effect was only observed in the laboratory, not outdoors. '
    text=opening+middle+target*6
    monkeypatch.setattr(entailment,'relevance_scores',lambda q,passages:[10 if 'motor turns' in p else -10 for p in passages])
    packed=storyboard.source_pack('Why does the fictional vane move?',[{'url':'https://example.edu/fiction','text':text}],budget=1600,semantic=True)[0]
    assert packed['text'] in text and 'motor turns' in packed['text'] and 'only observed' in packed['text']
    assert len(packed['text'])+len(packed.get('document_opening',''))<=1600
    assert packed['document_opening']==text[:600]


def test_passage_rank_reads_later_original_windows_not_just_opening(monkeypatch):
    text='An irrelevant fictional biography describes a performer and the venue. '*80+'A motor turns the fictional axle and raises the small flag. '*8
    seen=[]
    def rank(q,passages):
        seen.extend(passages);return [8 if 'motor turns' in p else -8 for p in passages]
    monkeypatch.setattr(entailment,'relevance_scores',rank)
    assert storyboard.passage_rank('Why does the flag rise?',text)==8
    assert len(seen)<=40 and all(len(p)<=1802 for p in seen)


def test_full_extract_has_explicit_limit_matching_identity_and_scope(monkeypatch):
    from urllib.parse import parse_qs,urlparse
    def fetch(url):
        query=parse_qs(urlparse(url).query)
        assert 'exchars' not in query and 'exintro' not in query
        return {'query':{'pages':{'12':{'pageid':12,'title':'Fictional experiment','fullurl':'https://en.wikipedia.org/wiki/Fixture','extract':'A fictional motor turns a vane. '*30}}}}
    monkeypatch.setattr(autonomy,'fetch',fetch);monkeypatch.setattr(autonomy,'public_url',lambda url:url)
    source=autonomy.wiki_article(12)
    assert source['source_scope']=='encyclopedia_article_excerpt' and 'motor' in source['text']


def test_education_government_host_rules_are_generic_not_a_topic_whitelist():
    assert autonomy.eligible_reference('https://fictional.weather.gov/article')
    assert autonomy.eligible_reference('https://fictional.ac.uk/article')
    assert not autonomy.eligible_reference('https://fictional.gov.attacker.invalid/article')
    assert not autonomy.eligible_reference('https://fictional.gov/search?q=example')
