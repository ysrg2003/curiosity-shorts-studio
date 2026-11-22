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
    if shown.get('thinking',{}).get('values')!=[False]:raise ValueError('Local model does not explicitly advertise non-thinking-only control')
    return {'local_model':MODEL,'manifest_verified':True,'non_thinking_only':True,'inference_performed':False}


if __name__=='__main__':
    from .spec import ROOT
    if json.loads((ROOT/'studio.json').read_text())['draft_model']!=MODEL:raise ValueError('Configured local model differs from the pinned workflow model')
    print(json.dumps(verify()))
