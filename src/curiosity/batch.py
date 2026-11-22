"""GitHub Actions entry point, inputs read as data rather than interpolated shell."""
import json
import os
from pathlib import Path
import subprocess
import sys
from .spec import ROOT, write_json


def main():
    config=json.loads((ROOT/'studio.json').read_text())
    count=int(os.environ.get('VIDEO_COUNT') or config['video_count'])
    if not 1<=count<=config['max_videos_per_run']:
        raise ValueError('Count outside the configured resource cap')
    mode=os.environ.get('MODE','starter')
    voice=os.environ.get('VOICE','kokoro')
    out=ROOT/'output'
    if mode=='starter':
        subprocess.run([sys.executable,'-m','curiosity.cli','generate','--episode',os.environ.get('EPISODE','stomach-growl'),
                        '--voice',voice,'--count',str(count),'--out',str(out)],check=True)
    elif mode=='new-topic':
        from .planner import draft
        topic=os.environ.get('TOPIC','Why do we get goosebumps?').strip()
        topics=[x.strip() for x in topic.splitlines() if x.strip()]
        source_urls=[x.strip() for x in os.environ.get('SOURCE_URLS','').splitlines() if x.strip()]
        summaries=[]
        for i in range(count):
            # A topic per line gives distinct topics; one topic supports distinct dialogue variations.
            selected=topics[min(i,len(topics)-1)]
            spec_path=ROOT/'drafts'/f'episode-{i+1}.json'
            obj=draft(selected,spec_path,source_urls or None,config['draft_model'],index=i+1)
            subprocess.run([sys.executable,'-m','curiosity.cli','generate','--spec',str(spec_path),
                            '--voice',voice,'--count','1','--out',str(out)],check=True)
            summaries.append(obj['id'])
        write_json(out/'generation.json',{'count':count,'episodes':summaries,'source_review':'drafts, human factual check recommended'})
    else:raise ValueError('Unknown mode')
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'],'a') as f:
            f.write('# Curiosity Studio\n\n')
            f.write('Generation complete. Nothing uploaded to YouTube. Download video-bundles.\n\n')
            for path in sorted(out.glob('*/manifest.json')):
                m=json.loads(path.read_text())
                f.write(f'## {m["episode"]}\n\nSHA256: `{m["video_sha256"]}`\n\nVoice: {m["voice"]}; word timing: {m["word_timing"]}.\n\n')
            f.write('Inspect final.mp4, review.jpg, qa.json, episode.json and sources before publishing.\n')


if __name__=='__main__':main()
