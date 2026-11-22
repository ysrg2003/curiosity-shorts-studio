"""Render the creative library and mux normalized narration."""
import importlib.util
import json
import math
import os
from pathlib import Path
import subprocess
import sys

from .spec import ROOT


def load_renderer(spec, out):
    os.environ['CURIOSITY_WORKDIR'] = str(Path(out).resolve())
    sys.path.insert(0, str(ROOT / 'creative'))
    path = ROOT / 'creative' / (spec['renderer'] + '.py')
    module_spec = importlib.util.spec_from_file_location('episode_renderer', path)
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    return module


def render(spec, out, seconds=None, width=1080):
    from PIL import ImageDraw
    module = load_renderer(spec, out)
    tl = json.loads((Path(out) / 'timeline.json').read_text())
    total = min(tl['total'], seconds) if seconds else tl['total']
    fps = 24
    height = width * 16 // 9
    height += height % 2
    target = Path(out) / 'silent.mp4'
    proc = subprocess.Popen(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-f', 'rawvideo',
                             '-pix_fmt', 'rgb24', '-s', f'{width}x{height}', '-r', str(fps), '-i', '-', '-an',
                             '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '19', '-pix_fmt', 'yuv420p', str(target)], stdin=subprocess.PIPE)
    sample_times = [max(0, min(total-0.05, ln['start'] + 0.6)) for ln in tl['lines'] if ln['start'] < total]
    sample_frames = {round(t*fps): i for i, t in enumerate(sample_times)}
    frames_dir = Path(out) / 'frames'
    frames_dir.mkdir(exist_ok=True)
    previous_idx = None
    try:
        for fr in range(math.ceil(total*fps)):
            t = fr/fps
            ln = module.line_at(t)
            beat = ln['beat']
            frame = module.beat_frame(beat, t)
            dt = t - ln['start']
            # Preserve the original short transitions when the selected renderer declares them.
            if hasattr(module, 'RIG_PREV') and beat in module.RIG_PREV and 0 <= dt < 0.35:
                frame = module.Image.blend(module.dialogue_frame(module.RIG_PREV[beat], ln['start']-0.001), frame, module.staging.smooth(dt/0.35))
            elif hasattr(module, 'AFTER_RIG') and beat in module.AFTER_RIG and 0 <= dt < 0.25:
                frame = module.Image.blend(module.rig_frame(module.AFTER_RIG[beat]-0.01), frame, module.staging.smooth(dt/0.25))
            elif hasattr(module, 'DLG_PREV') and beat in module.DLG_PREV and 0 <= dt < 0.25:
                frame = module.Image.blend(module.dialogue_frame(module.DLG_PREV[beat], ln['start']-0.001), frame, dt/0.25)
            draw = ImageDraw.Draw(frame, 'RGBA')
            draw.text((1010, 80), 'Y?', font=module.F_WM, fill=(245, 184, 65, 90), anchor='mm')
            if width != 1080:
                frame = frame.resize((width, height))
            if fr in sample_frames:
                frame.save(frames_dir / f'{sample_frames[fr]:02d}.jpg')
            proc.stdin.write(frame.convert('RGB').tobytes())
            previous_idx = ln['idx']
            if fr % 240 == 0:
                print(f'Render {fr}/{math.ceil(total*fps)}', flush=True)
    finally:
        proc.stdin.close()
        proc.wait()
    if proc.returncode:
        raise RuntimeError('Video encoding failed')
    return total


def mux(out, total):
    out = Path(out)
    tl = json.loads((out / 'timeline.json').read_text())
    inputs, filters, labels = [], [], []
    for i, ln in enumerate(tl['lines']):
        inputs += ['-i', str(out / ln['audio'])]
        filters.append(f'[{i}:a]adelay={round(ln["start"]*1000)}:all=1[a{i}]')
        labels.append(f'[a{i}]')
    graph = ';'.join(filters) + ';' + ''.join(labels) + f'amix=inputs={len(labels)}:normalize=0,apad,loudnorm=I=-18:TP=-2:LRA=9[a]'
    subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', *inputs, '-filter_complex', graph,
                    '-map', '[a]', '-t', str(total), '-c:a', 'aac', '-b:a', '192k', str(out/'narration.m4a')], check=True)
    subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-i', str(out/'silent.mp4'), '-i', str(out/'narration.m4a'),
                    '-c:v', 'copy', '-c:a', 'copy', '-movflags', '+faststart', '-shortest', str(out/'final.mp4')], check=True)
    # Portable subtitles retain service word boundaries in Edge mode.
    def stamp(t):
        ms = round(t*1000)
        return f'{ms//3600000:02d}:{ms//60000%60:02d}:{ms//1000%60:02d},{ms%1000:03d}'
    cues = []
    for ln in tl['lines']:
        for w in ln['words']:
            if w['start'] < total:
                cues.append(f'{len(cues)+1}\n{stamp(w["start"])} --> {stamp(min(w["end"],total))}\n{w["text"]}\n')
    (out/'captions.srt').write_text('\n'.join(cues))
