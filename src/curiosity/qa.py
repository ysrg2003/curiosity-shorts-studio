"""Machine-readable media checks and a human review contact sheet."""
import json
from pathlib import Path
import re
import subprocess
from PIL import Image, ImageDraw
from .audio import duration
from .spec import write_json


def check(out, expected_duration, width=1080):
    out = Path(out)
    file = out / 'final.mp4'
    probe = json.loads(subprocess.run(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(file)],capture_output=True,text=True,check=True).stdout)
    video = next((s for s in probe['streams'] if s['codec_type']=='video'), {})
    audio = next((s for s in probe['streams'] if s['codec_type']=='audio'), {})
    result = {'has_video': bool(video), 'has_audio': bool(audio),
              'portrait_9_16': abs(video.get('width',0)/max(1,video.get('height',1))-9/16) < 0.002,
              'expected_width': video.get('width') == width,
              'duration_correct': abs(float(probe['format']['duration'])-expected_duration)<0.2,
              'shorts_duration': 1 < float(probe['format']['duration']) <= 180,
              'nonempty_file': file.stat().st_size>10000}
    volume = subprocess.run(['ffmpeg','-hide_banner','-i',str(file),'-af','volumedetect','-vn','-f','null','-'],capture_output=True,text=True,check=True).stderr
    match = re.search(r'mean_volume: ([-\d.]+) dB',volume)
    peak = re.search(r'max_volume: ([-\d.]+) dB',volume)
    result['audible'] = bool(match and -40<float(match[1])<-5)
    result['not_clipped'] = bool(peak and float(peak[1])<=-0.1)
    frames = sorted((out/'frames').glob('*.jpg'))
    result['has_review_frames'] = bool(frames)
    sheet = Image.new('RGB',(900, math_height(len(frames))), '#101b33')
    draw = ImageDraw.Draw(sheet)
    for i,path in enumerate(frames):
        im = Image.open(path).convert('RGB')
        im.thumbnail((210,374))
        x,y=(i%4)*225+7,(i//4)*400+5
        sheet.paste(im,(x,y))
        draw.text((x,y+376),f'Beat {i+1}',fill='white')
    sheet.save(out/'review.jpg',quality=90)
    report = {'checks':result,'pass':all(result.values()),'duration':float(probe['format']['duration']),
              'width':video.get('width'),'height':video.get('height'),
              'audio_mean_db':float(match[1]) if match else None,'audio_peak_db':float(peak[1]) if peak else None,
              'human_review_required':['Science and sources','Voice acting and pronunciation','Captions and diagram timing','No persistent transition ghosting','Mobile legibility and framing']}
    write_json(out/'qa.json',report)
    if not report['pass']:
        raise ValueError(f'Media QA failed: {result}')
    return report


def math_height(n):
    return max(400, ((n+3)//4)*400)
