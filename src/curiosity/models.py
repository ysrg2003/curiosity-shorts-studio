"""Fetch a pinned open-weight speech model once, checking its SHA256."""
import hashlib
import os
from pathlib import Path
from urllib.request import urlopen
import json


def ensure_voice_models():
    root=Path(os.environ.get('CURIOSITY_MODEL_DIR',str(Path.home()/'.cache/curiosity-studio')))
    root.mkdir(parents=True,exist_ok=True)
    records=json.loads((Path(__file__).with_name('voice-models.json')).read_text())
    result=[]
    for record in records:
        path=root/record['name']
        if not path.exists() or checksum(path)!=record['sha256']:
            temp=path.with_suffix('.part')
            with urlopen(record['url'],timeout=120) as response, temp.open('wb') as out:
                while chunk:=response.read(1048576):out.write(chunk)
            if checksum(temp)!=record['sha256']:
                temp.unlink(missing_ok=True)
                raise ValueError('Speech model hash mismatch, refusing unverified model')
            temp.replace(path)
        result.append(path)
    return result


def checksum(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda:stream.read(1048576),b''):h.update(chunk)
    return h.hexdigest()
