"""Free-only calls through the owner's pinned public adapter, with typed output checks."""
import json
from copy import deepcopy
import os
import sys
import time
from decimal import Decimal
from urllib.request import urlopen

MODEL='particle-ai/particle-1:free'
# Documented free cap is 20 requests per minute: keep at least 3.2 s between inference requests.
MIN_SPACING_SECONDS=3.2
RETRY_AFTER_PAUSE_CAP_SECONDS=10
_pacing={'last':None}
_log=[]  # redacted per-request trail: number, calling stage (function names only), http status, spacing


def calling_stage():
    """Names of the nearest callers outside this module. Names only, never arguments or content."""
    names=[];frame=sys._getframe(1)
    while frame and len(names)<3:
        if frame.f_globals.get('__name__')!=__name__ and not frame.f_globals.get('__name__','').startswith(('pytest','_pytest','pluggy')):
            names.append(frame.f_code.co_name)
        frame=frame.f_back
    return '<'.join(names) or 'unknown'
_sleep=time.sleep
_clock=time.monotonic


def pace_before_request():
    """Wait out the minimum spacing since the previous inference request started. Never retries anything."""
    now=_clock();last=_pacing['last']
    if last is not None and now-last<MIN_SPACING_SECONDS:_sleep(MIN_SPACING_SECONDS-(now-last))
    _pacing['last']=_clock()


def pause_for_retry_after(shape):
    """Pause (bounded) for a documented Retry-After before the run stops. The caller still raises: this is not a retry."""
    value=shape.get('retry_after_seconds')
    if isinstance(value,int) and value>0:_sleep(min(value,RETRY_AFTER_PAUSE_CAP_SECONDS))


class ModelOutputInvalid(ValueError):
    def __init__(self,metadata,model_output=None):
        self.metadata=metadata
        self.model_output=model_output
        super().__init__('Model output was incomplete or failed local JSON/schema validation. '+json.dumps(metadata,sort_keys=True))


class ModelRequestFailed(RuntimeError):
    def __init__(self,metadata):
        self.metadata=metadata
        super().__init__(f"Free model request failed: HTTP={metadata['http_status']}, category={metadata['category']}, reason={metadata['reason']}. No paid model, paid tool or alternate key was attempted.")


class UnexpectedModelCost(RuntimeError):pass


def check_free_catalog():
    with urlopen('https://openrouter.ai/api/v1/models',timeout=25) as response:data=json.load(response)
    model=next((item for item in data.get('data',[]) if item.get('id')==MODEL),None)
    if not MODEL.endswith(':free') or not model or not model.get('pricing'):raise ValueError('The explicit free model is unavailable in the live model catalog')
    for value in model['pricing'].values():
        if value is not None and Decimal(str(value))!=0:raise ValueError('Model pricing is no longer zero. No request sent.')
    required={'response_format','structured_outputs','reasoning_effort'}
    reasoning=model.get('reasoning') or {}
    if not required.issubset(set(model.get('supported_parameters',[]))) or reasoning.get('mandatory') is not False or not {'none','low'}.issubset(set(reasoning.get('supported_efforts') or [])):
        raise ValueError('The free model no longer advertises structured output and supported reasoning-off/low controls. No request sent.')
    return {item['id'] for item in data.get('data',[]) if isinstance(item.get('id'),str)}


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


def checked_usage(usage):
    cost=usage.get('cost')
    if cost is not None:
        try:amount=Decimal(str(cost))
        except Exception:raise UnexpectedModelCost('Cannot validate reported model cost. Stop further calls.') from None
        if not amount.is_finite() or amount!=0:raise UnexpectedModelCost('Unexpected nonzero model cost. Stop all further model calls and inspect account activity.')
    result={name:int(usage[name]) for name in ('prompt_tokens','completion_tokens','total_tokens') if isinstance(usage.get(name),int)}
    details=usage.get('completion_tokens_details') or {}
    if isinstance(details,dict) and isinstance(details.get('reasoning_tokens'),int):result['reasoning_tokens']=details['reasoning_tokens']
    if cost is not None:result['cost']=str(amount)
    return result


def object_from_text(text):
    """Extract a complete JSON object; never invent missing brackets, values or content."""
    decoder=json.JSONDecoder();candidates=[];cursor=0
    while True:
        start=text.find('{',cursor)
        if start<0:break
        try:value,end=decoder.raw_decode(text,start)
        except ValueError:raise ValueError('Incomplete or invalid JSON object') from None
        if isinstance(value,dict) and not text[end:].strip('` \t\r\n'):candidates.append(value)
        cursor=end
    if not candidates:raise ValueError('No complete terminal JSON object')
    return candidates[-1]


def request(prompt,system,schema=None,json_mode=False,effort='none'):
    if effort not in {'none','low'}:raise ValueError('Unsupported controlled reasoning profile. No request sent.')
    key=os.environ.get('OPENROUTER_API_KEY','').strip()
    if not key:raise ValueError('Missing OPENROUTER_API_KEY Actions secret. Never put its value in code or logs.')
    public_models=check_free_catalog()
    from ai_router.providers.openai_compatible import OpenAICompatibleAdapter
    shape={}
    class AuditedAdapter(OpenAICompatibleAdapter):
        def _body(self,response):
            body=super()._body(response)
            shape['http_status']=int(response.status_code);entry['http_status']=shape['http_status']
            if response.status_code==429:
                for header,name,ceiling in [('Retry-After','retry_after_seconds',604800),('X-RateLimit-Reset','rate_reset_unix_ms',4102444800000),('X-RateLimit-Limit','rate_limit',10**9),('X-RateLimit-Remaining','rate_remaining',10**9)]:
                    value=(getattr(response,'headers',{}) or {}).get(header)
                    try:number=int(value)
                    except (ValueError,TypeError):continue
                    if 0<=number<=ceiling:shape[name]=number
                metadata=(body.get('error') or {}).get('metadata') or {}
                if isinstance(metadata,dict):shape['provider_code_present']=metadata.get('provider_code') is not None
            resolved=body.get('model')
            if isinstance(public_models,set) and isinstance(resolved,str):shape['resolved_public_model']=resolved if resolved in public_models else 'unlisted'
            choices=body.get('choices') or []
            shape['choice_count']=len(choices) if isinstance(choices,list) else 0
            if choices and isinstance(choices,list) and isinstance(choices[0],dict):
                choice=choices[0];reason=choice.get('finish_reason')
                shape['finish_reason']=reason if reason in {'stop','length','content_filter','tool_calls','error'} else 'other'
                message=choice.get('message') or {}
                if isinstance(message,dict):shape['content_characters']=len(self._content_text(message.get('content')))
            if isinstance(body.get('usage'),dict):shape['usage']=checked_usage(body['usage'])
            return body
    # Use only an explicit free model whose live catalog advertises reasoning-off support.
    profile={'max_tokens_field':'max_tokens','max_tokens':12000,'reasoning_effort':effort}
    if schema:profile.update(response_format={'type':'json_schema','json_schema':{'name':'curiosity_response','schema':strict_schema(schema),'strict':True}},response_parser='json_or_text_envelope')
    elif json_mode:profile.update(response_format='json_object',response_parser='json_or_text_envelope')
    else:profile.update(response_format='none',response_parser='text_envelope')
    pace_before_request()
    entry={'request_number':len(_log)+1,'stage':calling_stage(),'http_status':None}
    _log.append(entry);shape['request_number']=entry['request_number'];shape['stage']=entry['stage']
    try:
        result=AuditedAdapter('openrouter','https://openrouter.ai/api/v1').complete_json(model=MODEL,secret=key,system_prompt=system,user_prompt=prompt,timeout_seconds=180,supports_response_format=bool(schema or json_mode),invocation_profile=profile)
    except UnexpectedModelCost:raise
    except Exception as error:
        status=getattr(error,'status_code',None) or shape.get('http_status')
        status=status if isinstance(status,int) and 100<=status<=599 else 'unavailable'
        category=getattr(error,'error_class','unavailable')
        allowed={'auth','authentication','rate_limit','quota','transient','invalid_or_unknown','invalid_request','permission','unavailable','plan_or_credit'}
        category=category if category in allowed else 'unavailable';reason='not_classified'
        try:
            body=json.loads(str(error));message=str(body.get('error',{}).get('message','')).lower()
            if 'data policy' in message or 'privacy setting' in message:reason='provider_data_policy_block'
            elif 'response_format' in message or 'json_schema' in message:reason='response_format_rejected'
            elif 'no endpoints' in message:reason='no_matching_free_endpoint'
            elif status==401:reason='authentication_rejected'
            elif status==429:reason='rate_or_quota_limit'
        except (ValueError,TypeError,AttributeError):pass
        if status==200 and category=='invalid_or_unknown':raise ModelOutputInvalid(shape) from None
        shape['requests_so_far']=len(_log);shape['recent_requests']=[dict(item) for item in _log[-5:]]
        if status==429:pause_for_retry_after(shape)
        raise ModelRequestFailed({**shape,'http_status':status,'category':category,'reason':reason}) from None
    usage=checked_usage(result.usage);output=result.payload;extracted=False
    if schema or json_mode:
        if output.get('output_type')=='text' and isinstance(output.get('text'),str):
            try:output=object_from_text(output['text']);extracted=True
            except ValueError:raise ModelOutputInvalid(shape) from None
        if not isinstance(output,dict):raise ModelOutputInvalid(shape)
        if schema:
            from jsonschema import Draft202012Validator
            if not Draft202012Validator(strict_schema(schema)).is_valid(output):raise ModelOutputInvalid(shape)
    else:output=output['text']
    return output,{'backend':'openrouter-free','model':MODEL,'usage':usage,'paid_fallback_allowed':False,'response_shape':shape,'complete_json_extracted':extracted,'reasoning_effort':effort}


def free_quota_status(minimum_requests=31):
    """Read only the documented current-key daily counter; never retain labels or account details."""
    key=os.environ.get('OPENROUTER_API_KEY','').strip()
    if not key:raise ValueError('Missing OPENROUTER_API_KEY Actions secret. No request sent.')
    import requests
    try:
        response=requests.get('https://openrouter.ai/api/v1/key',headers={'Authorization':f'Bearer {key}'},timeout=25,allow_redirects=False)
        status=int(response.status_code)
        result={'http_status':status,'daily_counter':'unknown','request_budget':'unknown','inference_performed':False}
        if status!=200:return result
        data=response.json().get('data',{})
        counter=data.get('free_model_daily_requests') or {}
        remaining=counter.get('remaining')
        if type(remaining) is int:
            result['daily_counter']='at_limit' if remaining<=0 else 'has_remaining'
            # Count1 worst case:2proposals+3relevance screens*2contract attempts+3drafts+3reviews+5visuals*3code attempts=29calls, plus2connection checks.
            result['request_budget']='sufficient_for_bounded_attempt' if remaining>=minimum_requests else 'below_conservative_reserve'
        return result
    except Exception:
        return {'http_status':'unavailable','daily_counter':'unknown','request_budget':'unknown','inference_performed':False}
