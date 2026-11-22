"""YouTube OAuth and explicit, channel-locked uploads. Never invoked by generation."""
import json
import os
from pathlib import Path
from .spec import digest, read_spec, write_json

CHANNEL = 'UCEawmiljBdHvnTScqnpPftw'
SCOPES = ['https://www.googleapis.com/auth/youtube.upload', 'https://www.googleapis.com/auth/youtube.readonly']


def authorize(client_path, token_path):
    from google_auth_oauthlib.flow import InstalledAppFlow
    flow = InstalledAppFlow.from_client_secrets_file(str(client_path), SCOPES)
    creds = flow.run_local_server(port=0, access_type='offline', prompt='consent')
    target = Path(token_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(creds.to_json())
    target.chmod(0o600)
    print('Authorization saved locally. Never commit or attach this file.')


def client(token_path):
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
    return build('youtube', 'v3', credentials=creds, cache_discovery=False)


def preflight(bundle, expected_hash, channel=CHANNEL):
    bundle = Path(bundle)
    m = json.loads((bundle/'manifest.json').read_text())
    actual = digest(bundle/'final.mp4')
    if actual != expected_hash or m.get('reviewed_sha256') != actual or m.get('video_sha256') != actual:
        raise ValueError('Specific full video hash must be reviewed before upload')
    if not m.get('qa_pass') or m.get('preview'):
        raise ValueError('Preview or failed QA cannot be uploaded')
    if m['spec_sha256'] != digest(bundle/'episode.json'):
        raise ValueError('Episode metadata changed after review')
    spec = read_spec(bundle/'episode.json')
    if (not spec.get('science_reviewed') and not m.get('science_accepted_by_operator')) or not spec.get('sources'):
        raise ValueError('Science review and sources required')
    if channel != CHANNEL:
        raise ValueError('Channel does not match configured owner')
    return m,spec


def upload(bundle, token_path, ledger_path, expected_hash, privacy='private', expected_channel=CHANNEL, service=None):
    from googleapiclient.http import MediaFileUpload
    if privacy not in ('private','unlisted','public'):
        raise ValueError('Invalid privacy')
    bundle, ledger_path = Path(bundle),Path(ledger_path)
    manifest,spec = preflight(bundle, expected_hash, expected_channel)
    ledger = json.loads(ledger_path.read_text()) if ledger_path.exists() else {}
    if expected_hash in ledger:
        record=ledger[expected_hash]
        reservation=os.environ.get('CURIOSITY_UPLOAD_RESERVATION')
        if not reservation or record.get('state')!='reserved' or record.get('reservation')!=reservation:
            raise ValueError('This video is already uploaded or its upload outcome is uncertain. Resolve ledger before retrying.')
    yt = service or client(token_path)
    channels = yt.channels().list(part='id', mine=True).execute().get('items',[])
    if [c['id'] for c in channels] != [expected_channel]:
        raise ValueError('Authorized account is not the single expected YouTube channel')
    # Reserve before the external call. Workflow persists this reservation before invoking upload.
    ledger[expected_hash] = {'state':'in_progress','channel':expected_channel,'privacy':privacy}
    write_json(ledger_path,ledger)
    body = {'snippet':{'title':spec['title'],'description':spec.get('description','')+'\n\nSources:\n'+'\n'.join(spec['sources']),
                       'tags':spec.get('tags',[]),'categoryId':'27','defaultLanguage':spec.get('language','en')},
            'status':{'privacyStatus':privacy,'selfDeclaredMadeForKids':False}}
    request = yt.videos().insert(part='snippet,status',body=body,media_body=MediaFileUpload(str(bundle/'final.mp4'),chunksize=8*1024*1024,resumable=True,mimetype='video/mp4'))
    response = None
    while response is None:
        _, response = request.next_chunk(num_retries=3)
    video_id = response['id']
    ledger[expected_hash].update(state='uploaded',video_id=video_id)
    write_json(ledger_path,ledger)
    result = yt.videos().list(part='status,snippet',id=video_id).execute()['items'][0]
    if result['snippet']['channelId'] != expected_channel or result['status']['privacyStatus'] != privacy:
        raise RuntimeError('Uploaded, but channel/privacy verification failed. Do not retry.')
    ledger[expected_hash]['state']='verified'
    write_json(ledger_path,ledger)
    # This application receives a real video ID directly from the API.
    receipt = {'video_id':video_id,'url':'https://www.youtube.com/watch?v='+video_id,
               'privacy':privacy,'channel':expected_channel,'processing_status':result['status'].get('uploadStatus')}
    write_json(bundle/'upload-receipt.json',receipt)
    return receipt
