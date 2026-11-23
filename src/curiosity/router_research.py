"""Model-assisted URL discovery. Generated URLs are leads, never evidence."""
from urllib.parse import urlparse
from .storyboard import ask,passage_rank
from .autonomy import article,eligible_reference,publisher,ResearchUnavailable
from .planner import source_error


def discover(question,terms,subject,model,endpoint):
    schema={'type':'object','required':['candidates'],'properties':{'candidates':{'type':'array','minItems':4,'maxItems':8,'items':{'type':'object','required':['url'],'additionalProperties':False,'properties':{'url':{'type':'string','minLength':12,'maxLength':500}}}}}}
    result,stats=ask(model,'Suggest 4 to 8 exact existing HTTPS educational article URLs that could directly explain the requested everyday science question. Prefer university, government, OpenStax and encyclopedia articles. Use multiple independent publishers. These are untrusted discovery leads, not verified citations. Do not invent a source title, quote, DOI or finding. Never give a search URL, site homepage, login, API endpoint or URL carrying credentials. A later independent reader will reject missing/unrelated articles. Return only JSON. /no_think',{'question':question,'subject':subject,'mechanism_search_hypothesis_not_fact':terms},schema,endpoint,57)
    attempts=[];sources=[];seen=set()
    for lead in result['candidates']:
        url=lead['url'];p=urlparse(url)
        record={'requested_url':url,'generated_url_is_unverified':True};attempts.append(record)
        if url in seen or p.scheme!='https' or p.username or p.password or p.query or p.fragment or not eligible_reference(url):
            record['status']='duplicate_or_ineligible';continue
        seen.add(url)
        try:
            source=article(url)
            if not eligible_reference(source['url']):record['status']='ineligible_resolved_publisher';continue
            record.update(status='retrieved',resolved_url=source['url'],title=source.get('title',''),characters=len(source['text']),source_scope=source.get('source_scope'))
            sources.append(source)
        except (ValueError,OSError) as error:record.update(status='unreadable',error_type=type(error).__name__,transport=source_error(error))
    ranked=sorted(sources,key=lambda item:-passage_rank(question,item['text'],item.get('title','')))
    chosen=[];groups=set()
    for source in ranked:
        group=publisher(source['url'])
        if group in groups:continue
        chosen.append(source);groups.add(group)
        if len(chosen)>=4:break
    report={'discovery_backend':'prepared-router-url-leads','generation':stats,'generated_urls_are_not_facts':True,'retrieval_attempts':attempts,'document_candidates':[{'url':s['url'],'title':s.get('title','')} for s in ranked],'publishers':sorted(groups),'operator_topic_or_source_input':False,'not_a_truth_guarantee':True}
    if len(groups)<2:raise ResearchUnavailable('Fewer than two readable independent publishers from untrusted model URL leads.',report)
    return chosen,report
