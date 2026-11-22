"""Manual publication action with persistent pre-upload reservation."""
import json
import os
from pathlib import Path
import re
import subprocess
from .spec import ROOT, review, write_json
from .youtube import upload,write_ledger,UploadRejected,failure_message


def git(*args):
    return subprocess.run(['git',*args],check=True,capture_output=True,text=True)


def persist(message):
    git('config','user.name','github-actions[bot]')
    git('config','user.email','41898282+github-actions[bot]@users.noreply.github.com')
    git('add','-f','.state/uploads.json')
    git('commit','-m',message)
    git('push','origin','HEAD:main')


def check_repository_privacy(is_private, privacy):
    if not is_private and privacy != 'public':
        raise UploadRejected('Make the repository private before private or unlisted uploads. Public repository logs and ledger are visible to others.')


def main():
    run=os.environ['SOURCE_RUN_ID']
    episode=os.environ['EPISODE_ID']
    sha=os.environ['VIDEO_SHA256']
    privacy=os.environ.get('PRIVACY','private')
    if not run.isdigit() or not re.fullmatch('[a-zA-Z0-9_-]+',episode) or not re.fullmatch('[0-9a-f]{64}',sha):
        raise UploadRejected('Invalid source run, episode ID or SHA256')
    if os.environ.get('APPROVAL')!='I reviewed this exact video':
        raise UploadRejected('Explicit exact-video approval is required')
    repo_info=json.loads(subprocess.run(['gh','api',f'repos/{os.environ["GITHUB_REPOSITORY"]}'],capture_output=True,text=True,check=True).stdout)
    check_repository_privacy(repo_info.get('private') is True,privacy)
    os.environ['CURIOSITY_PUBLIC_LEDGER']='0' if repo_info.get('private') is True else '1'
    if not os.environ.get('YOUTUBE_TOKEN_JSON'):
        raise UploadRejected('YouTube OAuth secret is not installed')
    info=json.loads(subprocess.run(['gh','api',f'repos/{os.environ["GITHUB_REPOSITORY"]}/actions/runs/{run}'],capture_output=True,text=True,check=True).stdout)
    if info.get('path')!='.github/workflows/generate.yml' or info.get('conclusion')!='success' or info.get('head_branch')!='main':
        raise UploadRejected('Source must be a successful generation run from main in this repository')
    subprocess.run(['gh','run','download',run,'--name','video-bundles','--dir','incoming'],check=True)
    candidates=list((ROOT/'incoming').glob('**/'+episode+'/manifest.json'))
    if len(candidates)!=1:raise UploadRejected('Expected exactly one matching video bundle')
    bundle=candidates[0].parent
    review(bundle,sha,accept_draft_science=os.environ.get('SCIENCE_CHECKED')=='true')
    ledger_path=ROOT/'.state/uploads.json'
    ledger_path.parent.mkdir(exist_ok=True)
    ledger=json.loads(ledger_path.read_text()) if ledger_path.exists() else {}
    if sha in ledger:raise UploadRejected('Duplicate or uncertain upload exists, refusing automatic retry')
    reservation=os.environ['GITHUB_RUN_ID']+':'+os.environ.get('GITHUB_RUN_ATTEMPT','1')
    ledger[sha]={'state':'reserved','reservation':reservation,'source_run':run,'privacy':privacy}
    write_ledger(ledger_path,ledger)
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


if __name__=='__main__':
    try:main()
    except Exception as error:
        print(failure_message(error))
        raise SystemExit(1) from None
