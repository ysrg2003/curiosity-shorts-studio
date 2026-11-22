"""Reuse paper2video's generated-scene, lint and repair loop, never execute it on host."""
import importlib.util
import json
from pathlib import Path
import subprocess
from .spec import ROOT,write_json,digest
from .process_safety import scrubbed_subprocesses

PORTRAIT='''
=== NATIVE PORTRAIT GEOMETRY, REPLACES LEGACY LANDSCAPE/CROP VALUES ===
The fixed renderer uses frame_width9 and frame_height16, not a landscape crop.
Do not change config or camera geometry. Use dark navy background already configured.
All shapes/text must remain inside x=-3.7to3.7 and y=-3.8to5.8.
Below y=-4 is reserved for separately added captions. Keep that region empty.
No extra title, captions, faces or paragraphs. The spoken narration and caption layer handle words.
At most3short labels, font_size28to36, each1to3words, fit with shrink-only helper.
Illustrate actual objects, spatial relationships and physical changes from the source.
At least3visible animation changes. Do not replace the mechanism with generic cards or bullet lists.
Use self.play run_time to fill the requested duration, short pauses, final composition stays visible.
'''


def prepare(spec,timeline,bundle,model):
    from paper2video.renderers import manim_r
    from paper2video.types import Scene
    from .remote_ai import ModelOutputInvalid,ModelRequestFailed,UnexpectedModelCost
    hook=importlib.util.spec_from_file_location('curiosity_upstream_adapter',ROOT/'experiments/upstream_pipeline.py')
    adapter=importlib.util.module_from_spec(hook);hook.loader.exec_module(adapter)
    llm=adapter.LocalModel(model)
    out=Path(bundle)/'generated';out.mkdir(parents=True,exist_ok=True)
    old_system,old_portrait,old_runner,old_lint=manim_r.CODEGEN_SYSTEM,manim_r.PORTRAIT_ADDENDUM,manim_r._run_manim,manim_r.lint_manim_code
    # Keep the existing upstream reliability rules; replace its landscape-only safe-area section.
    import re
    manim_r.CODEGEN_SYSTEM=re.sub(r'=== SAFE AREA.*?=== END SAFE AREA ===',PORTRAIT,old_system,flags=re.S)
    manim_r.PORTRAIT_ADDENDUM=PORTRAIT
    manim_r._run_manim=adapter.isolated_manim
    manim_r.lint_manim_code=lambda code,social_mode=False:old_lint(code,social_mode=social_mode)+adapter.extra_lint(code)
    records={}
    try:
        with scrubbed_subprocesses():
            for line in timeline['lines']:
                if line['beat']!='explain':continue
                if not line.get('visual_direction'):raise ValueError('Missing source-grounded visual direction. No preset fallback.')
                duration=line['end']-line['start']+0.35
                scene=Scene(id=line['idx'],narration=line['text'],visual_type='manim',visual_spec={'direction':line['visual_direction'],'elements':line.get('diagram',[])},duration_hint_sec=duration)
                try:clip=manim_r.render_manim_scene(scene,duration,out,llm,quality='l',max_retries=2,resolution=(1080,1920))
                except (manim_r.ManimRenderError,ModelOutputInvalid,ModelRequestFailed,UnexpectedModelCost) as error:
                    write_json(out/'failure.json',{'scene':scene.id,'kind':type(error).__name__,'render_or_lint_error':error.stderr if isinstance(error,manim_r.ManimRenderError) else '', 'response_shape':error.metadata if isinstance(error,(ModelOutputInvalid,ModelRequestFailed)) else {},'model_calls':llm.calls});raise
                # Make the prepared clip exactly long enough for its existing audio-aligned timeline.
                target=out/f'beat-{line["idx"]:02d}.mp4'
                subprocess.run(['ffmpeg','-y','-hide_banner','-loglevel','error','-threads','2','-i',str(clip),'-vf',f'fps=24,tpad=stop_mode=clone:stop_duration={duration},trim=duration={duration},setpts=PTS-STARTPTS','-an','-c:v','libx264','-preset','veryfast','-pix_fmt','yuv420p',str(target)],check=True,timeout=120)
                records[str(line['idx'])]={'file':target.name,'sha256':digest(target),'duration':duration}
    finally:manim_r.CODEGEN_SYSTEM,manim_r.PORTRAIT_ADDENDUM,manim_r._run_manim,manim_r.lint_manim_code=old_system,old_portrait,old_runner,old_lint
    write_json(out/'prepared.json',{'episode_sha256':digest(Path(bundle)/'episode.json'),'timeline_sha256':digest(Path(bundle)/'timeline.json'),'clips':records,'model_calls':llm.calls,'upstream':adapter.UPSTREAM,'revision':adapter.REVISION,'preset_fallback':False,'generated_code_network':'none','generated_code_credentials':'none'})
    return records


def prepared(spec,timeline,bundle):
    """Final compositor consumes verified prepared files and never calls a model."""
    out=Path(bundle)/'generated';index=json.loads((out/'prepared.json').read_text());result={}
    if index.get('episode_sha256')!=digest(Path(bundle)/'episode.json') or index.get('timeline_sha256')!=digest(Path(bundle)/'timeline.json'):raise ValueError('Episode or timing changed after generated animation preparation')
    for line in timeline['lines']:
        if line['beat']!='explain':continue
        record=index['clips'].get(str(line['idx']))
        if not record or record['file']!=f'beat-{line["idx"]:02d}.mp4':raise ValueError('Missing generated clip. No preset fallback.')
        path=out/record['file']
        if path.is_symlink() or digest(path)!=record['sha256']:raise ValueError('Prepared animation changed after trusted preparation')
        result[line['idx']]=path
    return result
