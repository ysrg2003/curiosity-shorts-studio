import json, math, os, subprocess
from PIL import Image, ImageDraw
import chars, staging
from explain import VestibularRig
from staging import W, H

FPS = 24
OUT = os.environ["CURIOSITY_WORKDIR"]
TL = json.load(open(f"{OUT}/timeline.json"))
TOTAL = TL["total"]
LINES = TL["lines"]

F_WM = staging.font(staging.QB, 34)

PIP_POS = (295, 930)
RAY_POS = (785, 930)
R_SPEAK = 250
R_LISTEN = 185
LISTENER_SAT = 0.88

BG_ZAP = staging.make_bg2(top=(40, 44, 92), bottom=(16, 18, 46), glow=(150, 140, 235), glow_xy=PIP_POS, glow_r=580)
BG_HOOK = staging.make_bg2(top=(64, 48, 74), bottom=(30, 22, 44), glow=(225, 175, 95), glow_xy=RAY_POS, glow_r=580)
BG_ASK = staging.make_bg2(glow=(70, 110, 200), glow_xy=PIP_POS, glow_r=560)
BG_WATCH = staging.make_bg2(top=(64, 48, 74), bottom=(30, 22, 44), glow=(225, 175, 95), glow_xy=RAY_POS, glow_r=560)
BG_RIG = staging.make_bg2(top=(18, 30, 60), bottom=(8, 12, 30), glow=(70, 110, 190), glow_xy=(470, 900), glow_r=780)
BG_GAG = staging.make_bg2(glow=(90, 150, 230), glow_xy=PIP_POS, glow_r=580)
BG_FINALE = staging.make_bg2(top=(60, 46, 70), bottom=(28, 20, 42), glow=(225, 175, 95), glow_xy=RAY_POS, glow_r=580)
BG_REACT = staging.make_bg2(glow=(90, 150, 230), glow_xy=PIP_POS, glow_r=580)

BEAT_BG = dict(zap=BG_ZAP, hook=BG_HOOK, ask=BG_ASK, watch=BG_WATCH,
               ask2=BG_ASK, gag=BG_GAG, finale=BG_FINALE, react=BG_REACT)

RIG = VestibularRig()

# line indices
(L_ZAP, L_HOOK, L_ASK, L_WATCH, L_EXPLAIN, L_EXPLAIN1B, L_ASK2,
 L_EXPLAIN2, L_EXPLAIN2B, L_GAG, L_FINALE, L_REACT) = range(12)

RIG_BEATS = ("explain", "explain1b", "explain2", "explain2b")
CAPS = {i: staging.KaraokeCap(ln["words"]) for i, ln in enumerate(LINES)
        if ln["beat"] not in RIG_BEATS}

def speaking(ln, t):
    return any(w["start"] - 0.03 <= t <= w["end"] + 0.07 for w in ln["words"])

def word_time(li, text, which="start", occurrence=0):
    hits = [w for w in LINES[li]["words"] if w["text"].strip(".,!?").upper() == text]
    if not hits:
        return None
    w = hits[min(occurrence, len(hits) - 1)]
    return w[which]

# ---------------- rig timing anchors
T_EX0 = LINES[L_EXPLAIN]["start"]
T_SPIN = word_time(L_EXPLAIN, "spin") or T_EX0 + 1.5
T_LAGS = word_time(L_EXPLAIN, "lags") or T_SPIN + 1.5
T_BEND = word_time(L_EXPLAIN, "bends") or T_LAGS + 1.2
T_TELLS = word_time(L_EXPLAIN, "SPINNING") or T_BEND + 2.0
T_EX_END = LINES[L_EXPLAIN]["end"]

T_B0 = LINES[L_EXPLAIN1B]["start"]
T_CATCH = word_time(L_EXPLAIN1B, "catches") or T_B0 + 1.5
T_STRAIGHT = word_time(L_EXPLAIN1B, "straighten") or T_CATCH + 2.0
T_B_END = LINES[L_EXPLAIN1B]["end"]

T_C0 = LINES[L_EXPLAIN2]["start"]
T_KEEPS = word_time(L_EXPLAIN2, "keeps") or T_C0 + 1.0
T_OTHER = word_time(L_EXPLAIN2, "OTHER") or T_KEEPS + 1.6
T_HEARS = word_time(L_EXPLAIN2, "SPINNING") or T_OTHER + 1.8
T_SEES = word_time(L_EXPLAIN2, "STILL") or T_HEARS + 1.2
T_C_END = LINES[L_EXPLAIN2]["end"]

T_D0 = LINES[L_EXPLAIN2B]["start"]
T_MIXED = word_time(L_EXPLAIN2B, "mixed") or T_D0 + 0.6
T_DIZZY = word_time(L_EXPLAIN2B, "dizziness") or T_MIXED + 1.0
T_D_END = LINES[L_EXPLAIN2B]["end"]

# fluid velocity keyframes (cycles/sec, head frame; linear ramps between)
FLUID_KEYS = [
    (0.0, 0.0),
    (T_SPIN, 0.0),
    (T_LAGS + 0.6, -0.10),      # spin start: fluid lags backward
    (T_CATCH + 0.4, 0.0),       # catches up: still relative to canal
    (T_KEEPS + 0.5, 0.0),       # constant spin: still
    (T_OTHER + 0.5, 0.10),      # head stopped: fluid keeps going forward
    (T_D_END, 0.10),            # still going through the reveal
    (LINES[L_FINALE]["start"] + 3.0, 0.0),  # settles by the finale
    (TOTAL, 0.0),
]

def fluid_vel(t):
    ks = FLUID_KEYS
    if t <= ks[0][0]:
        return ks[0][1]
    for i in range(1, len(ks)):
        if t <= ks[i][0]:
            t0, v0 = ks[i - 1]
            t1, v1 = ks[i]
            p = (t - t0) / max(1e-6, t1 - t0)
            return v0 + (v1 - v0) * p
    return ks[-1][1]

def fluid_phase(t):
    # trapezoid integral of fluid_vel at 0.1s steps (plenty smooth)
    ph = 0.0
    tt = 0.0
    while tt < t:
        dt = min(0.1, t - tt)
        ph += 0.5 * (fluid_vel(tt) + fluid_vel(tt + dt)) * dt
        tt += dt
    return ph

def rig_params(t):
    spin_p = staging.smooth((t - T_SPIN) / 0.8) * (1 - staging.smooth((t - T_KEEPS + 0.3) / 0.8))
    if t < T_SPIN:
        bend = 0.0
    elif t < T_CATCH:
        bend = -staging.smooth((t - T_LAGS) / 1.0)
    elif t < T_KEEPS:
        bend = -1.0 + staging.smooth((t - T_CATCH) / 1.0)
    elif t < T_D_END + 2.0:
        bend = staging.smooth((t - T_OTHER) / 1.0)
    else:
        bend = max(0.0, 1 - (t - (T_D_END + 2.0)) / 2.0)
    return spin_p, fluid_phase(t), bend

LABELS_A = [
    (staging.LeaderLabel("you spin!", (250, 470), "left"), T_SPIN - 0.2),
    (staging.LeaderLabel("fluid lags behind", (830, 620), "right"), T_LAGS - 0.2),
    (staging.LeaderLabel("hairs bend", (240, 1420), "left"), T_BEND - 0.2),
    (staging.LeaderLabel('"we\'re SPINNING!"', (300, 300), "left"), T_TELLS - 0.3),
]
LABELS_B = [
    (staging.LeaderLabel("fluid catches up", (800, 560), "right"), T_CATCH - 0.2),
    (staging.LeaderLabel("hairs straighten", (260, 1420), "left"), T_STRAIGHT - 0.2),
]
LABELS_C = [
    (staging.LeaderLabel("you STOP", (260, 470), "left"), T_C0 + 0.2),
    (staging.LeaderLabel("fluid keeps going!", (810, 620), "right"), T_KEEPS - 0.2),
    (staging.LeaderLabel("hairs bend the OTHER way", (430, 1600), "left"), T_OTHER - 0.2),
    (staging.LeaderLabel("ears: SPINNING", (300, 320), "left"), T_HEARS - 0.3),
    (staging.LeaderLabel("eyes: STILL", (880, 1380), "right"), T_SEES - 0.3),
]
LABELS_D = [
    (staging.LeaderLabel("mixed signal = DIZZY!", (540, 240), "right"), T_DIZZY - 0.4),
]
def labels_at(t):
    if t < T_B0:
        return LABELS_A
    if t < T_C0:
        return LABELS_B
    if t < T_D0:
        return LABELS_C
    return LABELS_D

def head_tile(who, r, expr, talking, t, blink_on, glasses=False, glasses_p=1.0,
              turn=0.0):
    f = chars.preset(expr, who)
    if talking:
        f["mouth"] = "open"
        f["m_open"] = 0.35 + 0.35 * abs(math.sin(t * 13))
    return chars.render_head(who, r, f, glasses=glasses, glasses_p=glasses_p,
                             blink=blink_on, turn=turn)

def draw_two_shot(frame, speaker, ln, t, expr, glasses_ray=False, ray_gp=1.0, action=None):
    order = []
    for who, pos, is_spk in (("PIP", PIP_POS, speaker == "PIP"), ("RAY", RAY_POS, speaker == "RAY")):
        order.append((who, pos, is_spk))
    order.sort(key=lambda o: o[2])
    for who, (px, py), is_spk in order:
        turn = 0.7 if who == "PIP" else -0.7
        expr_w = expr if is_spk else "listening"
        r = R_SPEAK if is_spk else R_LISTEN
        talking = is_spk and speaking(ln, t)
        blink = ((t + (1.1 if who == "PIP" else 2.4)) % (3.7 if who == "PIP" else 4.1)) < 0.09 and not talking
        glasses = (who == "RAY") and glasses_ray
        tile = head_tile(who, r, expr_w, talking, t, blink, glasses, ray_gp, turn=turn)
        if not is_spk:
            g = tile.convert("L").convert("RGBA")
            g.putalpha(tile.getchannel("A"))
            tile = Image.blend(g, tile, LISTENER_SAT)
        if is_spk:
            tr = dict(dy=2.4 * math.sin(t * 1.7), rot=-4.0 * turn)
            if action:
                p = min(1.0, (t - ln["start"]) / action[1])
                a = chars.ACTIONS[action[0]](p)
                a["rot"] = a.get("rot", 0) + tr["rot"]
                tr.update(a)
            chars.place_head(frame, tile, px + tr.get("dx", 0), py + tr.get("dy", 0),
                             rot=tr.get("rot", 0), scale=tr.get("scale", 1.0),
                             squash=tr.get("squash", 1.0))
        else:
            nod = 0.0
            tail = ln["end"] - t
            if 0 < tail < 0.6:
                nod = 3.0 * math.sin((0.6 - tail) / 0.6 * math.pi)
            chars.place_head(frame, tile, px, py + 1.6 * math.sin(t * 0.9),
                             rot=-4.0 * turn + nod)

def draw_caption(frame, li, t):
    cap = CAPS[li]
    for c in range(cap.n_lines()):
        st, en = cap.span(c)
        if st <= t < en:
            idxs = cap.lines[c]
            cw = -1
            for i in idxs:
                w = cap.words[i]
                if w["start"] - 0.02 <= t <= w["end"] + 0.12:
                    cw = i
            img = cap.render(c, cw)
            frame.paste(img, ((W - img.width) // 2, staging.KaraokeCap.Y), img)
            break

def draw_prop(frame, kind, who, t, line_t):
    pop = min(1.0, line_t / 0.22)
    if pop <= 0:
        return
    d = ImageDraw.Draw(frame, "RGBA")
    cx, cy = PIP_POS if who == "PIP" else RAY_POS
    y = cy - R_SPEAK - 78 + 8 * math.sin(t * 2.2)
    if kind in ("?", "!", "!?"):
        col = (245, 184, 65) if kind == "?" else (235, 110, 75)
        d.text((cx, y), kind, font=staging.font(staging.QB, int(104 * pop)),
               fill=col, anchor="mm", stroke_width=5, stroke_fill=(16, 27, 51))
    elif kind == "stars":
        for k in range(3):
            chars._star(d, cx + (k - 1) * 120, y + (k % 2) * -30,
                        (16 + 6 * math.sin(t * 4 + k)) * pop, (255, 226, 120))
    elif kind == "dizzy":
        # swirl circling the dizzy head
        for k in range(4):
            a = t * 4.5 + k * math.pi / 2
            rr = 150
            sx = cx + rr * math.cos(a)
            sy = y + 30 + 46 * math.sin(a)
            chars._star(d, sx, sy, (11 + 4 * math.sin(t * 5 + k)) * pop, (255, 226, 120))
    elif kind == "coffee":
        s = pop
        cx = cx - 150
        y = y - 40
        # mug
        d.rounded_rectangle([cx - 56 * s, y - 20 * s, cx + 56 * s, y + 78 * s],
                            radius=14 * s, fill=(235, 240, 245), outline=(170, 180, 195), width=5)
        d.arc([cx + 34 * s, y + 4 * s, cx + 88 * s, y + 58 * s], -80, 80,
              fill=(170, 180, 195), width=int(12 * s) + 3)
        # coffee surface
        d.ellipse([cx - 48 * s, y - 26 * s, cx + 48 * s, y - 4 * s], fill=(122, 78, 46),
                  outline=(86, 52, 28), width=4)
        # swirl in the coffee
        for k in range(2):
            a = t * 3.5 + k * math.pi
            sx = cx + 22 * s * math.cos(a)
            sy = y - 15 * s + 7 * s * math.sin(a)
            d.ellipse([sx - 6 * s, sy - 6 * s, sx + 6 * s, sy + 6 * s], fill=(160, 110, 70))
        # steam
        for k in range(2):
            cyc = (t * 0.45 + k / 2) % 1.0
            sx = cx - 16 + k * 30 + 8 * math.sin(t * 2 + k)
            sy = y - 34 * s - cyc * 60
            d.line([(sx, sy), (sx + 6, sy - 16)], fill=(220, 225, 235, int(160 * (1 - cyc))), width=5)

def draw_specks(frame, t, alpha=1.0):
    d = ImageDraw.Draw(frame, "RGBA")
    for k in range(14):
        cyc = (t * 0.10 + k / 14) % 1.0
        sx = 60 + k * 74 + 34 * math.sin(t * 0.6 + k * 2.1)
        sy = -40 + cyc * 2000
        a = 170 * alpha * (0.35 + 0.65 * ((k * 37) % 10) / 10)
        chars._star(d, sx, sy, 6 + (k % 4) * 3, (200, 220, 250, int(a)))

# ---------------------------------------------------------------- rig frame
def rig_frame(t):
    spin_p, ph, bend = rig_params(t)
    beat_t = min(1.0, max(0.0, (t - T_EX0) / (T_D_END - T_EX0)))
    scale = staging.push_in(beat_t, 0.08)
    img = BG_RIG.copy()
    RIG.draw(img, spin_p=spin_p, fluid_ph=ph, bend_p=bend, t=t)
    if scale > 1.001:
        sw, sh = int(W * scale), int(H * scale)
        big = img.resize((sw, sh), Image.LANCZOS)
        cx, cy = int(540 * scale), int(950 * scale)
        img = big.crop((max(0, cx - W // 2), max(0, cy - H // 2),
                        max(0, cx - W // 2) + W, max(0, cy - H // 2) + H))
    d = ImageDraw.Draw(img, "RGBA")
    labs = labels_at(t)
    active = -1
    for i, (lab, t0) in enumerate(labs):
        if t >= t0:
            active = i
    for i, (lab, t0) in enumerate(labs):
        if t < t0:
            continue
        lab.draw(d, (t - t0) / 0.55, dim=1.0 if i == active else 0.30)
    return img

# ------------------------------------------------------------ dialogue beats
def dialogue_frame(beat, t):
    frame = BEAT_BG[beat].copy()
    if beat == "zap":
        draw_specks(frame, t)
        ln = LINES[L_ZAP]
        draw_two_shot(frame, "PIP", ln, t, "worried", action=("tremble", 2.6))
        draw_prop(frame, "dizzy", "PIP", t, t - ln["start"])
        draw_caption(frame, L_ZAP, t)
        return frame
    if beat == "hook":
        ln = LINES[L_HOOK]
        draw_two_shot(frame, "RAY", ln, t, "smart")
        draw_prop(frame, "!", "RAY", t, t - ln["start"])
        draw_caption(frame, L_HOOK, t)
        return frame
    if beat == "ask":
        ln = LINES[L_ASK]
        draw_two_shot(frame, "PIP", ln, t, "confused", action=("lean_in", 3.2))
        draw_prop(frame, "?", "PIP", t, t - ln["start"])
        draw_caption(frame, L_ASK, t)
        return frame
    if beat == "watch":
        ln = LINES[L_WATCH]
        line_t = t - ln["start"]
        gp = min(1.0, max(0.0, line_t / 0.55))
        draw_two_shot(frame, "RAY", ln, t, "smart", glasses_ray=True, ray_gp=gp,
                      action=("nod", 1.4))
        if 0.45 < line_t < 1.0:
            p = (line_t - 0.45) / 0.55
            d = ImageDraw.Draw(frame, "RGBA")
            for k in range(6):
                a = k * math.pi / 3 + t * 2
                rr = 110 + 110 * p
                chars._star(d, RAY_POS[0] + rr * math.cos(a), RAY_POS[1] - 60 + rr * 0.55 * math.sin(a),
                            13 * (1 - p), (255, 226, 120, int(220 * (1 - p))))
        draw_caption(frame, L_WATCH, t)
        if t > ln["end"] - 0.15:
            p = (t - (ln["end"] - 0.15)) / 0.5
            staging.iris_open(frame, rig_frame(T_EX0 + 0.01), p, center=(540, 940))
        return frame
    if beat == "ask2":
        ln = LINES[L_ASK2]
        draw_two_shot(frame, "PIP", ln, t, "confused", glasses_ray=True, action=("head_bob", 2.4))
        draw_prop(frame, "?", "PIP", t, t - ln["start"])
        draw_caption(frame, L_ASK2, t)
        return frame
    if beat == "gag":
        ln = LINES[L_GAG]
        t_juice = word_time(L_GAG, "juice") or ln["end"] - 1.0
        expr = "confused" if t < t_juice else "delighted"
        draw_two_shot(frame, "PIP", ln, t, expr, glasses_ray=True, action=("double_take", 2.8))
        draw_prop(frame, "!?", "PIP", t, t - ln["start"])
        draw_caption(frame, L_GAG, t)
        return frame
    if beat == "finale":
        ln = LINES[L_FINALE]
        draw_two_shot(frame, "RAY", ln, t, "proud", glasses_ray=True, action=("nod", 1.6))
        draw_caption(frame, L_FINALE, t)
        return frame
    # react
    ln = LINES[L_REACT]
    line_t = t - ln["start"]
    expr = "amazed" if line_t < 0.9 else "delighted"
    draw_two_shot(frame, "PIP", ln, t, expr, glasses_ray=True)
    draw_prop(frame, "coffee", "PIP", t, line_t)
    draw_caption(frame, L_REACT, t)
    return frame

# ---------------------------------------------------------------- main loop
def beat_frame(beat, t):
    if beat in RIG_BEATS:
        return rig_frame(t)
    return dialogue_frame(beat, t)

def line_at(t):
    for ln in LINES:
        if ln["start"] <= t < ln["end"] + 0.35:
            return ln
    return LINES[-1]

def main():
    frames_total = int(os.environ.get("FRAMES_LIMIT", int(TOTAL * FPS) + 1))
    start_frame = int(os.environ.get("START_FRAME", 0))
    seg = os.environ.get("SEG", "")
    cmd = ["ffmpeg", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
           "-i", "-", "-an", "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p", "-crf", "19",
           f"{OUT}/silent{seg}.mp4"]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    prev_li = None
    for fr in range(start_frame, frames_total):
        t = fr / FPS
        ln = line_at(t)
        li = ln["idx"]
        beat = ln["beat"]
        frame = beat_frame(beat, t)
        # crossfades back into dialogue from rig beats
        if beat in ("ask2", "gag", "finale", "react"):
            dt = t - ln["start"]
            win = 0.25 if beat in ("ask2", "gag") else 0.2
            if 0 <= dt < win:
                if beat == "ask2":
                    prev = rig_frame(T_B_END - 0.01)
                elif beat == "gag":
                    prev = rig_frame(T_D_END - 0.01)
                elif beat == "finale":
                    prev = dialogue_frame("gag", ln["start"] - 0.001)
                else:
                    prev = dialogue_frame("finale", ln["start"] - 0.001)
                frame = Image.blend(prev, frame, staging.smooth(dt / win))
        # crossfade ask2 -> explain2 (back into the rig)
        if beat == "explain2":
            dt = t - ln["start"]
            if 0 <= dt < 0.35:
                prev = dialogue_frame("ask2", ln["start"] - 0.001)
                frame = Image.blend(prev, frame, staging.smooth(dt / 0.35))
        # crossfade zap -> hook / hook -> ask / ask -> watch (bg changes)
        if beat in ("hook", "ask", "watch"):
            dt = t - ln["start"]
            prev_beat = {"hook": "zap", "ask": "hook", "watch": "ask"}[beat]
            if 0 <= dt < 0.25:
                prev = dialogue_frame(prev_beat, ln["start"] - 0.001)
                frame = Image.blend(prev, frame, dt / 0.25)
        prev_li = li
        d = ImageDraw.Draw(frame, "RGBA")
        d.text((W - 70, 80), "Y?", font=F_WM, fill=(245, 184, 65, 90), anchor="mm")
        proc.stdin.write(frame.convert("RGB").tobytes())
        if fr % 120 == 0:
            print(f"frame {fr}/{frames_total}", flush=True)
    proc.stdin.close(); proc.wait()
    if proc.returncode:
        raise RuntimeError("Video encoder failed")
    print("silent done:", proc.returncode)

if __name__ == "__main__":
    main()
