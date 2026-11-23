"""No-input topic hypotheses and keyless research. Discovery is not truth certification."""
import hashlib
import re
from urllib.parse import urlencode,urlparse,parse_qs
from html.parser import HTMLParser
from .planner import fetch,public_url,source_bytes,source_error,SourceValidationError
from .storyboard import ask

from functools import lru_cache
import unicodedata

STOP = frozenset('a an and are as at be because been being by can could did do does for from had has have how i if in into is it its may might not of on or our should so than that the their them there these they this those to under up was we were what when where which while who why will with without would you your'.split())


@lru_cache(maxsize=1)
def stemmer():
    import snowballstemmer
    return snowballstemmer.stemmer('english')


@lru_cache(maxsize=4096)
def tokens(text):
    words=re.findall(r'[a-z]{3,}',unicodedata.normalize('NFKC',text).casefold())
    return tuple(stemmer().stemWords([word for word in words if word not in STOP]))


def rank_texts(query,texts):
    """BM25L avoids negative common-term weights in tiny candidate collections."""
    from rank_bm25 import BM25L
    rows=[list(tokens(text)) for text in texts]
    if not rows or not any(rows):return [0.0]*len(rows)
    scorer=BM25L(rows)
    return [round(float(score),6) for score in scorer.get_scores(list(tokens(query)))]


def subject_overlap(subject,text):
    wanted=set(tokens(subject))
    return len(wanted&set(tokens(text)))/max(1,len(wanted))


PUBLISHERS=('nasa.gov','noaa.gov','usgs.gov','nih.gov','nsf.gov','science.org','nature.com','scientificamerican.com','openstax.org','esa.int','metoffice.gov.uk','sciencefocus.com','britannica.com')


def publisher(url):
    host=(urlparse(url).hostname or '').lower()
    parts=host.split('.')
    return '.'.join(parts[-3:] if '.'.join(parts[-2:]) in {'co.uk','ac.uk','gov.uk','com.au','gov.au'} else parts[-2:])


def eligible_reference(url):
    p=urlparse(url);host=(p.hostname or '').lower()
    if p.path.rstrip('/').lower().split('/')[-1] in {'search','query','query.fcgi','entrez'} or set(parse_qs(p.query)) & {'q','query','search','term'}:return False
    return p.scheme=='https' and (host.endswith(('.edu','.gov','.ac.uk','.edu.au','.ac.nz')) or any(host==root or host.endswith('.'+root) for root in PUBLISHERS))


def questions(model,previous,endpoint='http://127.0.0.1:11434',seed=43):
    from .remote_ai import ModelOutputInvalid
    schema={'type':'object','properties':{'candidates':{'type':'array','minItems':3,'maxItems':3,'items':{'type':'object','properties':{'question':{'type':'string','minLength':10,'maxLength':110},'search_terms':{'type':'string','minLength':3,'maxLength':150},'subject_query':{'type':'string','minLength':3,'maxLength':80}},'required':['question','search_terms','subject_query']}}},'required':['candidates']}
    attempts=[]
    for attempt in range(2):
        try:
            data,stats=ask(model,'Propose exactly 3 distinct, visually explainable everyday science questions for a playful English educational cartoon. Choose from physics, chemistry, astronomy, weather or ordinary nonmedical biology. Do not propose medical advice, disease, politics, product claims or current events. These are unverified research hypotheses, not factual answers. Avoid the supplied previous topics. Each question is 10 to 110 characters. subject_query is a 1 to 6 word encyclopedia-style subject phrase, 3 to 80 characters, naming the observable subject of the question, not its proposed cause. Include a domain qualifier if ambiguous. search_terms is 3 to 150 characters and names a proposed mechanism as an unverified search hypothesis, never an established fact. Return JSON only. /no_think',{'previous_topics':previous[-100:],'proposal_variation':attempt+1,'revision_feedback':attempts[-1].get('rejected') if attempts else ''},schema,endpoint,seed+attempt)
        except ModelOutputInvalid as error:
            attempts.append({'attempt':attempt+1,'rejected':'schema_invalid','response_shape':error.metadata});continue
        result=[];checks=[]
        for item in data.get('candidates',[]):
            q=str(item.get('question','')).strip();terms=str(item.get('search_terms','')).strip();subject=str(item.get('subject_query','')).strip()
            repeated=duplicate(q,previous);valid=10<=len(q)<=110 and 3<=len(terms)<=150 and 3<=len(subject)<=80 and 1<=len(subject.split())<=6 and bool(research_words(q)&research_words(subject)) and not repeated
            checks.append({'question_characters':len(q),'search_characters':len(terms),'subject_characters':len(subject),'subject_is_unverified_query':True,'duplicate':repeated,'accepted':valid})
            if valid:result.append({'question':q,'search_terms':terms,'subject_query':subject})
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


def wiki_article(page_id):
    """One explicitly bounded full-page extract, not an intro mistaken for evidence."""
    params={'action':'query','pageids':str(page_id),'prop':'extracts|info',
            'explaintext':1,'inprop':'url','maxlag':5,'format':'json'}
    data=fetch('https://en.wikipedia.org/w/api.php?'+urlencode(params))
    pages=data.get('query',{}).get('pages',{})
    page=pages.get(str(page_id),{})
    if page.get('pageid')!=page_id or len(page.get('extract',''))<450:
        raise SourceValidationError('encyclopedia_extract_missing','No matching readable full-page extract')
    text=page['extract'][:18000]
    return {'url':public_url(page['fullurl']),'title':page.get('title',''),'text':text,
            'publisher':'wikipedia.org','source_scope':'encyclopedia_article_excerpt',
            'extraction_method':'MediaWiki bounded full-page extract API'}


class ParagraphCitations(HTMLParser):
    """Associate bibliography IDs with the surrounding original body paragraph."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.blocks=[];self.parts=[];self.targets=[];self.contexts={};self.skip=0
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if tag in {'script','style'}:self.skip+=1
        if tag in {'p','li','dd'}:
            self.blocks.append((tag,self.parts,self.targets));self.parts=[];self.targets=[]
        if tag=='a' and attrs.get('href','').startswith('#cite_note'):
            self.targets.append(attrs['href'][1:])
    def handle_data(self,text):
        if not self.skip:self.parts.append(text)
    def handle_endtag(self,tag):
        if tag in {'script','style'}:self.skip=max(0,self.skip-1)
        if self.blocks and tag==self.blocks[-1][0]:
            context=re.sub(r'\s+',' ',' '.join(self.parts)).strip()[:1800]
            for target in self.targets:
                existing=self.contexts.setdefault(target,[])
                if context and context not in existing and len(existing)<3:existing.append(context)
            _,self.parts,self.targets=self.blocks.pop()


class CitationLinks(HTMLParser):
    """Original citation titles plus their in-article paragraph context, not facts."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.items=[];self.depth=0;self.urls=[];self.parts=[];self.citation_id=''
    def feed(self,data):
        super().feed(data)
        paragraphs=ParagraphCitations();paragraphs.feed(data)
        for item in self.items:
            item['citation_context']=item['context']
            item['body_context']=' '.join(paragraphs.contexts.get(item['citation_id'],[]))
            item['context']=(item['body_context']+' '+item['citation_context']).strip()[:6600]
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if tag=='li':
            if self.depth:self.depth+=1
            elif attrs.get('id','').startswith('cite_note'):
                self.depth=1;self.urls=[];self.parts=[];self.citation_id=attrs['id']
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
                self.items.extend({'url':url,'context':context,'citation_id':self.citation_id} for url in dict.fromkeys(self.urls))


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


def research_words(text):
    filler={'why','how','who','can','are','the','and','for','you','your','our','its','was','were','not','but','than','then','what','when','where','which','does','that','this','with','from','have','about','they','their','into','would','could','should','without'}
    return {word.replace('colour','color').rstrip('s') for word in re.findall(r'[a-z]{3,}',text.lower()) if word not in filler}


def document_rank(source,question,subject):
    # Discovery ranking only. Scientific acceptance remains a later independent gate.
    target=research_words(question+' '+subject)
    title=research_words(source.get('title',''))
    body=research_words(source['text'])
    return 4*len(target&title)+len(target&body)


def research(question,terms,subject_query=""):
    # Discover every query before any article read. Search hypotheses are not facts.
    sources=[];groups=set();attempted=[];discovery=[];seen_pages=set();seen_urls=set()
    queries=list(dict.fromkeys(([subject_query] if subject_query else [])+[terms,question]));pools=[]
    def report():return {'question':question,'queries':queries,'publishers':sorted(groups),'discovery':discovery,'retrieval_attempts':attempted,'all_query_discovery_precedes_reference_reads':True,'not_a_truth_guarantee':True,'retrieval_model':'cross-encoder/ms-marco-MiniLM-L6-v2','retrieval_window_tokens':512,'retrieval_logits_are_not_probabilities':True}
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
    pages=[]
    for query_index,pool in enumerate(pools):
        for page in pool:
            page_id=page.get('pageid')
            if page_id is None or page_id in seen_pages:continue
            seen_pages.add(page_id)
            pages.append({**page,'query_index':query_index})
    from .entailment import relevance_scores
    page_passages=[(page.get('title','')+'. '+page.get('extract',''))[:6000] or 'Empty discovery result.' for page in pages]
    weights=relevance_scores(question,page_passages)
    if subject_query:
        subject_weights=relevance_scores(subject_query,page_passages)
        weights=[(a+b)/2 for a,b in zip(weights,subject_weights)]
    ordered=sorted(zip(weights,pages),key=lambda row:-row[0])
    # A fixed retrieval shortlist, never a scientific acceptance threshold.
    pages=[page for _,page in ordered[:5]]
    for score,page in ordered:
        discovery.append({'page_id':page['pageid'],'page_title':page.get('title',''),
                          'status':'semantic_retrieval_candidate' if page in pages else 'outside_semantic_shortlist',
                          'retrieval_logit':score,'retrieval_only':True,'query':queries[page['query_index']]})
    intro=next((page for page in pages if len(page.get('extract',''))>=450),None)
    if intro:
        try:
            encyclopedia=wiki_article(intro['pageid'])
        except (ValueError,OSError) as error:
            details=source_error(error)
            discovery.append({'page_id':intro['pageid'],'status':'full_extract_unavailable','transport':details})
            if details.get('provider')=='wikimedia' and details.get('provider_stop'):
                raise ResearchUnavailable('Discovery provider requested a stop. No further candidate requests or media.',{**report(),'provider_pause':details}) from None
            # The original intro remains explicitly scoped, never relabeled full text.
            encyclopedia={'url':public_url(intro['fullurl']),'title':intro.get('title',''),'text':intro['extract'],'publisher':'wikipedia.org','extraction_method':'MediaWiki introduction API','source_scope':'encyclopedia_introduction'}
        sources.append(encyclopedia);groups.add('wikipedia.org')
    queues=[];reference_candidates=[]
    for page in pages:
        page_id=page['pageid'];query_index=page['query_index']
        try:links=wiki_links(page_id)
        except (ValueError,OSError) as error:
            details=source_error(error)
            discovery.append({'page_id':page_id,'status':'references_unavailable','error_type':type(error).__name__,'transport':details})
            if details.get('provider')=='wikimedia' and details.get('provider_stop'):
                raise ResearchUnavailable('Discovery provider requested a stop. No further candidate requests or media.',{**report(),'provider_pause':details}) from None
            continue
        urls=rank_references(links,question,terms)
        context={item.get('url',item.get('*','')).replace('http://','https://',1):item.get('context','') for item in links}
        eligible=[]
        for url in urls:
            citation=context.get(url,'')
            eligible.append(url)
        discovery.append({'page_id':page_id,'status':'references_ranked','citation_links':len(links),'eligible_unique_links':len(urls),
                          'retrieval_candidate_links':len(eligible),'ranking_is_not_truth_verification':True})
        queue={'page_id':page_id,'query':queries[query_index],'urls':eligible,'attempts':0};queues.append(queue)
        for url in eligible:reference_candidates.append({'url':url,'queue':queue,'text':context.get(url,'')+' '+urlparse(url).path})
    # Cheap lexical pre-ranking only limits work for the semantic component.
    lexical=rank_texts((subject_query or question)+' '+question,[item['text'] for item in reference_candidates])
    reference_candidates=[item for _,item in sorted(zip(lexical,reference_candidates),key=lambda row:-row[0])][:120]
    ref_weights=relevance_scores(question,[(item['text'] or 'Citation URL without context.')[:6000] for item in reference_candidates])
    reference_candidates=[{**item,'retrieval_logit':score} for score,item in sorted(zip(ref_weights,reference_candidates),key=lambda row:-row[0])]
    # One globally ranked queue, while retaining each page's six-read cap and the
    # overall ten-read cap. An irrelevant query pool no longer gets equal turns.
    while len(attempted)<10:
        candidate=next((item for item in reference_candidates if item['url'] not in seen_urls and item['queue']['attempts']<6),None)
        if candidate is None:break
        queue=candidate['queue'];url=candidate['url']
        seen_urls.add(url);queue['attempts']+=1
        record={'requested_url':url,'discovery_page_id':queue['page_id'],'discovery_query':queue['query'],'retrieval_logit':candidate['retrieval_logit'],'retrieval_not_a_truth_guarantee':True};attempted.append(record)
        try:
            source=article(url);group=publisher(source['url'])
            if not eligible_reference(source['url']):
                record['status']='ineligible_or_duplicate_resolved_publisher';continue
            sources.append(source);groups.add(group);record.update(status='retrieved',resolved_url=source['url'],title=source.get('title',''),source_scope=source.get('source_scope','article_excerpt'),characters=len(source['text']))
        except Exception as error:
            record.update(status='unreadable',error_type=type(error).__name__,transport=source_error(error));continue
    # Read the same bounded queue before choosing one candidate per publisher.
    # The first readable but unrelated paper must not suppress its better references.
    encyclopedias=[source for source in sources if publisher(source['url'])=='wikipedia.org']
    articles=[source for source in sources if publisher(source['url'])!='wikipedia.org']
    from .storyboard import passage_rank
    article_weights=[passage_rank(question,source['text'],source.get('title','')) for source in articles]
    weighted=sorted(zip(article_weights,articles),key=lambda row:-row[0])
    ranked=[source for _,source in weighted]
    weight_by_url={source['url']:weight for weight,source in weighted}
    selected=encyclopedias[:1];selected_groups={publisher(source['url']) for source in selected}
    candidates=[{'url':source['url'],'title':source.get('title',''),'publisher':publisher(source['url']),
                 'source_scope':source.get('source_scope','article_excerpt'),
                 'retrieval_rank':weight_by_url[source['url']]} for source in ranked]
    for source in ranked:
        group=publisher(source['url'])
        if group in selected_groups:continue
        selected.append(source);selected_groups.add(group)
        if len(selected)>=4:break
    sources=selected;groups=selected_groups
    if len(groups)>=2:return sources,{**report(),'document_candidates':candidates,'subject_query_is_not_fact':True}

    raise ResearchUnavailable('No two readable publisher groups from live research. No unsupported fallback or video.',report())


def pubmed_abstract(url):
    """Use the documented public Europe PMC record endpoint, not PubMed page chrome."""
    from .planner import TextOnly
    parsed=urlparse(url)
    if parsed.hostname!='pubmed.ncbi.nlm.nih.gov' or not re.fullmatch(r'/[0-9]{1,10}/?',parsed.path):
        raise SourceValidationError('not_pubmed_record','Not a numeric PubMed record URL')
    public_url(url)
    identifier=parsed.path.strip('/')
    endpoint='https://www.ebi.ac.uk/europepmc/webservices/rest/article/MED/'+identifier+'?'+urlencode({'resultType':'core','format':'json'})
    data=fetch(endpoint)
    if not isinstance(data,dict):raise SourceValidationError('abstract_record_shape','Structured abstract response is not a record')
    record=data.get('result',{})
    if not isinstance(record,dict):raise SourceValidationError('abstract_record_shape','Structured abstract response is not a record')
    if data.get('hitCount')!=1 or record.get('source')!='MED' or record.get('id')!=identifier or record.get('pmid')!=identifier:
        raise SourceValidationError('abstract_identity_mismatch','Structured abstract identity did not match requested record')
    abstract=record.get('abstractText','')
    if not isinstance(abstract,str) or not abstract.strip():
        raise SourceValidationError('abstract_missing','Structured record contains no abstract')
    parser=TextOnly();parser.feed(abstract)
    text=re.sub(r'\s+',' ',' '.join(parser.parts)).strip()
    # Keep the existing text-size floor. Do not pad abstracts with metadata.
    if len(text)<700:raise SourceValidationError('abstract_too_short','Abstract too short for source checks')
    return {'url':url,'requested_url':url,'retrieval_url':endpoint,'pmid':identifier,
            'title':record.get('title',''),'text':text[:18000],'publisher':publisher(url),
            'source_scope':'abstract_only','publication_year':record.get('pubYear',''),
            'extraction_method':'Europe PMC structured PubMed abstract API',
            'text_sha256':hashlib.sha256(text.encode()).hexdigest()}


def article(url):
    if urlparse(url).hostname=='pubmed.ncbi.nlm.nih.gov':return pubmed_abstract(url)
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
            'publisher':publisher(final),'source_scope':'article_excerpt','extraction_method':method,'text_sha256':hashlib.sha256(text.encode()).hexdigest()}


def select_and_research(model,previous,endpoint='http://127.0.0.1:11434',seed=43):
    from .remote_ai import ModelOutputInvalid
    candidates,stats=questions(model,previous,endpoint,seed);audit=[]
    for item in candidates:
        report=None
        try:
            sources,report=research(item['question'],item['search_terms'],item.get('subject_query',''))
            from .evidence import screen,plan_sources
            from .storyboard import source_pack
            packed=source_pack(item['question'],sources,semantic=True)
            plan_ok,source_plan=plan_sources(item['question'],packed,model,endpoint)
            report['source_scope_plan']=source_plan
            report['packed_original_sources']=packed
            if not plan_ok:raise ResearchUnavailable('Original sources did not complete pre-answer scope planning.',{'research':report})
            planned=[{**source,**({'source_scope_plan':source_plan['selected_original_paths']} if index==0 else {})} for index,source in enumerate(packed)]
            relevant,relevance=screen(item['question'],planned,model,endpoint)
            report['relevance']=relevance
            if not relevant:raise ResearchUnavailable('Readable sources did not directly support the exact question and mechanism.',{'research':report})
            approved=[{**sources[index],'text':packed[index]['text'],**({'document_opening':packed[index]['document_opening']} if packed[index].get('document_opening') else {})} for index in relevance['approved_source_indices']]
            return item['question'],approved,{'selection':stats,'candidates':candidates,'rejections':audit,'research':report,'operator_topic_or_source_input':False}
        except (ValueError,OSError) as error:
            details=error.metadata if isinstance(error,ModelOutputInvalid) else getattr(error,'diagnostics',{})
            if isinstance(error,ModelOutputInvalid):
                status='source_assessment_contract_invalid'
                details={'model_contract':details,'untrusted_original_output':error.model_output,'research':report}
            else:status='research_unavailable'
            audit.append({'question':item['question'],'status':status,'error_type':type(error).__name__,'details':details})
            if details.get('provider_pause'):
                raise ResearchUnavailable('Public discovery provider requested a stop. No further candidate requests, script or media.',{'selection':stats,'candidates':candidates,'rejections':audit,'provider_pause':details['provider_pause']}) from None
    raise ResearchUnavailable('No automatic candidate completed topic/source acceptance. Inspect failure stages; a contract failure is not a scientific evidence rejection. No video created.',{'selection':stats,'candidates':candidates,'rejections':audit})
