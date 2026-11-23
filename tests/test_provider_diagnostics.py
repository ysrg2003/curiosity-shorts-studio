import json
from curiosity.provider_diagnostics import shape


def test_no_text_failure_keeps_only_structure():
    result=shape({'candidates':[{'finishReason':'SAFETY','groundingMetadata':{'webSearchQueries':['PRIVATE QUERY'],'groundingChunks':[{'web':{'uri':'PRIVATE URL'}}]},'content':{'parts':[]}}],'promptFeedback':{'blockReason':'SAFETY','private':'HIDDEN'}})
    assert result['candidates'][0]['finish_reason']=='SAFETY'
    assert result['candidates'][0]['text_present'] is False
    assert result['candidates'][0]['search_query_count']==1
    assert 'PRIVATE' not in json.dumps(result) and 'HIDDEN' not in json.dumps(result)


def test_untrusted_reason_cannot_enter_diagnostics():
    data=shape({'candidates':[{'finishReason':'secret-value','content':{'parts':[{'text':'DO NOT COPY'}]}}]})
    assert data['candidates'][0]['text_present'] and 'secret-value' not in json.dumps(data) and 'DO NOT COPY' not in json.dumps(data)
