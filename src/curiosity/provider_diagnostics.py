"""Safe structural response diagnostics. Never retain text, URLs or identifiers."""
FINISH={'STOP','MAX_TOKENS','SAFETY','RECITATION','LANGUAGE','OTHER','BLOCKLIST','PROHIBITED_CONTENT','SPII','MALFORMED_FUNCTION_CALL','IMAGE_SAFETY','UNEXPECTED_TOOL_CALL','TOO_MANY_TOOL_CALLS','FINISH_REASON_UNSPECIFIED'}
BLOCK={'SAFETY','OTHER','BLOCKLIST','PROHIBITED_CONTENT','BLOCK_REASON_UNSPECIFIED'}


def shape(body):
    if not isinstance(body,dict):return {'json_object':False}
    candidates=body.get('candidates');candidates=candidates if isinstance(candidates,list) else []
    rows=[]
    for candidate in candidates[:4]:
        if not isinstance(candidate,dict):continue
        content=candidate.get('content');content=content if isinstance(content,dict) else {}
        parts=content.get('parts');parts=parts if isinstance(parts,list) else []
        metadata=candidate.get('groundingMetadata');metadata=metadata if isinstance(metadata,dict) else {}
        reason=candidate.get('finishReason')
        rows.append({'finish_reason':reason if reason in FINISH else 'unrecognized_or_missing','parts_count':len(parts),'text_present':any(isinstance(p,dict) and isinstance(p.get('text'),str) and bool(p['text'].strip()) for p in parts),'grounding_chunks_count':len(metadata.get('groundingChunks') or []),'search_query_count':len(metadata.get('webSearchQueries') or [])})
    feedback=body.get('promptFeedback');feedback=feedback if isinstance(feedback,dict) else {}
    block=feedback.get('blockReason')
    return {'json_object':True,'candidate_count':len(candidates),'candidates':rows,'prompt_block_reason':block if block in BLOCK else 'unrecognized_or_missing','error_object_present':isinstance(body.get('error'),dict)}


def install(router):
    adapter=router.adapters.get('google_gemini')
    if adapter is None or not hasattr(adapter,'_body'):return
    original=adapter._body
    def read(response):
        body=original(response)
        router._curiosity_response_shape=shape(body)
        return body
    adapter._body=read
