"""Speech adapters. Edge keeps the original voices; Kokoro is a local alternative."""
import asyncio
import json
import subprocess
from pathlib import Path

VOICES = {
    'PIP': {'voice': 'en-US-AnaNeural', 'pitch': '+14Hz', 'rate': '+4%'},
    'RAY': {'voice': 'en-US-AndrewNeural', 'pitch': '+0Hz', 'rate': '+0%'},
}


def duration(path):
    p = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'json', str(path)], capture_output=True, text=True, check=True)
    return float(json.loads(p.stdout)['format']['duration'])


async def edge_line(text, speaker, path):
    import edge_tts
    for attempt in range(3):
        cues = []
        try:
            comm = edge_tts.Communicate(text, **VOICES[speaker], boundary='WordBoundary')
            with path.open('wb') as stream:
                async for chunk in comm.stream():
                    if chunk['type'] == 'audio':
                        stream.write(chunk['data'])
                    elif chunk['type'] == 'WordBoundary':
                        cues.append({'text': chunk['text'], 'start': chunk['offset']/1e7,
                                     'end': (chunk['offset'] + chunk['duration'])/1e7})
            if path.stat().st_size < 200 or not cues:
                raise RuntimeError('Speech service returned empty audio or no word timings')
            return cues
        except Exception:
            path.unlink(missing_ok=True)
            if attempt == 2:
                raise
            await asyncio.sleep(2 * (attempt + 1))


def kokoro_line(text, speaker, path, pipeline):
    import soundfile as sf
    voice = 'af_sky' if speaker == 'PIP' else 'am_michael'
    audio, sample_rate = pipeline.create(text, voice=voice, speed=1.04 if speaker == 'PIP' else 1.0, lang='en-us')
    sf.write(str(path), audio, sample_rate)
    # These are estimates, explicitly labelled. Exact service boundaries are used in Edge mode.
    tokens = text.split()
    total = len(audio)/sample_rate
    weight = sum(max(1, len(t)) for t in tokens)
    cues, t = [], 0.0
    for word in tokens:
        end = t + total*max(1, len(word))/weight
        cues.append({'text': word, 'start': t, 'end': end})
        t = end
    return cues


async def generate(spec, out, engine='edge'):
    out = Path(out)
    audio_dir = out / 'audio'
    audio_dir.mkdir(parents=True, exist_ok=True)
    pipeline = None
    if engine == 'kokoro':
        from kokoro_onnx import Kokoro
        from .models import ensure_voice_models
        model, voices = ensure_voice_models()
        pipeline = Kokoro(str(model), str(voices))
    lines, t = [], 0.4
    for i, ln in enumerate(spec['lines']):
        path = audio_dir / f'line{i:02d}.{ "mp3" if engine == "edge" else "wav" }'
        # Cache only audio whose text, voice and engine match.
        key = json.dumps([ln['text'], ln['speaker'], engine, VOICES], sort_keys=True)
        cache = path.with_suffix('.json')
        if path.exists() and cache.exists() and json.loads(cache.read_text()).get('key') == key:
            cues = json.loads(cache.read_text())['cues']
        else:
            cues = await edge_line(ln['text'], ln['speaker'], path) if engine == 'edge' else kokoro_line(ln['text'], ln['speaker'], path, pipeline)
            cache.write_text(json.dumps({'key': key, 'cues': cues}))
        d = duration(path)
        lines.append({**ln, 'idx': i, 'start': t, 'end': t+d, 'audio': str(path.relative_to(out)),
                      'words': [{**c, 'start': t+c['start'], 'end': t+c['end']} for c in cues]})
        t += d+0.35
    timeline = {'total': t+0.9, 'lines': lines, 'voice_engine': engine,
                'word_timing': 'service-boundaries' if engine == 'edge' else 'estimated'}
    (out / 'timeline.json').write_text(json.dumps(timeline, indent=2))
    return timeline
