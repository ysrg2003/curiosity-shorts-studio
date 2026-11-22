"""No-input topic hypotheses and keyless research. Discovery is not truth certification."""
import hashlib
import re
from urllib.parse import urlencode,urlparse
from .planner import fetch,public_url
from .storyboard import ask

PUBLISHERS=('nasa.gov','noaa.gov','usgs.gov','nih.gov','nsf.gov','science.org','nature.com','scientificamerican.com','openstax.org','esa.int','metoffice.gov.uk','sciencefocus.com','britannica.com')


def publisher(url):
    host=(urlparse(url).hostname or '').lower()
    parts=host.split('.')
    return '.'.join(parts[-3:] if '.'.join(parts[-2:]) in {'co.uk','ac.uk','gov.uk','com.au','gov.au'} else parts[-2:])


def eligible_reference(url):
    p=urlparse(url);host=(p.hostname or '').lower()
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
    params=urlencode({'action':'query','generator':'search','gsrsearch':query,'gsrlimit':3,'prop':'extracts|info','explaintext':1,'exintro':1,'inprop':'url','format':'json'})
    data=fetch('https://en.wikipedia.org/w/api.php?'+params)
    return sorted(data.get('query',{}).get('pages',{}).values(),key=lambda page:page.get('index',999))


def wiki_links(page_id):
    links=[];continuation={}
    for _ in range(2):
        params={'action':'query','pageids':str(page_id),'prop':'extlinks','ellimit':100,'format':'json',**continuation}
        data=fetch('https://en.wikipedia.org/w/api.php?'+urlencode(params))
        for page in data.get('query',{}).get('pages',{}).values():links.extend(page.get('extlinks',[]))
        following=data.get('continue',{})
        if 'elcontinue' not in following:break
        continuation={key:following[key] for key in ('continue','elcontinue') if key in following}
    return links


def document_resolution(requested,final,is_pdf):
    if urlparse(requested).path.lower().endswith('.pdf') and not is_pdf:raise ValueError('PDF reference resolved to a non-PDF page')
    if not is_pdf and urlparse(final).path.rstrip('/')=='':raise ValueError('Reference resolved to a generic website root, not an article')


def research(question,terms):
    sources=[];groups=set();attempted=[];discovery=[];seen_pages=set();seen_urls=set()
    def report():return {'question':question,'queries':list(dict.fromkeys([terms,question])),'publishers':sorted(groups),'discovery':discovery,'retrieval_attempts':attempted,'not_a_truth_guarantee':True}
    for query in dict.fromkeys([terms,question]):
        if len(attempted)>=10:break
        try:pages=wiki_pages(query)
        except (ValueError,OSError) as error:
            discovery.append({'query':query,'status':'unavailable','error_type':type(error).__name__});continue
        discovery.append({'query':query,'status':'retrieved','page_titles':[page.get('title','') for page in pages]})
        for page in pages:
            page_id=page.get('pageid')
            if page_id is None or page_id in seen_pages:continue
            seen_pages.add(page_id)
            if len(page.get('extract',''))>=450 and 'wikipedia.org' not in groups:
                sources.append({'url':public_url(page['fullurl']),'title':page.get('title',''),'text':page['extract'],'publisher':'wikipedia.org','extraction_method':'MediaWiki introduction API'})
                groups.add('wikipedia.org')
            if len(attempted)>=10:break
            try:links=wiki_links(page_id)
            except (ValueError,OSError) as error:
                discovery.append({'page_id':page_id,'status':'references_unavailable','error_type':type(error).__name__});continue
            page_attempts=0
            for item in links:
                url=item.get('*',item.get('url',''))
                if url.startswith('http://'):url='https://'+url[7:]
                if len(attempted)>=10 or page_attempts>=6:break
                if not eligible_reference(url) or publisher(url) in groups or url in seen_urls:continue
                seen_urls.add(url);page_attempts+=1
                record={'requested_url':url};attempted.append(record)
                try:
                    source=article(url);group=publisher(source['url'])
                    if not eligible_reference(source['url']) or group in groups:
                        record['status']='ineligible_or_duplicate_resolved_publisher';continue
                    sources.append(source);groups.add(group);record.update(status='retrieved',resolved_url=source['url'])
                except Exception as error:
                    record.update(status='unreadable',error_type=type(error).__name__);continue
                if len(groups)>=4:return sources,report()
    if len(groups)>=2:return sources,report()
    raise ResearchUnavailable('No two readable publisher groups from live research. No unsupported fallback or video.',report())


def article(url):
    # Reuse the public-source safety checks, then the Apache-licensed Trafilatura extractor.
    from urllib.request import Request,build_opener
    from .planner import PublicRedirects,USER_AGENT
    import trafilatura
    public_url(url)
    with build_opener(PublicRedirects()).open(Request(url,headers={'User-Agent':USER_AGENT}),timeout=25) as response:
        final=public_url(response.url);raw=response.read(2_000_001)
        if len(raw)>2_000_000:raise ValueError('Source exceeds2MB')
    document_resolution(url,final,raw.startswith(b'%PDF'))
    if raw.startswith(b'%PDF'):
        from io import BytesIO
        from pypdf import PdfReader
        reader=PdfReader(BytesIO(raw))
        if len(reader.pages)>40:raise ValueError('Source PDF exceeds40pages')
        text='\n'.join(page.extract_text() or '' for page in reader.pages)
        data={'text':text,'title':str((reader.metadata or {}).get('/Title') or '')}
        method='pypdf'
    else:
        doc=trafilatura.bare_extraction(raw,url=final,include_comments=False,include_tables=False,with_metadata=True)
        if not doc:raise ValueError('No readable article')
        data=doc.as_dict() if hasattr(doc,'as_dict') else dict(doc)
        method='trafilatura'
    text=re.sub(r'\s+',' ',data.get('text') or '').strip()
    if len(text)<700:raise ValueError('Article too short for source checks')
    return {'url':final,'requested_url':url,'title':data.get('title') or '', 'text':text[:18000],
            'publisher':publisher(final),'extraction_method':method,'text_sha256':hashlib.sha256(text.encode()).hexdigest()}


def select_and_research(model,previous,endpoint='http://127.0.0.1:11434',seed=43):
    from .remote_ai import ModelOutputInvalid
    candidates,stats=questions(model,previous,endpoint,seed);audit=[]
    for item in candidates:
        try:
            sources,report=research(item['question'],item['search_terms'])
            from .evidence import screen
            from .storyboard import source_pack
            relevant,relevance=screen(item['question'],source_pack(item['question'],sources),model,endpoint)
            report['relevance']=relevance
            if not relevant:raise ResearchUnavailable('Readable sources did not directly support the exact question and mechanism.',{'research':report})
            approved=[sources[index] for index in relevance['approved_source_indices']]
            return item['question'],approved,{'selection':stats,'candidates':candidates,'rejections':audit,'research':report,'operator_topic_or_source_input':False}
        except (ValueError,OSError) as error:audit.append({'question':item['question'],'status':'research_unavailable','error_type':type(error).__name__,'details':error.metadata if isinstance(error,ModelOutputInvalid) else getattr(error,'diagnostics',{})})
    raise ResearchUnavailable('All automatic topic candidates lacked sufficient retrieved evidence. No video created.',{'selection':stats,'candidates':candidates,'rejections':audit})
