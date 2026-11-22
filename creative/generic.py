"""Data-driven dialogue and causal diagram renderer for newly generated topics."""
import json
import math
import os
from PIL import Image, ImageDraw
import chars
import staging
from staging import W,H

TL=json.load(open(os.path.join(os.environ['CURIOSITY_WORKDIR'],'timeline.json')))
LINES=TL['lines']
F_WM=staging.font(staging.QB,34)
BG=staging.make_bg2(top=(26,34,66),bottom=(10,16,36),glow=(90,135,220),glow_xy=(540,880),glow_r=700)
CAPS={x['idx']:staging.KaraokeCap(x['words']) for x in LINES}


def line_at(t):
    return next((x for x in LINES if x['start']<=t<x['end']+0.35),LINES[-1])


def wrap(text,font,width):
    words=text.split(); rows=[]; row=''
    for w in words:
        candidate=(row+' '+w).strip()
        if font.getlength(candidate)>width and row:
            rows.append(row);row=w
        else:row=candidate
    if row: rows.append(row)
    return rows


def caption(frame,ln,t):
    cap=CAPS[ln['idx']]
    for c in range(cap.n_lines()):
        st,en=cap.span(c)
        if st<=t<en:
            current=next((i for i in cap.lines[c] if cap.words[i]['start']-0.02<=t<=cap.words[i]['end']+0.12),-1)
            image=cap.render(c,current)
            frame.paste(image,((W-image.width)//2,staging.KaraokeCap.Y),image)
            break


def dialogue_frame(beat,t):
    ln=line_at(t)
    frame=BG.copy()
    for who,cx in [('PIP',295),('RAY',785)]:
        active=ln['speaker']==who
        r=250 if active else 185
        expr=ln.get('expression','curious') if active else 'listening'
        expr={'curious':'curious','surprised':'surprised','happy':'happy','serious':'thinking'}.get(expr,'curious')
        f=dict(chars.PRESETS.get(expr,chars.PRESETS['neutral']))
        talking=active and any(w['start']<=t<=w['end'] for w in ln['words'])
        if talking:
            f['mouth']='open';f['m_open']=0.25+0.35*abs(math.sin(t*17))
        blink=math.sin(t*1.7+(0 if who=='PIP' else 1))>0.995
        if blink:f['eye_open']=0
        tile=chars.render_head(who,r,f,glasses=(who=='RAY'))
        # Library head tile is square RGBA; no body keeps the character silhouette.
        x=round(cx-tile.width/2);y=round(930-tile.height/2+math.sin(t*2.2)*6)
        frame.paste(tile,(x,y),tile)
    caption(frame,ln,t)
    return frame


def beat_frame(beat,t):
    if beat!='explain':return dialogue_frame(beat,t)
    ln=line_at(t); frame=BG.copy();d=ImageDraw.Draw(frame)
    title_font=staging.font(staging.QB,58)
    label_font=staging.font(staging.QB,43)
    d.text((540,210),'HOW IT HAPPENS',font=title_font,fill=(245,184,65),anchor='mm')
    labels=ln.get('diagram') or ['CAUSE','SIGNAL','EFFECT']
    p=staging.smooth((t-ln['start'])/max(0.1,ln['end']-ln['start']))
    for i,label in enumerate(labels):
        cy=440+i*290
        on=p>i/len(labels)
        color=(245,184,65) if on else (78,96,132)
        d.rounded_rectangle((145,cy-75,935,cy+75),radius=40,fill=(26,42,74),outline=color,width=5)
        rows=wrap(label.upper(),label_font,700)
        for j,row in enumerate(rows[:2]):
            d.text((540,cy+(j-(len(rows)-1)/2)*50),row,font=label_font,fill=(247,242,231),anchor='mm')
        if i<len(labels)-1:
            a,b=cy+86,cy+200
            d.line((540,a,540,b),fill=color,width=8)
            d.polygon([(520,b-18),(560,b-18),(540,b+5)],fill=color)
            dot=a+(b-a)*((t*0.8)%1)
            d.ellipse((530,dot-10,550,dot+10),fill=(245,184,65))
    caption(frame,ln,t)
    return frame
