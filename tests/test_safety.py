import copy
import json
from pathlib import Path
from unittest.mock import MagicMock
import pytest
from curiosity.spec import EPISODES, read_spec, write_json, digest, review
from curiosity.youtube import CHANNEL, preflight, upload
from curiosity.planner import public_url


def fixture_spec():
    return json.loads((EPISODES/'stomach-growl.json').read_text())


def save_spec(tmp_path,obj):
    p=tmp_path/'episode.json';write_json(p,obj);return p


@pytest.mark.parametrize('path',list(EPISODES.glob('*.json')))
def test_pack_schema(path):
    assert read_spec(path)['schema_version']==1


@pytest.mark.parametrize('field,value', [('id','../../etc'),('title',''),('renderer','shell'),('schema_version',2)])
def test_invalid_spec(tmp_path,field,value):
    obj=fixture_spec();obj[field]=value
    with pytest.raises(ValueError):read_spec(save_spec(tmp_path,obj))


def test_no_shell_speaker(tmp_path):
    obj=fixture_spec();obj['lines'][0]['speaker']='$(touch bad)'
    with pytest.raises(ValueError):read_spec(save_spec(tmp_path,obj))


def test_bespoke_rig_cannot_change_structure(tmp_path):
    obj=fixture_spec();obj['lines'].pop()
    with pytest.raises(ValueError):read_spec(save_spec(tmp_path,obj))


def test_generic_new_topic_structure(tmp_path):
    obj=fixture_spec();obj['renderer']='generic';obj['lines']=obj['lines'][:3]
    assert read_spec(save_spec(tmp_path,obj))['renderer']=='generic'


def make_bundle(tmp_path,preview=False,reviewed=False):
    save_spec(tmp_path,fixture_spec())
    (tmp_path/'final.mp4').write_bytes(b'not-an-actual-video')
    sha=digest(tmp_path/'final.mp4')
    write_json(tmp_path/'manifest.json',{'preview':preview,'qa_pass':True,'video_sha256':sha,
        'spec_sha256':digest(tmp_path/'episode.json'),'reviewed_sha256':sha if reviewed else None})
    return sha


def test_review_hash_binding(tmp_path):
    sha=make_bundle(tmp_path)
    assert review(tmp_path,sha)['reviewed_sha256']==sha
    with pytest.raises(ValueError):review(tmp_path,'wrong')


def test_preview_cannot_be_approved(tmp_path):
    sha=make_bundle(tmp_path,preview=True)
    with pytest.raises(ValueError):review(tmp_path,sha)


def test_mutation_after_render_blocks_review(tmp_path):
    sha=make_bundle(tmp_path)
    (tmp_path/'episode.json').write_text('{}')
    with pytest.raises(ValueError):review(tmp_path,sha)


def test_upload_needs_explicit_review(tmp_path):
    sha=make_bundle(tmp_path)
    with pytest.raises(ValueError):preflight(tmp_path,sha)


def test_channel_lock(tmp_path):
    sha=make_bundle(tmp_path,reviewed=True)
    with pytest.raises(ValueError):preflight(tmp_path,sha,'wrong-channel')


def test_duplicate_upload_blocked(tmp_path):
    sha=make_bundle(tmp_path,reviewed=True)
    ledger=tmp_path/'uploads.json';write_json(ledger,{sha:{'state':'verified'}})
    with pytest.raises(ValueError):upload(tmp_path,'missing-token',ledger,sha)


def test_uncertain_upload_not_retried(tmp_path):
    sha=make_bundle(tmp_path,reviewed=True)
    ledger=tmp_path/'uploads.json';write_json(ledger,{sha:{'state':'in_progress'}})
    with pytest.raises(ValueError):upload(tmp_path,'missing-token',ledger,sha)


def test_wrong_account_never_inserts(tmp_path):
    sha=make_bundle(tmp_path,reviewed=True)
    service=MagicMock()
    service.channels.return_value.list.return_value.execute.return_value={'items':[{'id':'wrong'}]}
    with pytest.raises(ValueError):upload(tmp_path,'missing-token',tmp_path/'uploads.json',sha,service=service)
    service.videos.assert_not_called()


def test_mock_upload_and_readback(tmp_path):
    sha=make_bundle(tmp_path,reviewed=True)
    service=MagicMock()
    service.channels.return_value.list.return_value.execute.return_value={'items':[{'id':CHANNEL}]}
    service.videos.return_value.insert.return_value.next_chunk.return_value=(None,{'id':'test-video'})
    service.videos.return_value.list.return_value.execute.return_value={'items':[{'snippet':{'channelId':CHANNEL},'status':{'privacyStatus':'private','uploadStatus':'uploaded'}}]}
    result=upload(tmp_path,'missing-token',tmp_path/'uploads.json',sha,service=service)
    assert result['privacy']=='private'
    body=service.videos.return_value.insert.call_args.kwargs['body']
    assert body['status']['privacyStatus']=='private'


@pytest.mark.parametrize('url',['http://example.com','https://127.0.0.1/a','https://localhost/a','https://user:pass@example.com'])
def test_source_private_network_rejected(url):
    with pytest.raises(ValueError):public_url(url)


def test_workflow_has_manual_trigger_no_publication():
    import yaml
    from curiosity.spec import ROOT
    obj=yaml.safe_load((ROOT/'.github/workflows/generate.yml').read_text())
    trigger=obj.get('on',obj.get(True))
    assert 'workflow_dispatch' in trigger
    assert trigger['workflow_dispatch']['inputs']['video_count']['default']==1
    assert 'schedule' not in trigger and 'push' not in trigger
    assert obj['jobs']['generate']['timeout-minutes']<=60


@pytest.mark.parametrize('privacy',['private','unlisted'])
def test_nonpublic_youtube_needs_private_repository(privacy):
    from curiosity.publish import check_repository_privacy
    with pytest.raises(ValueError):check_repository_privacy(False,privacy)
    check_repository_privacy(True,privacy)


def test_public_youtube_can_use_public_repository():
    from curiosity.publish import check_repository_privacy
    check_repository_privacy(False,'public')


def test_private_redirect_rejected_before_request(monkeypatch):
    from curiosity.planner import PublicRedirects
    with pytest.raises(ValueError):
        PublicRedirects().redirect_request(None,None,302,'Moved',{},'https://127.0.0.1/private')


def test_native_phoneme_word_boundaries():
    from types import SimpleNamespace as P
    from curiosity.alignment import align_words
    class Tokenizer:
        def phonemize(self,word,lang):return word
    ph=[P(phoneme=c,start=i/10,end=(i+1)/10) for i,c in enumerate('hi ray')]
    cues,coverage=align_words('hi ray',ph,Tokenizer())
    assert cues[0]['end']==0.2 and cues[1]['start']==0.3
    assert coverage==1


def test_reduced_function_word_stays_with_native_neighbors():
    from types import SimpleNamespace as P
    from curiosity.alignment import align_words
    class Tokenizer:
        def phonemize(self,word,lang):return {'not':'nɑt','a':'eɪ','monster':'mɔnstər'}[word]
    ph=[P(phoneme=c,start=i/10,end=(i+1)/10) for i,c in enumerate('nɑɾə mɔnstər')]
    cues,_=align_words('not a monster',ph,Tokenizer())
    assert cues[1]['source']=='reduced-phoneme-interpolation'
    assert cues[0]['end']<=cues[1]['start']<cues[1]['end']<=cues[2]['start']


def test_audio_envelope_has_real_silence():
    import numpy as np
    from curiosity.alignment import envelope
    env=envelope(np.r_[np.zeros(50),np.ones(50)],100,hz=10)
    assert env[:5]==[0]*5 and env[5:]==[1]*5


def test_public_ledger_hides_unverified_upload_id(tmp_path,monkeypatch):
    from curiosity.youtube import UploadUncertain
    monkeypatch.setenv('CURIOSITY_PUBLIC_LEDGER','1')
    sha=make_bundle(tmp_path,reviewed=True)
    service=MagicMock()
    service.channels.return_value.list.return_value.execute.return_value={'items':[{'id':CHANNEL}]}
    service.videos.return_value.insert.return_value.next_chunk.return_value=(None,{'id':'unverified-video-id'})
    service.videos.return_value.list.return_value.execute.return_value={'items':[{'snippet':{'channelId':CHANNEL},'status':{'privacyStatus':'private'}}]}
    ledger=tmp_path/'uploads.json'
    with pytest.raises(UploadUncertain):upload(tmp_path,'missing-token',ledger,sha,privacy='public',service=service)
    raw=ledger.read_text()
    assert 'unverified-video-id' not in raw and CHANNEL not in raw
    assert json.loads(raw)[sha]['state']=='uploaded_unverified'


def test_public_ledger_retains_only_verified_public_receipt(tmp_path,monkeypatch):
    monkeypatch.setenv('CURIOSITY_PUBLIC_LEDGER','1')
    sha=make_bundle(tmp_path,reviewed=True)
    service=MagicMock()
    service.channels.return_value.list.return_value.execute.return_value={'items':[{'id':CHANNEL}]}
    service.videos.return_value.insert.return_value.next_chunk.return_value=(None,{'id':'verified-public-id'})
    service.videos.return_value.list.return_value.execute.return_value={'items':[{'snippet':{'channelId':CHANNEL},'status':{'privacyStatus':'public','uploadStatus':'uploaded'}}]}
    ledger=tmp_path/'uploads.json'
    result=upload(tmp_path,'missing-token',ledger,sha,privacy='public',service=service)
    assert result['video_id']=='verified-public-id'
    assert json.loads(ledger.read_text())[sha]['state']=='verified'


def test_unexpected_publication_exception_cannot_echo_api_url():
    from curiosity.youtube import failure_message
    message=failure_message(RuntimeError('A provider URL with an unverified identifier and credentials'))
    assert 'provider URL' not in message and 'Do not retry' not in message
    assert 'before any retry' in message
