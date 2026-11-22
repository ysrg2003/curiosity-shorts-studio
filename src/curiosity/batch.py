"""GitHub Actions entry point, inputs read as data rather than interpolated shell."""
import json
import os
import re
from pathlib import Path
import subprocess
import sys
from .process_safety import media_environment
from .spec import ROOT, write_json


def generate():
    config=json.loads((ROOT/'studio.json').read_text())
    count=int(os.environ.get('VIDEO_COUNT') or config['video_count'])
    if not 1<=count<=config['max_videos_per_run']:
        raise ValueError('Count outside the configured resource cap')
    mode=os.environ.get('MODE','starter')
    voice=os.environ.get('VOICE','kokoro')
    out=ROOT/'output'
    if mode=='starter':
        subprocess.run([sys.executable,'-m','curiosity.cli','generate','--episode',os.environ.get('EPISODE','stomach-growl'),
                        '--voice',voice,'--count',str(count),'--out',str(out)],check=True,env=media_environment())
    elif mode in ('new-topic','automatic'):
        from .planner import draft
        from .autonomy import select_and_research,ResearchUnavailable
        if os.environ.get('CURIOSITY_LLM_BACKEND')=='openrouter-free':
            from .remote_ai import free_quota_status
            quota=free_quota_status(minimum_requests=23*count)
            (ROOT/'drafts').mkdir(parents=True,exist_ok=True)
            write_json(ROOT/'drafts/quota-budget.json',{**quota,'video_count':count,'rule':'conservative maximum 23 inference requests per automatic video; availability can still change'})
            if quota['http_status']!=200 or quota['request_budget']!='sufficient_for_bounded_attempt':
                raise RuntimeError('Request budget is unavailable or below the conservative reserve. No inference attempted.')
        topic=os.environ.get('TOPIC','Why do we get goosebumps?').strip()
        topics=[x.strip() for x in re.split(r"[;\n]+",topic) if x.strip()]
        if mode=='new-topic' and not topics: raise ValueError('Supply at least one topic')
        source_urls=[x for x in re.split(r'[\s;]+',os.environ.get('SOURCE_URLS','').strip()) if x]
        history_path=ROOT/'.state/topics.json'
        previous=json.loads(history_path.read_text()).get('generated_topics',[]) if history_path.exists() else []
        previous += [json.loads(path.read_text()).get('title','') for path in (ROOT/'episodes').glob('*.json')]
        summaries=[]
        for i in range(count):
            spec_path=ROOT/'drafts'/f'episode-{i+1}.json'
            spec_path.parent.mkdir(parents=True,exist_ok=True)
            records=None
            if mode=='automatic':
                try:selected,records,selection=select_and_research(config['draft_model'],previous,seed=43+i)
                except ResearchUnavailable as error:
                    write_json(spec_path.with_suffix('.selection.json'),error.diagnostics);raise
                write_json(spec_path.with_suffix('.selection.json'),selection)
            else:selected=topics[min(i,len(topics)-1)]
            obj=draft(selected,spec_path,None if mode=='automatic' else source_urls or None,config['draft_model'],index=i+1,source_records=records)
            from .generated_motion import prepare
            worker=[sys.executable,'-m','curiosity.media_worker']
            options=['--spec',str(spec_path),'--voice',voice,'--out',str(out)]
            subprocess.run(worker+['audio']+options,check=True,env=media_environment())
            bundle=out/obj['id'];timeline=json.loads((bundle/'timeline.json').read_text())
            prepare(obj,timeline,bundle,config['draft_model'])
            subprocess.run(worker+['video']+options,check=True,env=media_environment())
            summaries.append(obj['id']);previous.append(selected)
            history_path.parent.mkdir(exist_ok=True)
            write_json(history_path,{'generated_topics':previous[-500:],'deduplication':'available cached history only, not a complete channel archive'})
        write_json(out/'generation.json',{'count':count,'episodes':summaries,'operator_topic_or_source_input':mode!='automatic','source_review':'automated evidence checks are not a factual-accuracy guarantee'})
    else:raise ValueError('Unknown mode')
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'],'a') as f:
            f.write('# Curiosity Studio\n\n')
            f.write('Generation complete. Nothing uploaded to YouTube. Download video-bundles.\n\n')
            for path in sorted(out.glob('*/manifest.json')):
                m=json.loads(path.read_text())
                f.write(f'## {m["episode"]}\n\nSHA256: `{m["video_sha256"]}`\n\nVoice: {m["voice"]}; word timing: {m["word_timing"]}.\n\n')
            f.write('Inspect final.mp4, review.jpg, qa.json, episode.json and sources before publishing.\n')


def main():
    from .remote_ai import ModelOutputInvalid,ModelRequestFailed,UnexpectedModelCost
    try:generate()
    except (ModelOutputInvalid,ModelRequestFailed,UnexpectedModelCost) as error:
        (ROOT/'drafts').mkdir(parents=True,exist_ok=True)
        write_json(ROOT/'drafts/model-failure.json',{'accepted':False,'kind':type(error).__name__,'response_shape':error.metadata if isinstance(error,(ModelOutputInvalid,ModelRequestFailed)) else {},'complete_video':False})
        raise


if __name__=='__main__':main()
