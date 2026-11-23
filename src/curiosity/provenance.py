"""Bind continuation research to an actual runtime, not a generic flag."""
import hashlib,json,os,uuid
from pathlib import Path

INVALID_RUNS={'45111351142':'Unit-test synthetic dossiers contaminated drafts before runtime; all research dossiers from this run are invalid.'}


def payload_hash(question,sources):
    return hashlib.sha256(json.dumps({'question':question,'sources':sources},sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()


def begin(root):
    drafts=Path(root)/'drafts';drafts.mkdir(parents=True,exist_ok=True)
    # Old research/selection evidence cannot silently join a new execution.
    stale=list(drafts.glob('research-*.json'))
    if stale:raise ValueError('Stale research dossiers present before runtime; refuse mixing executions')
    run={'runtime_id':str(uuid.uuid4()),'github_run_id':os.environ.get('GITHUB_RUN_ID'),'github_repository':os.environ.get('GITHUB_REPOSITORY'),'github_sha':os.environ.get('GITHUB_SHA'),'kind':'automatic-production','unit_test':False}
    (drafts/'runtime.json').write_text(json.dumps(run));return run


def bind(root,question,sources):
    path=Path(root)/'drafts/runtime.json'
    if not path.exists():return {'kind':'unbound','continuation_allowed':False}
    run=json.loads(path.read_text())
    return {**run,'payload_sha256':payload_hash(question,sources),'continuation_allowed':bool(run.get('github_run_id')) and run.get('github_run_id') not in INVALID_RUNS}


def validate(record,runtime):
    provenance=record.get('provenance',{})
    if str(provenance.get('github_run_id')) in INVALID_RUNS:raise ValueError('Invalidated original run research')
    if provenance.get('continuation_allowed') is not True or provenance.get('kind')!='automatic-production' or provenance.get('unit_test') is not False:raise ValueError('Missing actual production provenance')
    if not provenance.get('runtime_id') or provenance['runtime_id']!=runtime.get('runtime_id') or provenance.get('github_run_id')!=runtime.get('github_run_id'):raise ValueError('Original runtime does not match research dossier')
    if provenance.get('payload_sha256')!=payload_hash(record['question'],record['packed_original_sources']):raise ValueError('Original source dossier integrity mismatch')
