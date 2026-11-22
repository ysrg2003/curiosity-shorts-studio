"""Command-line entry point. Generation never publishes as a side effect."""
import argparse
import asyncio
import json
from pathlib import Path
import shutil
import sys
from .spec import ROOT, EPISODES, digest, read_spec, review, write_json


def produce(args):
    from .audio import generate
    from .render import render, mux
    from .qa import check
    if not 1 <= args.count <= 20:
        raise ValueError('count must be between 1 and 20')
    paths = [Path(args.spec)] if args.spec else [EPISODES/(args.episode+'.json')]
    if args.count > 1:
        paths += [p for p in sorted(EPISODES.glob('*.json')) if p not in paths]
    if args.count > len(paths):
        raise ValueError(f'Only {len(paths)} distinct episode packs available. Add new reviewed packs before increasing count further.')
    out = Path(args.out).resolve()
    out.mkdir(parents=True,exist_ok=True)
    receipts = []
    for path in paths[:args.count]:
        spec = read_spec(path)
        bundle = out/spec['id']
        bundle.mkdir(parents=True,exist_ok=True)
        write_json(bundle/'episode.json',spec)
        timeline = asyncio.run(generate(spec,bundle,args.voice))
        if timeline['total'] > 180:
            raise ValueError('Narration exceeds the 180-second Shorts limit, shorten script')
        total = render(spec,bundle,args.preview_seconds,args.width)
        mux(bundle,total)
        qa = check(bundle,total,args.width)
        manifest = {'schema_version':1,'episode':spec['id'],'title':spec['title'],'voice':args.voice,
                    'word_timing':timeline['word_timing'],'preview':bool(args.preview_seconds),
                    'width':args.width,'qa_pass':qa['pass'],'video_sha256':digest(bundle/'final.mp4'),
                    'spec_sha256':digest(bundle/'episode.json'),'reviewed_sha256':None,'publishing':'not_requested'}
        write_json(bundle/'manifest.json',manifest)
        receipts.append(manifest)
        print(f'Completed {spec["id"]}: {bundle}/final.mp4 SHA256={manifest["video_sha256"]}')
    write_json(out/'batch.json',{'requested_count':args.count,'completed_count':len(receipts),'videos':receipts})


def main(argv=None):
    p = argparse.ArgumentParser(prog='curiosity')
    sub = p.add_subparsers(dest='command',required=True)
    gen = sub.add_parser('generate')
    gen.add_argument('--episode',default='stomach-growl')
    gen.add_argument('--spec')
    gen.add_argument('--count',type=int,default=1)
    gen.add_argument('--voice',choices=['edge','kokoro'],default='edge')
    gen.add_argument('--width',type=int,choices=[540,1080],default=1080)
    gen.add_argument('--preview-seconds',type=float)
    gen.add_argument('--out',default='output')
    rev = sub.add_parser('review')
    rev.add_argument('--bundle',required=True)
    rev.add_argument('--sha256',required=True)
    rev.add_argument('--accept-draft-science',action='store_true')
    auth = sub.add_parser('authorize')
    auth.add_argument('--client',required=True)
    auth.add_argument('--token',default='.secrets/youtube-token.json')
    pub = sub.add_parser('upload')
    pub.add_argument('--bundle',required=True)
    pub.add_argument('--sha256',required=True)
    pub.add_argument('--token',required=True)
    pub.add_argument('--ledger',default='.state/uploads.json')
    pub.add_argument('--privacy',choices=['private','unlisted','public'],default='private')
    dra = sub.add_parser('draft')
    dra.add_argument('--topic',required=True)
    dra.add_argument('--source',action='append')
    dra.add_argument('--model',default='qwen3:4b-instruct')
    dra.add_argument('--out',default='draft.json')
    dra.add_argument('--index',type=int,default=1)
    args = p.parse_args(argv)
    if args.command == 'generate':
        if args.preview_seconds is not None and args.preview_seconds < 1:
            p.error('preview must be at least 1 second')
        produce(args)
    elif args.command == 'draft':
        from .planner import draft
        draft(args.topic,args.out,args.source,args.model,index=args.index)
        print('New script, SEO and diagram drafted from sources. Review science before publishing.')
    elif args.command == 'review':
        review(args.bundle,args.sha256,args.accept_draft_science)
        print('Specific artifact hash approved locally.')
    elif args.command == 'authorize':
        from .youtube import authorize
        authorize(args.client,args.token)
    elif args.command == 'upload':
        from .youtube import upload,failure_message,UploadUncertain
        Path(args.ledger).parent.mkdir(parents=True,exist_ok=True)
        try:print(json.dumps(upload(args.bundle,args.token,args.ledger,args.sha256,args.privacy),indent=2))
        except Exception as error:raise UploadUncertain(failure_message(error)) from None


if __name__ == '__main__':
    try:
        main()
    except (ValueError, RuntimeError) as error:
        print(f'Error: {error}',file=sys.stderr)
        raise SystemExit(1)
