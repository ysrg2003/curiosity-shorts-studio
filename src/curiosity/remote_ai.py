"""Free-only model calls through the owner's pinned public provider adapter."""
import json
from copy import deepcopy
import os
from decimal import Decimal
from functools import lru_cache
from urllib.request import urlopen

MODEL='openrouter/free'


@lru_cache(maxsize=1)
def check_free_catalog():
    with urlopen('https://openrouter.ai/api/v1/models',timeout=25) as response:data=json.load(response)
    model=next((item for item in data.get('data',[]) if item.get('id')==MODEL),None)
    if not model or not model.get('pricing'):raise ValueError('Free router is unavailable in the live model catalog')
    for value in model['pricing'].values():
        if value is not None and Decimal(str(value))!=0:raise ValueError('Model pricing is no longer zero. No request sent.')
    return True


def strict_schema(schema):
    result=deepcopy(schema)
    def visit(value):
        if isinstance(value,dict):
            if value.get('type')=='object':
                value['additionalProperties']=False
                value['required']=list(value.get('properties',{}))
            for child in value.values():visit(child)
        elif isinstance(value,list):
            for child in value:visit(child)
    visit(result);return result


def request(prompt,system,schema=None,json_mode=False):
    key=os.environ.get('OPENROUTER_API_KEY','').strip()
    if not key:raise ValueError('Missing OPENROUTER_API_KEY Actions secret. Never put its value in code or logs.')
    check_free_catalog()
    from ai_router.providers.openai_compatible import OpenAICompatibleAdapter
    profile={'max_tokens_field':'max_tokens','max_tokens':5000}
    if schema:profile['response_format']={'type':'json_schema','json_schema':{'name':'curiosity_response','schema':strict_schema(schema),'strict':True}}
    elif json_mode:profile['response_format']='json_object'
    else:profile.update(response_format='none',response_parser='text_envelope')
    try:
        result=OpenAICompatibleAdapter('openrouter','https://openrouter.ai/api/v1').complete_json(
            model=MODEL,secret=key,system_prompt=system,user_prompt=prompt,
            timeout_seconds=180,supports_response_format=bool(schema or json_mode),invocation_profile=profile)
    except Exception as error:
        status=getattr(error,'status_code',None)
        status=status if isinstance(status,int) and 100<=status<=599 else 'unavailable'
        category=getattr(error,'error_class','unavailable')
        allowed={'auth','authentication','rate_limit','quota','transient','invalid_or_unknown','invalid_request','permission','unavailable','plan_or_credit'}
        category=category if category in allowed else 'unavailable'
        reason='not_classified'
        try:
            body=json.loads(str(error));message=str(body.get('error',{}).get('message','')).lower()
            if 'data policy' in message or 'privacy setting' in message:reason='provider_data_policy_block'
            elif 'response_format' in message or 'json_schema' in message:reason='response_format_rejected'
            elif 'no endpoints' in message:reason='no_matching_free_endpoint'
            elif status==401:reason='authentication_rejected'
            elif status==429:reason='rate_or_quota_limit'
        except (ValueError,TypeError,AttributeError):pass
        raise RuntimeError(f'Free model request failed: HTTP={status}, category={category}, reason={reason}. No paid model, paid tool or alternate key was attempted.') from None
    cost=result.usage.get('cost')
    if cost is not None and Decimal(str(cost))!=0:raise RuntimeError('Unexpected nonzero model cost. Stop all further model calls and inspect account activity.')
    output=result.payload if schema or json_mode else result.payload['text']
    usage={name:int(result.usage[name]) for name in ('prompt_tokens','completion_tokens','total_tokens') if isinstance(result.usage.get(name),int)}
    if cost is not None:usage['cost']=str(Decimal(str(cost)))
    return output,{'backend':'openrouter-free','model':MODEL,'usage':usage,'paid_fallback_allowed':False}
