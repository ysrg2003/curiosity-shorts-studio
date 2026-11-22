"""Prepare bounded Manim scenes and decode them into the final frame compositor."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
from .spec import ROOT


def prepare(spec,timeline,out,width):
    if spec.get('visual_engine')=='generated-manim':
        if width!=1080:raise ValueError('Generated-scene compositor currently requires1080pixels')
        from .generated_motion import prepared
        return prepared(spec,timeline,out)
    config=json.loads((ROOT/'studio.json').read_text())
    if spec['renderer']!='generic' or config.get('motion_renderer')!='manim':return {}
    module_spec=importlib.util.spec_from_file_location('curiosity_motion_scene',ROOT/'creative/motion_scene.py')
    module=importlib.util.module_from_spec(module_spec);module_spec.loader.exec_module(module)
    out=Path(out)/'motion';out.mkdir(exist_ok=True)
    result={}
    for line in timeline['lines']:
        if line['beat']!='explain':continue
        beat={k:line.get(k) for k in ['diagram','visual_type','visual_title']}
        beat['duration']=line['end']-line['start']+0.35
        key=hashlib.sha256(json.dumps([beat,width,hashlib.sha256((ROOT/'creative/motion_scene.py').read_bytes()).hexdigest()],sort_keys=True).encode()).hexdigest()[:16]
        target=out/f'beat-{line["idx"]:02d}-{key}.mp4'
        if not target.exists():module.render_scene(beat,target,width)
        result[line['idx']]=target
    return result


class Frames:
    def __init__(self,path,width,height):
        self.width,self.height=width,height
        self.process=subprocess.Popen(['ffmpeg','-hide_banner','-loglevel','error','-threads','1','-i',str(path),'-f','rawvideo','-pix_fmt','rgb24','-'],stdout=subprocess.PIPE)
        self.last=None;self.missing=0
    def next(self):
        from PIL import Image
        raw=self.process.stdout.read(self.width*self.height*3)
        if len(raw)==self.width*self.height*3:self.last=Image.frombytes('RGB',(self.width,self.height),raw)
        elif raw or self.last is None:raise RuntimeError('Incomplete motion frame')
        if not raw:
            self.missing+=1
            if self.missing>3:raise RuntimeError('Motion scene ended too early')
        return self.last.copy()
    def close(self):
        self.process.stdout.close()
        if self.process.poll() is None:self.process.terminate()
        self.process.wait()
