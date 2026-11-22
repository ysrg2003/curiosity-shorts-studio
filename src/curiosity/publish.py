"""Manual publication action with persistent pre-upload reservation."""
import json
import os
from pathlib import Path
import re
import subprocess
from .spec import ROOT, review, write_json
from .youtube import upload


def git(*args):
    return subprocess.run(['git',*args],check=True,capture_output=True,text=True)


def persist(message):
    git('config','user.name','github-actions[bot]')
    git('config','user.email','41898282+github-actions[bot]@users.noreply.github.com')
    git('add','-f','.state/uploads.json')
    git('commit','-m',message)
    git('push','origin','HEAD:main')


def main():
    run=os.environ['SOURCE_RUN_ID']
    episode=os.environ['EPISODE_ID']
    sha=os.environ['VIDEO_SHA256']
    privacy=os.environ.get('PRIVACY','private')
    if not run.isdigit() or not re.fullmatch('[a-zA-Z0-9_-]+',episode) or not re.fullmatch('[0-9a-f]{64}',sha):
        raise ValueError('Invalid source run, episode ID or SHA256')
    if os.environ.get('APPROVAL')!='I reviewed this exact video':
        raise ValueError('Explicit exact-video approval is required')
    if not os.environ.get('YOUTUBE_TOKEN_JSON'):
        raise ValueError('YouTube OAuth secret is not installed')
    info=json.loads(subprocess.run(['gh','api',f'repos/{os.environ["GITHUB_REPOSITORY"]}/actions/runs/{run}'],capture_output=True,text=True,check=True).stdout)
    if info.get('path')!='.github/workflows/generate.yml' or info.get('conclusion')!='success' or info.get('head_branch')!='main':
        raise ValueError('Source must be a successful generation run from main in this repository')
    subprocess.run(['gh','run','download',run,'--name','video-bundles','--dir','incoming'],check=True)
    candidates=list((ROOT/'incoming').glob('**/'+episode+'/manifest.json'))
    if len(candidates)!=1:raise ValueError('Expected exactly one matching video bundle')
    bundle=candidates[0].parent
    review(bundle,sha,accept_draft_science=os.environ.get('SCIENCE_CHECKED')=='true')
    ledger_path=ROOT/'.state/uploads.json'
    ledger_path.parent.mkdir(exist_ok=True)
    ledger=json.loads(ledger_path.read_text()) if ledger_path.exists() else {}
    if sha in ledger:raise ValueError('Duplicate or uncertain upload exists, refusing automatic retry')
    reservation=os.environ['GITHUB_RUN_ID']+':'+os.environ.get('GITHUB_RUN_ATTEMPT','1')
    ledger[sha]={'state':'reserved','reservation':reservation,'source_run':run,'privacy':privacy}
    write_json(ledger_path,ledger)
    # A failed push stops before inserting anything. A crash after this commit blocks later retries.
    persist('Reserve reviewed video upload')
    os.environ['CURIOSITY_UPLOAD_RESERVATION']=reservation
    secrets=ROOT/'.secrets';secrets.mkdir(exist_ok=True)
    token_path=secrets/'youtube-token.json'
    token_path.write_text(os.environ['YOUTUBE_TOKEN_JSON']);token_path.chmod(0o600)
    try:
        receipt=upload(bundle,token_path,ledger_path,sha,privacy)
        print(json.dumps(receipt))
    finally:
        token_path.unlink(missing_ok=True)
        if ledger_path.exists():
            try:persist('Record video upload outcome')
            except subprocess.CalledProcessError:
                print('Ledger reservation is already persisted. Outcome commit needs manual reconciliation; do not retry upload.')


if __name__=='__main__':main()
