"""Automatic topic/research/script experiment only. Never starts audio, video or upload."""
import json
from .autonomy import select_and_research, ResearchUnavailable
from .planner import draft
from .spec import ROOT, write_json


def main(experimental_nine=False):
    config = json.loads((ROOT / 'studio.json').read_text())
    from .local_ai import EXPERIMENTAL_MODEL
    model=EXPERIMENTAL_MODEL if experimental_nine else config['draft_model']
    target = ROOT / 'drafts' / 'episode-1.json'
    target.parent.mkdir(parents=True, exist_ok=True)
    history = ROOT / '.state' / 'topics.json'
    previous = json.loads(history.read_text()).get('generated_topics', []) if history.exists() else []
    previous += [json.loads(path.read_text()).get('title', '') for path in (ROOT / 'episodes').glob('*.json')]
    try:
        question, records, selection = select_and_research(model, previous)
    except ResearchUnavailable as error:
        write_json(target.with_suffix('.selection.json'), error.diagnostics)
        raise
    write_json(target.with_suffix('.selection.json'), selection)
    draft(question, target, model=model, source_records=records)
    import os
    backend=os.environ.get('CURIOSITY_LLM_BACKEND','ollama')
    if backend=='prepared-router':
        from .router_ai import MODEL as model
    write_json(ROOT / 'drafts' / 'preflight-result.json', {
        'backend':backend,
        'experimental_model':experimental_nine,'model':model,'automated_script_checks_passed': True, 'operator_topic_or_source_input': False,
        'audio_created': False, 'video_created': False, 'upload_attempted': False,
        'human_scientific_and_story_review_still_required': True})
    print('Automatic script preflight completed. No audio, video or upload was created.')


if __name__ == '__main__':
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument('--experimental-nine',action='store_true')
    main(parser.parse_args().experimental_nine)
