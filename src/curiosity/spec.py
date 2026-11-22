"""Validated episode inputs and immutable review manifests."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EPISODES = ROOT / 'episodes'
RENDERERS = {'brain_freeze', 'dizziness', 'onion_tears', 'hiccups', 'stomach_growl', 'generic'}


def read_spec(path):
    obj = json.loads(Path(path).read_text())
    if obj.get('schema_version') != 1:
        raise ValueError('schema_version must be 1')
    if not obj.get('id') or not all(c.isalnum() or c in '-_' for c in obj['id']):
        raise ValueError('id must contain only letters, digits, hyphens or underscores')
    if obj.get('renderer') not in RENDERERS:
        raise ValueError('Unknown renderer')
    if not 1 <= len(obj.get('title', '')) <= 100:
        raise ValueError('title must be 1 to 100 characters')
    lines = obj.get('lines', [])
    if not 2 <= len(lines) <= 40:
        raise ValueError('Episode must have 2 to 40 lines')
    for line in lines:
        if line.get('speaker') not in ('PIP', 'RAY') or not line.get('beat'):
            raise ValueError('Each line needs PIP/RAY speaker and a beat')
        if not isinstance(line.get('text'), str) or not 1 <= len(line['text']) <= 700:
            raise ValueError('Each line needs 1 to 700 text characters')
    if sum(len(x['text'].split()) for x in lines) > 650:
        raise ValueError('Script too long for a Short')
    if obj['renderer'] != 'generic':
        canonical = json.loads((EPISODES / (obj['renderer'].replace('_', '-') + '.json')).read_text())
        if [(x['speaker'], x['beat']) for x in lines] != [(x['speaker'], x['beat']) for x in canonical['lines']]:
            raise ValueError('Bespoke rig requires its canonical speaker and beat order; use generic for new structures')
    return obj


def digest(path):
    h = hashlib.sha256()
    with open(path, 'rb') as stream:
        for block in iter(lambda: stream.read(1048576), b''):
            h.update(block)
    return h.hexdigest()


def write_json(path, data):
    Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n')


def review(bundle, expected_hash, accept_draft_science=False):
    bundle = Path(bundle)
    m = json.loads((bundle / 'manifest.json').read_text())
    actual = digest(bundle / 'final.mp4')
    if actual != expected_hash or actual != m['video_sha256']:
        raise ValueError('Video hash does not match the reviewed artifact')
    if m.get('preview') or not m.get('qa_pass'):
        raise ValueError('Only a complete QA-passed video can be approved')
    spec = read_spec(bundle / 'episode.json')
    if digest(bundle / 'episode.json') != m['spec_sha256']:
        raise ValueError('Episode changed after rendering')
    if not spec.get('sources') or (not spec.get('science_reviewed') and not accept_draft_science):
        raise ValueError('Science needs review. For a checked AI draft, explicitly accept draft science after reading sources.')
    m['science_accepted_by_operator'] = bool(spec.get('science_reviewed') or accept_draft_science)
    m['reviewed_sha256'] = actual
    write_json(bundle / 'manifest.json', m)
    return m
