"""Pinned non-thinking local model check, with no inference or account access."""
import json
from urllib.request import Request,urlopen

MODEL='qwen3:4b-instruct'
MANIFEST='0edcdef34593eac1aa2be9c7d06c432dcf81945adca5eca2f27662c18f168ba0'


def read_metadata():
    with urlopen('http://127.0.0.1:11434/api/tags',timeout=10) as response:tags=json.load(response)
    installed=next((item for item in tags.get('models',[]) if item.get('name')==MODEL),None)
    request=Request('http://127.0.0.1:11434/api/show',data=json.dumps({'model':MODEL}).encode(),headers={'Content-Type':'application/json'})
    with urlopen(request,timeout=10) as response:shown=json.load(response)
    return installed,shown


def snapshot(installed,shown):
    caps=shown.get('capabilities');thinking=shown.get('thinking');values=thinking.get('values') if isinstance(thinking,dict) else None
    allowed={'completion','thinking','tools','vision','embedding','insert','speech'}
    controls={'none','low','medium','high','minimal','xhigh','max'}
    return {'manifest_matches':bool(installed and installed.get('digest')==MANIFEST),'capabilities_type':type(caps).__name__,'known_capabilities':[x for x in caps if isinstance(x,str) and x in allowed] if isinstance(caps,list) else [],'thinking_present':'thinking' in shown,'thinking_values_type':type(values).__name__,'known_thinking_values':[x for x in values if type(x) is bool or isinstance(x,str) and x in controls] if isinstance(values,list) else [],'inference_performed':False}


def inspect():
    installed,shown=read_metadata()
    with urlopen('http://127.0.0.1:11434/api/version',timeout=10) as response:version=json.load(response).get('version')
    import re
    safe=version if isinstance(version,str) and re.fullmatch(r'[0-9A-Za-z.+-]{1,40}',version) else 'unrecognized'
    return {**snapshot(installed,shown),'server_version':safe}


def probe():
    """One bounded local control test, never an episode input or truth check."""
    installed,shown=read_metadata()
    if not installed or installed.get('digest')!=MANIFEST:raise ValueError('Probe requires the inspected pinned instruct manifest')
    payload={'model':MODEL,'prompt':'Return only the JSON object with ready set to true.','format':{'type':'object','properties':{'ready':{'type':'boolean'}},'required':['ready'],'additionalProperties':False},'stream':False,'think':False,'options':{'num_ctx':1024,'num_predict':64,'temperature':0,'seed':1,'num_thread':4}}
    request=Request('http://127.0.0.1:11434/api/generate',data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'})
    with urlopen(request,timeout=120) as response:result=json.load(response)
    text=result.get('response','');thinking=result.get('thinking','')
    try:obj=json.loads(text)
    except (ValueError,TypeError):obj=None
    accepted=isinstance(obj,dict) and set(obj)=={'ready'} and obj['ready'] is True and isinstance(thinking,str) and not thinking and result.get('done') is True and result.get('done_reason')=='stop'
    tokens=result.get('eval_count');reason=result.get('done_reason')
    return {'accepted':accepted,'manifest_verified':True,'inference_performed':True,'thinking_characters':len(thinking) if isinstance(thinking,str) else -1,'response_characters':len(text) if isinstance(text,str) else -1,'output_tokens':tokens if type(tokens) is int else None,'done_reason':reason if reason in {'stop','length','load'} else 'unrecognized','episode_content_supplied':False}


def verify():
    installed,shown=read_metadata()
    if not installed or installed.get('digest')!=MANIFEST:raise ValueError('Local model manifest differs from the inspected non-thinking instruct model')
    caps=shown.get('capabilities')
    if not isinstance(caps,list) or 'completion' not in caps or 'thinking' in caps:raise ValueError('Pinned instruct model has missing or conflicting capabilities')
    # The pinned provider instruct model is non-thinking. Legacy Go templates may
    # omit thinking metadata in this server version; absence alone proves nothing.
    if 'thinking' in shown and (not isinstance(shown['thinking'],dict) or shown['thinking'].get('values')!=[False]):raise ValueError('Pinned instruct model has conflicting non-thinking-only metadata')
    origin='explicit_show_metadata' if 'thinking' in shown else 'pinned_instruct_manifest_and_capabilities'
    return {'local_model':MODEL,'manifest_verified':True,'non_thinking_only':True,'thinking_control_source':origin,'inference_performed':False}


if __name__=='__main__':
    from pathlib import Path
    import sys
    root=Path(__file__).resolve().parents[2]
    if json.loads((root/'studio.json').read_text())['draft_model']!=MODEL:raise ValueError('Configured local model differs from the pinned workflow model')
    if '--probe-only' in sys.argv:
        result=probe();print(json.dumps(result));sys.exit(0 if result['accepted'] else 1)
    print(json.dumps(inspect() if '--inspect-only' in sys.argv else verify()))
