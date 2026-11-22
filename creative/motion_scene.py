"""CPU-rendered mechanism scenes using Manim Community (MIT).

Scene selection and labels are data. No generated Python or external code is run.
"""
from pathlib import Path
import math
from manim import (Scene,VGroup,Rectangle,RoundedRectangle,Circle,Ellipse,Line,Dot,
                   Arrow,Text,VMobject,Create,FadeIn,FadeOut,Transform,Rotate,
                   MoveAlongPath,Indicate,tempconfig,UP,DOWN,LEFT,RIGHT,ORIGIN,
                   linear,smooth)
import manimpango

ROOT=Path(__file__).resolve().parents[1]
for font in (ROOT/'creative/fonts').glob('*.ttf'):
    manimpango.register_font(str(font))
INK='#F4EFE3'; GOLD='#F5B841'; BLUE='#73B9DF'; TEAL='#6AD2BD'; BG='#111B34'


def label(text,size=38,color=INK,max_width=7.7):
    words=str(text).strip()[:80].split(); rows=[]; row=[]
    for word in words:
        if row and len(' '.join(row+[word]))>25:rows.append(' '.join(row));row=[]
        row.append(word)
    if row:rows.append(' '.join(row))
    obj=Text('\n'.join(rows[:2]),font='Quicksand',font_size=size,color=color,line_spacing=0.85,weight='BOLD')
    if obj.width>max_width:obj.scale_to_fit_width(max_width)
    return obj


class MechanismScene(Scene):
    def __init__(self,beat,**kwargs):self.beat=beat;super().__init__(**kwargs)
    def construct(self):
        duration=max(2.0,float(self.beat['duration']))
        self.camera.background_color=BG
        self.add(Line([-3.9,6.2,0],[3.9,6.2,0],color=GOLD,stroke_width=2))
        self.add(label(self.beat.get('visual_title','THE CAUSE AND EFFECT'),42,GOLD).move_to([0,6.75,0]))
        labels=self.beat.get('diagram') or ['A SIGNAL','A RESPONSE','AN EFFECT']
        if self.beat.get('visual_type')=='skin_hair':self.skin_hair(labels,duration)
        else:self.flow(labels,duration)

    def skin_hair(self,labels,duration):
        self.add(label('STYLIZED CROSS-SECTION',22,'#AEBBD1').move_to([0,-3.9,0]))
        skin=RoundedRectangle(width=7.6,height=3.3,corner_radius=0.35,
                              fill_color='#C58D72',fill_opacity=1,stroke_color='#F0C6A4',stroke_width=4).shift(DOWN*0.9)
        layers=VGroup(*[Line([-3.7,y,0],[3.7,y,0],stroke_color='#A76660',stroke_opacity=0.4,stroke_width=2) for y in [-0.5,-1.3,-2.1]])
        root=[0,-1.9,0]
        follicle=Ellipse(width=0.9,height=2.4,fill_color='#A95756',fill_opacity=1,
                         stroke_color='#F3B797',stroke_width=4).move_to([0,-1,0]).rotate(-0.22)
        hair=Line(root,[1.1,2.7,0],color='#F0D7B5',stroke_width=20)
        hair_inner=Line(root,[1.1,2.7,0],color='#765047',stroke_width=9)
        hairs=VGroup(hair,hair_inner)
        muscle=Line([-2.7,-0.3,0],[0,-1.5,0],color='#F29483',stroke_width=24)
        muscle_fibres=VGroup(*[Line([-2.65+i*.25,-.33-i*.11,0],[-2.50+i*.25,-.10-i*.11,0],color='#FFCFAD',stroke_width=3) for i in range(10)])
        nerve=VMobject(color=GOLD,stroke_width=7).set_points_smoothly([[-3.6,-3.2,0],[-2.9,-2.7,0],[-3.2,-1.6,0],[-2.7,-.3,0]])
        self.play(FadeIn(VGroup(skin,layers,follicle,hairs,muscle,muscle_fibres)),Create(nerve),run_time=.55)
        stages=max(2,len(labels)); each=(duration-.55)/stages
        current=None
        for i in range(stages):
            text=label(labels[min(i,len(labels)-1)],43,GOLD).move_to([0,4.5,0])
            changes=[FadeIn(text)]
            if current is not None:changes.append(FadeOut(current))
            self.play(*changes,run_time=min(.3,each*.2)); current=text
            action_time=min(.85,each*.45)
            if i==0:
                pulse=Dot(nerve.get_start(),radius=.15,color='#FFF2B2');self.add(pulse)
                self.play(MoveAlongPath(pulse,nerve,rate_func=linear),run_time=action_time);self.remove(pulse)
            elif i==1:
                contracted=Line([-2.7,-0.3,0],[-.4,-1.2,0],color='#F29483',stroke_width=27)
                contracted_fibres=VGroup(*[Line([-2.65+i*.23,-.33-i*.09,0],[-2.50+i*.23,-.10-i*.09,0],color='#FFCFAD',stroke_width=3) for i in range(10)])
                self.play(Transform(muscle,contracted),Transform(muscle_fibres,contracted_fibres),Rotate(hairs,angle=.25,about_point=root),Rotate(follicle,angle=.20,about_point=root),run_time=action_time)
            else:
                bump=VMobject(color='#FFD5B2',stroke_width=9).set_points_smoothly([[-1.0,.74,0],[-.45,.85,0],[0,1.18,0],[.45,.85,0],[1.0,.74,0]])
                self.play(Create(bump),Indicate(follicle,color=GOLD,scale_factor=1.035),run_time=action_time)
            self.wait(max(0,each-min(.3,each*.2)-action_time))

    def flow(self,labels,duration):
        n=min(4,max(2,len(labels))); ys=[3.5-i*(7/(n-1)) for i in range(n)]
        nodes=[]
        for i,y in enumerate(ys):
            color=[BLUE,TEAL,GOLD,'#F39E91'][i]
            ring=Circle(radius=.58,stroke_color=color,stroke_width=6,fill_color=BG,fill_opacity=1).move_to([-2.7,y,0])
            dots=VGroup(*[Dot([-2.7+.26*math.cos(a),y+.26*math.sin(a),0],radius=.055,color=color) for a in [0,1.6,3.2,4.8]])
            text=label(labels[min(i,len(labels)-1)],40,INK,max_width=5.1).move_to([.6,y,0])
            nodes.append(VGroup(ring,dots,text))
        each=duration/n
        for i,node in enumerate(nodes):
            intro=min(.4,each*.2);self.play(FadeIn(node,shift=RIGHT*.2),run_time=intro)
            action=min(.8,each*.45)
            if i:
                arrow=Arrow([-2.7,ys[i-1]-.7,0],[-2.7,ys[i]+.7,0],color=GOLD,stroke_width=6,buff=0)
                self.play(Create(arrow),run_time=action*.45)
                pulse=Dot(arrow.get_start(),radius=.13,color='#FFF1AD');self.add(pulse)
                self.play(MoveAlongPath(pulse,arrow),Indicate(node[0],scale_factor=1.1,color=GOLD),run_time=action*.55);self.remove(pulse)
            else:self.play(Indicate(node[0],scale_factor=1.12,color=GOLD),run_time=action)
            self.wait(max(0,each-intro-action))


def render_scene(beat,target,width=1080):
    target=Path(target).resolve();target.parent.mkdir(parents=True,exist_ok=True)
    settings={'pixel_width':width,'pixel_height':width*16//9,'frame_width':9,'frame_height':16,
              'frame_rate':24,'renderer':'cairo','media_dir':str(target.parent/'cache'),
              'output_file':target.stem,'disable_caching':True,'write_to_movie':True,
              'verbosity':'WARNING','progress_bar':'none'}
    with tempconfig(settings):
        scene=MechanismScene(beat);scene.render()
        result=Path(scene.renderer.file_writer.movie_file_path)
        if result!=target:target.write_bytes(result.read_bytes())
    return target


if __name__=='__main__':
    import argparse,json
    p=argparse.ArgumentParser();p.add_argument('--beat',required=True);p.add_argument('--out',required=True);p.add_argument('--width',type=int,default=1080)
    a=p.parse_args();render_scene(json.loads(Path(a.beat).read_text()),a.out,a.width)
