"""Pinned non-thinking local model check, with no inference or account access."""
import json
from urllib.request import Request,urlopen

MODEL='qwen3:4b-instruct'
MANIFEST='0edcdef34593eac1aa2be9c7d06c432dcf81945adca5eca2f27662c18f168ba0'


def verify():
    with urlopen('http://127.0.0.1:11434/api/tags',timeout=10) as response:tags=json.load(response)
    installed=next((item for item in tags.get('models',[]) if item.get('name')==MODEL),None)
    if not installed or installed.get('digest')!=MANIFEST:raise ValueError('Local model manifest differs from the inspected non-thinking instruct model')
    request=Request('http://127.0.0.1:11434/api/show',data=json.dumps({'model':MODEL}).encode(),headers={'Content-Type':'application/json'})
    with urlopen(request,timeout=10) as response:shown=json.load(response)
    caps=shown.get('capabilities')
    if not isinstance(caps,list) or 'completion' not in caps or 'thinking' in caps:raise ValueError('Pinned instruct model has missing or conflicting capabilities')
    # The pinned provider instruct model is non-thinking. Legacy Go templates may
    # omit thinking metadata in this server version; absence alone proves nothing.
    if 'thinking' in shown and (not isinstance(shown['thinking'],dict) or shown['thinking'].get('values')!=[False]):raise ValueError('Pinned instruct model has conflicting non-thinking-only metadata')
    origin='explicit_show_metadata' if 'thinking' in shown else 'pinned_instruct_manifest_and_capabilities'
    return {'local_model':MODEL,'manifest_verified':True,'non_thinking_only':True,'thinking_control_source':origin,'inference_performed':False}


if __name__=='__main__':
    from .spec import ROOT
    if json.loads((ROOT/'studio.json').read_text())['draft_model']!=MODEL:raise ValueError('Configured local model differs from the pinned workflow model')
    print(json.dumps(verify()))
