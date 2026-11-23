"""Continue an unchanged autonomous source dossier, never skip acceptance gates."""
import argparse,json
from pathlib import Path
from .spec import ROOT,write_json
from .evidence import plan_sources,screen
from .planner import draft


def resume(path,model):
    record=json.loads(Path(path).read_text())
    if record.get('schema_version')!=1 or record.get('operator_topic_or_source_input') is not False:
        raise ValueError('Not an autonomous original research dossier')
    question=record['question'];packed=record['packed_original_sources'];target=ROOT/'drafts/episode-1.json'
    target.parent.mkdir(parents=True,exist_ok=True)
    ok,plan=plan_sources(question,packed,model)
    write_json(target.with_suffix('.resumed-source-plan.json'),plan)
    if not ok:raise ValueError('Unchanged source dossier failed pre-answer planning')
    planned=[{**source,**({'source_scope_plan':plan['selected_original_paths']} if i==0 else {})} for i,source in enumerate(packed)]
    ok,review=screen(question,planned,model)
    write_json(target.with_suffix('.resumed-source-review.json'),review)
    if not ok:raise ValueError('Unchanged source dossier failed scientific scope screening')
    approved=[packed[i] for i in review['approved_source_indices']]
    draft(question,target,model=model,source_records=approved)
    write_json(ROOT/'drafts/preflight-result.json',{'automated_script_checks_passed':True,'operator_topic_or_source_input':False,'resumed_unchanged_source_dossier':True,'audio_created':False,'video_created':False,'upload_attempted':False,'human_scientific_and_story_review_still_required':True})


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('dossier');args=parser.parse_args()
    config=json.loads((ROOT/'studio.json').read_text());resume(args.dossier,config['draft_model'])
