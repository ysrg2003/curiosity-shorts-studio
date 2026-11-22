"""Separate speech and final compositing workers. No model credential is needed."""
import argparse
import asyncio
import json
from pathlib import Path
from .spec import read_spec,write_json,digest


def main():
    parser=argparse.ArgumentParser();parser.add_argument('phase',choices=['audio','video']);parser.add_argument('--spec',required=True);parser.add_argument('--voice',default='kokoro');parser.add_argument('--out',required=True)
    args=parser.parse_args();spec=read_spec(args.spec);bundle=Path(args.out)/spec['id'];bundle.mkdir(parents=True,exist_ok=True)
    if args.phase=='audio':
        from .audio import generate
        write_json(bundle/'episode.json',spec)
        timeline=asyncio.run(generate(spec,bundle,args.voice))
        if timeline['total']>180:raise ValueError('Narration exceeds180seconds. No video created.')
        return
    from .render import render,mux
    from .qa import check
    timeline=json.loads((bundle/'timeline.json').read_text());total=render(spec,bundle,None,1080);mux(bundle,total);qa=check(bundle,total,1080)
    manifest={'schema_version':1,'episode':spec['id'],'title':spec['title'],'voice':args.voice,'word_timing':timeline['word_timing'],'preview':False,'width':1080,'qa_pass':qa['pass'],'video_sha256':digest(bundle/'final.mp4'),'spec_sha256':digest(bundle/'episode.json'),'reviewed_sha256':None,'publishing':'not_requested','visuals':'source-directed generated Manim, not a preset'}
    write_json(bundle/'manifest.json',manifest)
    print('Completed complete video bundle:',spec['id'])


if __name__=='__main__':main()
