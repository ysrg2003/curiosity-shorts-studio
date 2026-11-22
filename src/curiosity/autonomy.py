"""No-input topic hypotheses and keyless research. Discovery is not truth certification."""
import hashlib
import re
from urllib.parse import urlencode,urlparse,parse_qs
from html.parser import HTMLParser
from .planner import fetch,public_url,source_bytes,source_error,SourceValidationError
from .storyboard import ask

PUBLISHERS=('nasa.gov','noaa.gov','usgs.gov','nih.gov','nsf.gov','science.org','nature.com','scientificamerican.com','openstax.org','esa.int','metoffice.gov.uk','sciencefocus.com','britannica.com')


def publisher(url):
    host=(urlparse(url).hostname or '').lower()
    parts=host.split('.')
    return '.'.join(parts[-3:] if '.'.join(parts[-2:]) in {'co.uk','ac.uk','gov.uk','com.au','gov.au'} else parts[-2:])


def eligible_reference(url):
    p=urlparse(url);host=(p.hostname or '').lower()
    if p.path.rstrip('/').lower().split('/')[-1] in {'search','query','query.fcgi','entrez'} or set(parse_qs(p.query)) & {'q','query','search','term'}:return False
    return p.scheme=='https' and (host.endswith('.edu') or any(host==root or host.endswith('.'+root) for root in PUBLISHERS))


def questions(model,previous,endpoint='http://127.0.0.1:11434',seed=43):
    from .remote_ai import ModelOutputInvalid
    schema={'type':'object','properties':{'candidates':{'type':'array','minItems':3,'maxItems':3,'items':{'type':'object','properties':{'question':{'type':'string','minLength':10,'maxLength':110},'search_terms':{'type':'string','minLength':3,'maxLength':150}},'required':['question','search_terms']}}},'required':['candidates']}
    attempts=[]
    for attempt in range(2):
        try:
            data,stats=ask(model,'Propose exactly 3 distinct, visually explainable everyday science questions for a playful English educational cartoon. Choose from physics, chemistry, astronomy, weather or ordinary nonmedical biology. Do not propose medical advice, disease, politics, product claims or current events. These are unverified research hypotheses, not factual answers. Avoid the supplied previous topics. Each question is 10 to 110 characters. search_terms is 3 to 150 characters and names its precise scientific mechanism. Return JSON only. /no_think',{'previous_topics':previous[-100:],'proposal_variation':attempt+1,'revision_feedback':attempts[-1].get('rejected') if attempts else ''},schema,endpoint,seed+attempt)
        except ModelOutputInvalid as error:
            attempts.append({'attempt':attempt+1,'rejected':'schema_invalid','response_shape':error.metadata});continue
        result=[];checks=[]
        for item in data.get('candidates',[]):
            q=str(item.get('question','')).strip();terms=str(item.get('search_terms','')).strip()
            repeated=duplicate(q,previous);valid=10<=len(q)<=110 and 3<=len(terms)<=150 and not repeated
            checks.append({'question_characters':len(q),'search_characters':len(terms),'duplicate':repeated,'accepted':valid})
            if valid:result.append({'question':q,'search_terms':terms})
        attempts.append({'attempt':attempt+1,'selection':stats,'candidate_checks':checks,'rejected':None if result else 'no_unseen_in_bounds_candidate'})
        if result:return result,{**stats,'proposal_attempts':attempts}
    raise ResearchUnavailable('No valid unseen topic hypotheses after 2 bounded proposals. No video created.',{'proposal_attempts':attempts,'operator_topic_or_source_input':False})


def duplicate(question,previous):
    def words(text):return set(re.findall(r'[a-z]{4,}',text.lower()))-{'does','what','when','where','that','with','have','from','your'}
    a=words(question)
    return any(a==words(old) or len(a&words(old))/max(1,len(a|words(old)))>=0.7 for old in previous)


class ResearchUnavailable(ValueError):
    def __init__(self,message,diagnostics):
        super().__init__(message);self.diagnostics=diagnostics


def wiki_pages(query):
    params=urlencode({'action':'query','generator':'search','gsrsearch':query,'gsrlimit':3,'prop':'extracts|info','explaintext':1,'exintro':1,'inprop':'url','maxlag':5,'format':'json'})
    data=fetch('https://en.wikipedia.org/w/api.php?'+params)
    return sorted(data.get('query',{}).get('pages',{}).values(),key=lambda page:page.get('index',999))


class CitationLinks(HTMLParser):
    """Read citation context, not bare URL ordering. Context remains untrusted data."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.items=[];self.depth=0;self.urls=[];self.parts=[]
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if tag=='li':
            if self.depth:self.depth+=1
            elif attrs.get('id','').startswith('cite_note'):
                self.depth=1;self.urls=[];self.parts=[]
        if self.depth and tag=='a':
            href=attrs.get('href','')
            if href.startswith(('https://','http://')):self.urls.append(href)
    def handle_data(self,data):
        if self.depth:self.parts.append(data)
    def handle_endtag(self,tag):
        if tag=='li' and self.depth:
            self.depth-=1
            if not self.depth:
                context=re.sub(r'\s+',' ',' '.join(self.parts)).strip()[:1200]
                self.items.extend({'url':url,'context':context} for url in dict.fromkeys(self.urls))


def wiki_links(page_id):
    params={'action':'parse','pageid':str(page_id),'prop':'text','disableeditsection':1,
            'disablelimitreport':1,'maxlag':5,'format':'json','formatversion':2}
    data=fetch('https://en.wikipedia.org/w/api.php?'+urlencode(params))
    text=data.get('parse',{}).get('text','')
    if isinstance(text,dict):text=text.get('*','')
    parser=CitationLinks();parser.feed(text)
    return parser.items


def rank_references(links,question,terms):
    # Retrieval relevance is not a scientific verdict. Ties preserve citation order.
    filler={'what','when','where','which','does','that','this','with','from','have','about','they','their','into','would','could','should'}
    def words(text):return {w.rstrip('s') for w in re.findall(r'[a-z]{4,}',text.lower()) if w not in filler}
    target=words(question+' '+terms)
    scored=[];seen=set()
    for item in links:
        url=item.get('url',item.get('*',''))
        if url.startswith('http://'):url='https://'+url[7:]
        if not eligible_reference(url) or url in seen:continue
        seen.add(url)
        score=len(target & words(item.get('context','')+' '+urlparse(url).path))
        scored.append((score,url))
    return [url for score,url in sorted(scored,key=lambda row:-row[0])]


def document_resolution(requested,final,is_pdf):
    if urlparse(requested).path.lower().endswith('.pdf') and not is_pdf:raise SourceValidationError('pdf_resolved_to_html','PDF reference resolved to a non-PDF page')
    if not is_pdf and urlparse(final).path.rstrip('/')=='':raise SourceValidationError('generic_website_root','Reference resolved to a generic website root, not an article')


def research(question,terms):
    # Discover both query pools before any article read can consume the budget.
    # Mechanism-first text anchors the encyclopedia excerpt; references are interleaved.
    from itertools import zip_longest
    sources=[];groups=set();attempted=[];discovery=[];seen_pages=set();seen_urls=set()
    queries=list(dict.fromkeys([terms,question]));pools=[]
    def report():return {'question':question,'queries':queries,'publishers':sorted(groups),'discovery':discovery,'retrieval_attempts':attempted,'all_query_discovery_precedes_reference_reads':True,'not_a_truth_guarantee':True}
    for query in queries:
        try:pages=wiki_pages(query)
        except (ValueError,OSError) as error:
            details=source_error(error)
            discovery.append({'query':query,'status':'unavailable','error_type':type(error).__name__,'transport':details})
            if details.get('provider')=='wikimedia' and details.get('provider_stop'):
                raise ResearchUnavailable('Discovery provider requested a stop. No further candidate requests or media.',{**report(),'provider_pause':details}) from None
            pools.append([]);continue
        discovery.append({'query':query,'status':'retrieved','page_titles':[page.get('title','') for page in pages]})
        pools.append(pages)
    for pages in pools:
        intro=next((page for page in pages if len(page.get('extract',''))>=450),None)
        if intro:
            sources.append({'url':public_url(intro['fullurl']),'title':intro.get('title',''),'text':intro['extract'],'publisher':'wikipedia.org','extraction_method':'MediaWiki introduction API'})
            groups.add('wikipedia.org');break
    queues=[]
    for row in zip_longest(*pools):
        for query_index,page in enumerate(row):
            if page is None:continue
            page_id=page.get('pageid')
            if page_id is None or page_id in seen_pages:continue
            seen_pages.add(page_id)
            try:links=wiki_links(page_id)
            except (ValueError,OSError) as error:
                details=source_error(error)
                discovery.append({'page_id':page_id,'status':'references_unavailable','error_type':type(error).__name__,'transport':details})
                if details.get('provider')=='wikimedia' and details.get('provider_stop'):
                    raise ResearchUnavailable('Discovery provider requested a stop. No further candidate requests or media.',{**report(),'provider_pause':details}) from None
                continue
            urls=rank_references(links,question,terms)
            discovery.append({'page_id':page_id,'status':'references_ranked','citation_links':len(links),'eligible_unique_links':len(urls),'ranking_is_not_truth_verification':True})
            queues.append({'page_id':page_id,'query':queries[query_index],'urls':urls,'attempts':0})
    while len(attempted)<10 and any(item['urls'] and item['attempts']<6 for item in queues):
        for queue in queues:
            if len(attempted)>=10:break
            if queue['attempts']>=6:continue
            while queue['urls']:
                url=queue['urls'].pop(0)
                if publisher(url) not in groups and url not in seen_urls:break
            else:continue
            seen_urls.add(url);queue['attempts']+=1
            record={'requested_url':url,'discovery_page_id':queue['page_id'],'discovery_query':queue['query']};attempted.append(record)
            try:
                source=article(url);group=publisher(source['url'])
                if not eligible_reference(source['url']) or group in groups:
                    record['status']='ineligible_or_duplicate_resolved_publisher';continue
                sources.append(source);groups.add(group);record.update(status='retrieved',resolved_url=source['url'])
            except Exception as error:
                record.update(status='unreadable',error_type=type(error).__name__,transport=source_error(error));continue
            if len(groups)>=4:return sources,report()
    if len(groups)>=2:return sources,report()
    raise ResearchUnavailable('No two readable publisher groups from live research. No unsupported fallback or video.',report())


def article(url):
    # Reuse the public-source safety checks, then the Apache-licensed Trafilatura extractor.
    import trafilatura
    final,raw,_=source_bytes(url)
    document_resolution(url,final,raw.startswith(b'%PDF'))
    if raw.startswith(b'%PDF'):
        from io import BytesIO
        from pypdf import PdfReader
        reader=PdfReader(BytesIO(raw))
        if len(reader.pages)>40:raise SourceValidationError('pdf_page_limit','Source PDF exceeds40pages')
        text='\n'.join(page.extract_text() or '' for page in reader.pages)
        data={'text':text,'title':str((reader.metadata or {}).get('/Title') or '')}
        method='pypdf'
    else:
        doc=trafilatura.bare_extraction(raw,url=final,include_comments=False,include_tables=False,with_metadata=True)
        if not doc:raise SourceValidationError('no_readable_article','No readable article')
        data=doc.as_dict() if hasattr(doc,'as_dict') else dict(doc)
        method='trafilatura'
    text=re.sub(r'\s+',' ',data.get('text') or '').strip()
    if len(text)<700:raise SourceValidationError('article_too_short','Article too short for source checks')
    return {'url':final,'requested_url':url,'title':data.get('title') or '', 'text':text[:18000],
            'publisher':publisher(final),'extraction_method':method,'text_sha256':hashlib.sha256(text.encode()).hexdigest()}


def select_and_research(model,previous,endpoint='http://127.0.0.1:11434',seed=43):
    from .remote_ai import ModelOutputInvalid
    candidates,stats=questions(model,previous,endpoint,seed);audit=[]
    for item in candidates:
        report=None
        try:
            sources,report=research(item['question'],item['search_terms'])
            from .evidence import screen
            from .storyboard import source_pack
            relevant,relevance=screen(item['question'],source_pack(item['question'],sources),model,endpoint)
            report['relevance']=relevance
            if not relevant:raise ResearchUnavailable('Readable sources did not directly support the exact question and mechanism.',{'research':report})
            approved=[sources[index] for index in relevance['approved_source_indices']]
            return item['question'],approved,{'selection':stats,'candidates':candidates,'rejections':audit,'research':report,'operator_topic_or_source_input':False}
        except (ValueError,OSError) as error:
            details=error.metadata if isinstance(error,ModelOutputInvalid) else getattr(error,'diagnostics',{})
            if isinstance(error,ModelOutputInvalid):
                status='source_assessment_contract_invalid'
                details={'model_contract':details,'research':report}
            else:status='research_unavailable'
            audit.append({'question':item['question'],'status':status,'error_type':type(error).__name__,'details':details})
            if details.get('provider_pause'):
                raise ResearchUnavailable('Public discovery provider requested a stop. No further candidate requests, script or media.',{'selection':stats,'candidates':candidates,'rejections':audit,'provider_pause':details['provider_pause']}) from None
    raise ResearchUnavailable('No automatic candidate completed topic/source acceptance. Inspect failure stages; a contract failure is not a scientific evidence rejection. No video created.',{'selection':stats,'candidates':candidates,'rejections':audit})
