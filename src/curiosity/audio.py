"""Speech adapters. Edge keeps the original voices; Kokoro is a local alternative."""
import asyncio
import json
import re
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
    from .alignment import align_words
    sound = re.match(r'^(G[rR]+[kK]?[.!]*)\s+',text)
    spoken = text[sound.end():] if sound else text
    audio, sample_rate, phonemes = pipeline.create_timed(spoken, voice=voice, speed=1.04 if speaker == 'PIP' else 1.0, lang='en-us')
    if not phonemes:
        raise ValueError('This voice model has no duration output; model-backed timing is unavailable')
    cues, coverage = align_words(spoken,phonemes,pipeline.tokenizer)
    if sound:
        import numpy as np
        t=np.arange(round(sample_rate*0.48))/sample_rate
        noise=np.random.default_rng(42).normal(size=len(t))
        noise=np.convolve(noise,np.ones(100)/100,mode='same')
        effect=(np.sin(2*np.pi*(105*t-30*t*t))*(0.5+0.5*np.sin(2*np.pi*8*t))+0.5*noise)*0.17*np.sin(np.pi*t/0.48)**2
        pad=np.concatenate([effect,np.zeros(round(sample_rate*0.10))]).astype(audio.dtype)
        audio=np.concatenate([pad,audio]);offset=len(pad)/sample_rate
        cues=[{'text':sound.group(1),'start':0.0,'end':0.48,'kind':'sound-effect'}]+[{**c,'start':c['start']+offset,'end':c['end']+offset} for c in cues]
    sf.write(str(path), audio, sample_rate)
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
        key = json.dumps([ln['text'], ln['speaker'], engine, VOICES, 'duration-alignment-v3'], sort_keys=True)
        cache = path.with_suffix('.json')
        if path.exists() and cache.exists() and json.loads(cache.read_text()).get('key') == key:
            cues = json.loads(cache.read_text())['cues']
        else:
            cues = await edge_line(ln['text'], ln['speaker'], path) if engine == 'edge' else kokoro_line(ln['text'], ln['speaker'], path, pipeline)
            cache.write_text(json.dumps({'key': key, 'cues': cues}))
        d = duration(path)
        import soundfile as sf
        from .alignment import envelope
        waveform, sample_rate = sf.read(str(path))
        mouth = envelope(waveform,sample_rate)
        for c in cues:
            if c.get('kind')=='sound-effect':
                for j in range(int(c['start']*40),min(len(mouth),int(c['end']*40)+1)):mouth[j]=0.0
        lines.append({**ln, 'mouth_envelope':mouth,'mouth_hz':40, 'idx': i, 'start': t, 'end': t+d, 'audio': str(path.relative_to(out)),
                      'words': [{**c, 'start': t+c['start'], 'end': t+c['end']} for c in cues]})
        t += d+0.35
    timeline = {'total': t+0.9, 'lines': lines, 'voice_engine': engine,
                'word_timing': 'service-boundaries' if engine == 'edge' else 'model-phoneme-alignment'}
    (out / 'timeline.json').write_text(json.dumps(timeline, indent=2))
    return timeline
