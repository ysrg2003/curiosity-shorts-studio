"""Opt-in integration proof only. No topic/science/model-quality acceptance."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import pytest

pytestmark=pytest.mark.skipif(os.environ.get('CURIOSITY_RUN_RENDER_TEST')!='1',reason='Opt-in Docker integration check, not a normal unit test')

SYNTHETIC_CODE='''from manim import *
class MainScene(Scene):
    def construct(self):
        env=__import__('os').environ
        assert 'OPENROUTER_API_KEY' not in env and 'GITHUB_TOKEN' not in env and 'SYNTHETIC_PRIVATE_DATA' not in env
        sock=__import__('socket').socket()
        sock.settimeout(0.5)
        assert sock.connect_ex(('1.1.1.1',443))!=0
        sock.close()
        circle=Circle(radius=0.7,color=BLUE,fill_opacity=0.8)
        self.play(Create(circle),run_time=0.6)
        self.play(circle.animate.move_to(RIGHT),run_time=0.6)
        self.play(circle.animate.set_color(YELLOW).move_to(ORIGIN),run_time=0.8)
        self.wait(0.2)
'''


def test_actual_generated_scene_boundary_and_portrait_pixels(monkeypatch,tmp_path):
    from curiosity import generated_motion,remote_ai,motion
    from curiosity.spec import write_json,digest
    monkeypatch.setenv('CURIOSITY_LLM_BACKEND','openrouter-free')
    monkeypatch.setenv('OPENROUTER_API_KEY','synthetic-not-a-provider-key')
    monkeypatch.setenv('GITHUB_TOKEN','synthetic-not-a-repository-token')
    monkeypatch.setenv('SYNTHETIC_PRIVATE_DATA','synthetic-environment-value')
    calls=[]
    def synthetic_response(*args,**kwargs):
        calls.append(True)
        return SYNTHETIC_CODE,{'backend':'synthetic-test','model':'no-service-called','usage':{'cost':'0'},'paid_fallback_allowed':False}
    monkeypatch.setattr(remote_ai,'request',synthetic_response)
    spec={'id':'synthetic-safety','renderer':'generic','visual_engine':'generated-manim'}
    timeline={'total':2.35,'lines':[{'idx':1,'start':0,'end':2,'text':'Synthetic motion check, not a scientific claim.','beat':'explain','diagram':['A','B'],'visual_direction':'A circle moves right, changes color and moves back. This tests plumbing only, not topic quality.'}]}
    write_json(tmp_path/'episode.json',spec);write_json(tmp_path/'timeline.json',timeline)
    generated_motion.prepare(spec,timeline,tmp_path,'synthetic-no-network-model')
    clips=motion.prepare(spec,timeline,tmp_path,1080);assert len(clips)==1 and len(calls)==1
    probe=json.loads(subprocess.run(['ffprobe','-v','error','-show_streams','-of','json',str(clips[1])],capture_output=True,text=True,check=True).stdout)
    video=next(x for x in probe['streams'] if x['codec_type']=='video')
    assert (video['width'],video['height'])==(1080,1920)
    reader=motion.Frames(clips[1],1080,1920);frames=[]
    try:
        for index in range(48):
            image=reader.next()
            if index in [15,40]:frames.append(image)
    finally:reader.close()
    from PIL import ImageChops
    assert ImageChops.difference(*frames).getbbox() is not None
    destination=Path(os.environ.get('CURIOSITY_SMOKE_OUT','output/sandbox-smoke'));destination.mkdir(parents=True,exist_ok=True)
    shutil.copy2(clips[1],destination/'synthetic-motion.mp4')
    for i,image in enumerate(frames):image.save(destination/f'frame-{i+1}.png')
    write_json(destination/'result.json',{'synthetic_only':True,'science_or_new_topic_acceptance':False,'real_model_calls':0,'network_connection_blocked':True,'credential_environment_absent':True,'portrait_pixels':[1080,1920],'different_sampled_frames':True,'video_sha256':digest(clips[1])})
