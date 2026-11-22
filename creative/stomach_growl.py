import json, math, os, subprocess
from PIL import Image, ImageDraw
import chars, staging
from explain import GutRig
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
BG_RIG = staging.make_bg2(top=(34, 26, 50), bottom=(14, 10, 26), glow=(190, 140, 90), glow_xy=(540, 950), glow_r=800)
BG_GAG = staging.make_bg2(glow=(90, 150, 230), glow_xy=PIP_POS, glow_r=580)
BG_FINALE = staging.make_bg2(top=(60, 46, 70), bottom=(28, 20, 42), glow=(225, 175, 95), glow_xy=RAY_POS, glow_r=580)
BG_REACT = staging.make_bg2(glow=(90, 150, 230), glow_xy=PIP_POS, glow_r=580)

BEAT_BG = dict(zap=BG_ZAP, hook=BG_HOOK, ask=BG_ASK, ask2=BG_ASK, ask3=BG_ASK,
               watch=BG_WATCH, gag=BG_GAG, gag2=BG_GAG, gag3=BG_GAG,
               finale=BG_FINALE, react=BG_REACT)

RIG = GutRig()

(L_ZAP, L_HOOK, L_ASK, L_EXPLAIN, L_ASK2, L_EXPLAIN1B, L_GAG, L_EXPLAIN2,
 L_ASK3, L_EXPLAIN2B, L_GAG2, L_WATCH, L_GAG3, L_FINALE, L_REACT) = range(15)

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
T_MUSCLE = word_time(L_EXPLAIN, "muscle", occurrence=0) or T_EX0 + 1.0
T_TUBE = word_time(L_EXPLAIN, "tube") or T_EX0 + 2.2
T_SQUEEZES = word_time(L_EXPLAIN, "squeeze") or T_EX0 + 4.2
T_EX_END = LINES[L_EXPLAIN]["end"]

T_B0 = LINES[L_EXPLAIN1B]["start"]
T_FOOD = word_time(L_EXPLAIN1B, "Food") or T_B0 + 0.6
T_PUSH = word_time(L_EXPLAIN1B, "pushes") or T_B0 + 3.0
T_RUMBLE = word_time(L_EXPLAIN1B, "rumble") or T_B0 + 5.5
T_B_END = LINES[L_EXPLAIN1B]["end"]

T_C0 = LINES[L_EXPLAIN2]["start"]
T_EMPTY = word_time(L_EXPLAIN2, "empty") or T_C0 + 1.2
T_SENSORS = word_time(L_EXPLAIN2, "sensors") or T_C0 + 2.8
T_CWAVE = word_time(L_EXPLAIN2, "cleaning") or T_C0 + 4.6
T_MIGR = word_time(L_EXPLAIN2, "migrating") or T_C0 + 5.4
T_C_END = LINES[L_EXPLAIN2]["end"]

T_D0 = LINES[L_EXPLAIN2B]["start"]
T_SWEEPS = word_time(L_EXPLAIN2B, "sweeps") or T_D0 + 0.8
T_MUFFLE = word_time(L_EXPLAIN2B, "muffle") or T_D0 + 6.0
T_LOUD = word_time(L_EXPLAIN2B, "LOUD") or T_D0 + 8.0
T_D_END = LINES[L_EXPLAIN2B]["end"]

def pulse(t, a, attack=0.3, hold=0.35, decay=0.7):
    if t < a:
        return 0.0
    u = t - a
    if u < attack:
        return u / attack
    if u < attack + hold:
        return 1.0
    return max(0.0, 1.0 - (u - attack - hold) / decay)

def rig_params(t):
    # ambient peristalsis runs through all rig beats
    squeeze_p = staging.smooth((t - T_EX0) / 1.2)
    rumble_p = 0.35 * squeeze_p
    rumble_p = max(rumble_p, pulse(t, T_RUMBLE - 0.3, 0.4, 1.6, 1.2))
    empty_p = staging.smooth((t - T_EMPTY) / 0.9) * (1 - staging.smooth((t - T_D_END) / 0.6))
    sensor_p = pulse(t, T_SENSORS - 0.1, 0.25, 0.7, 0.8)
    # cleaning wave: starts at "cleaning wave", sweeps the whole tube into explain2b
    w0 = T_CWAVE - 0.1
    w1 = T_SWEEPS + 3.4
    wave_p = 0.0
    if t >= w0:
        wave_p = min(1.05, max(0.02, (t - w0) / max(0.5, w1 - w0)))
    crumbs_p = staging.smooth((t - T_FOOD) / 0.7)
    if t >= w1:
        crumbs_p = max(0.0, 1.0 - (t - w1) / 0.8)   # leftovers cleared
    if T_C0 <= t < w0 + 0.4:
        crumbs_p = min(crumbs_p, 0.35)              # mostly empty by then
    loud_p = pulse(t, T_LOUD - 0.2, 0.2, 0.5, 1.1)
    fed_p = 0.0
    return squeeze_p, rumble_p, empty_p, sensor_p, wave_p, crumbs_p, loud_p, fed_p

LABELS_A = [
    (staging.LeaderLabel("one long muscular tube", (300, 700), "left"), T_TUBE - 0.2),
    (staging.LeaderLabel("the walls SQUEEZE in waves", (790, 980), "right"), T_SQUEEZES - 0.2),
]
LABELS_B = [
    (staging.LeaderLabel("food, juice, swallowed air", (280, 240), "left"), T_FOOD + 0.2),
    (staging.LeaderLabel("every squeeze pushes it along", (790, 1240), "right"), T_PUSH - 0.2),
    (staging.LeaderLabel("the pushing makes the RUMBLE", (290, 1560), "left"), T_RUMBLE - 0.3),
]
LABELS_C = [
    (staging.LeaderLabel("empty for about two hours", (270, 215), "left"), T_EMPTY - 0.2),
    (staging.LeaderLabel("wall sensors fire!", (815, 395), "right"), T_SENSORS - 0.2),
    (staging.LeaderLabel("the CLEANING WAVE", (280, 1560), "left"), T_CWAVE - 0.2),
    (staging.LeaderLabel("= migrating motor complex", (790, 1640), "right"), T_MIGR - 0.1),
]
LABELS_D = [
    (staging.LeaderLabel("sweeps the leftovers down", (790, 240), "right"), T_SWEEPS - 0.2),
    (staging.LeaderLabel("an empty tube can't muffle it", (270, 1560), "left"), T_MUFFLE - 0.2),
    (staging.LeaderLabel("so you hear it LOUD!", (790, 700), "right"), T_LOUD - 0.3),
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
        d.text((cx, y), kind, font=staging.font(staging.QB, max(8, int(104 * pop))),
               fill=col, anchor="mm", stroke_width=5, stroke_fill=(16, 27, 51))
    elif kind == "stars":
        for k in range(3):
            chars._star(d, cx + (k - 1) * 120, y + (k % 2) * -30,
                        (16 + 6 * math.sin(t * 4 + k)) * pop, (255, 226, 120))
    elif kind == "grrr":
        for k in range(3):
            cyc = (line_t * 0.5 + k / 3) % 1.0
            a = int(255 * (1 - cyc) * pop)
            d.text((cx + (k % 2) * 60 - 30, y - k * 12 - 40 * cyc), "GRRRK!",
                   font=staging.font(staging.QB, max(8, int(52 * pop))),
                   fill=(255, 226, 120, a), anchor="mm",
                   stroke_width=4, stroke_fill=(16, 27, 51, a))
    elif kind == "broom":
        s = pop
        bx, by = cx + 150, y - 30
        d.line([(bx - 50 * s, by - 90 * s), (bx + 10 * s, by + 10 * s)],
               fill=(190, 140, 80), width=int(12 * s))
        d.polygon([(bx + 10 * s, by + 10 * s), (bx + 70 * s, by - 30 * s),
                   (bx + 95 * s, by - 5 * s), (bx + 30 * s, by + 45 * s)],
                  fill=(240, 200, 90), outline=(190, 150, 60), width=4)
        for k in range(4):
            d.line([(bx + (30 + k * 14) * s, by + (28 - k * 12) * s),
                    (bx + (44 + k * 14) * s, by + (40 - k * 12) * s)],
                   fill=(190, 150, 60), width=3)
    elif kind == "snack":
        s = pop
        kx, ky = cx + 150, y - 40
        d.ellipse([kx - 58 * s, ky - 58 * s, kx + 58 * s, ky + 58 * s],
                  fill=(214, 158, 84), outline=(160, 110, 50), width=5)
        for dx, dy in ((-22, -14), (14, -26), (24, 10), (-8, 22), (-30, 12)):
            d.ellipse([kx + (dx - 8) * s, ky + (dy - 8) * s,
                       kx + (dx + 8) * s, ky + (dy + 8) * s], fill=(90, 55, 30))
    elif kind == "clock":
        s = pop
        kx, ky = cx + 150, y - 40
        d.ellipse([kx - 52 * s, ky - 52 * s, kx + 52 * s, ky + 52 * s],
                  fill=(240, 244, 250), outline=(120, 140, 180), width=6)
        ang = -math.pi / 2 + line_t * 1.5
        d.line([(kx, ky), (kx + 34 * s * math.cos(ang), ky + 34 * s * math.sin(ang))],
               fill=(60, 80, 120), width=6)
        d.line([(kx, ky), (kx, ky - 26 * s)], fill=(60, 80, 120), width=5)

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
    squeeze_p, rumble_p, empty_p, sensor_p, wave_p, crumbs_p, loud_p, fed_p = rig_params(t)
    beat_t = min(1.0, max(0.0, (t - T_EX0) / (T_D_END - T_EX0)))
    scale = staging.push_in(beat_t, 0.08)
    img = BG_RIG.copy()
    RIG.draw(img, squeeze_p=squeeze_p, rumble_p=rumble_p, empty_p=empty_p,
             sensor_p=sensor_p, wave_p=wave_p, crumbs_p=crumbs_p,
             loud_p=loud_p, fed_p=fed_p, t=t)
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
        draw_prop(frame, "grrr", "PIP", t, t - ln["start"])
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
    if beat == "ask2":
        ln = LINES[L_ASK2]
        draw_two_shot(frame, "PIP", ln, t, "confused")
        draw_prop(frame, "?", "PIP", t, t - ln["start"])
        draw_caption(frame, L_ASK2, t)
        return frame
    if beat == "gag":
        ln = LINES[L_GAG]
        draw_two_shot(frame, "PIP", ln, t, "amazed", action=("double_take", 2.8))
        draw_prop(frame, "!?", "PIP", t, t - ln["start"])
        draw_caption(frame, L_GAG, t)
        return frame
    if beat == "ask3":
        ln = LINES[L_ASK3]
        draw_two_shot(frame, "PIP", ln, t, "amazed", action=("head_bob", 2.4))
        draw_prop(frame, "?", "PIP", t, t - ln["start"])
        draw_prop(frame, "broom", "PIP", t, t - ln["start"])
        draw_caption(frame, L_ASK3, t)
        return frame
    if beat == "gag2":
        ln = LINES[L_GAG2]
        draw_two_shot(frame, "PIP", ln, t, "amazed")
        draw_prop(frame, "grrr", "PIP", t, t - ln["start"])
        draw_caption(frame, L_GAG2, t)
        return frame
    if beat == "watch":
        ln = LINES[L_WATCH]
        line_t = t - ln["start"]
        gp = min(1.0, max(0.0, line_t / 0.55))
        draw_two_shot(frame, "RAY", ln, t, "smart", glasses_ray=True, ray_gp=gp,
                      action=("nod", 1.4))
        draw_prop(frame, "clock", "RAY", t, max(0.0, line_t - 2.2))
        draw_caption(frame, L_WATCH, t)
        return frame
    if beat == "gag3":
        ln = LINES[L_GAG3]
        t_snack = word_time(L_GAG3, "SNACK") or ln["end"] - 2.0
        expr = "amazed" if t < t_snack else "delighted"
        draw_two_shot(frame, "PIP", ln, t, expr, glasses_ray=True, action=("double_take", 2.8))
        draw_prop(frame, "!?", "PIP", t, t - ln["start"])
        draw_prop(frame, "snack", "PIP", t, max(0.0, t - t_snack + 0.3))
        draw_caption(frame, L_GAG3, t)
        return frame
    if beat == "finale":
        ln = LINES[L_FINALE]
        draw_two_shot(frame, "RAY", ln, t, "proud", glasses_ray=True, action=("nod", 1.6))
        draw_prop(frame, "snack", "RAY", t, t - ln["start"])
        draw_caption(frame, L_FINALE, t)
        return frame
    # react
    ln = LINES[L_REACT]
    line_t = t - ln["start"]
    expr = "amazed" if line_t < 0.9 else "delighted"
    draw_two_shot(frame, "PIP", ln, t, expr, glasses_ray=True)
    draw_prop(frame, "stars", "PIP", t, line_t)
    draw_caption(frame, L_REACT, t)
    return frame

# ---------------------------------------------------------------- main loop
RIG_PREV = {"explain": "ask", "explain1b": "ask2", "explain2": "gag", "explain2b": "ask3"}
AFTER_RIG = {"ask2": T_EX_END, "gag": T_B_END, "ask3": T_C_END, "gag2": T_D_END}
DLG_PREV = {"hook": "zap", "ask": "hook", "watch": "gag2", "gag3": "watch",
            "finale": "gag3", "react": "finale"}

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
    for fr in range(start_frame, frames_total):
        t = fr / FPS
        ln = line_at(t)
        beat = ln["beat"]
        frame = beat_frame(beat, t)
        dt = t - ln["start"]
        if beat in RIG_PREV and 0 <= dt < 0.35:
            prev = dialogue_frame(RIG_PREV[beat], ln["start"] - 0.001)
            frame = Image.blend(prev, frame, staging.smooth(dt / 0.35))
        elif beat in AFTER_RIG and 0 <= dt < 0.25:
            prev = rig_frame(AFTER_RIG[beat] - 0.01)
            frame = Image.blend(prev, frame, staging.smooth(dt / 0.25))
        elif beat in DLG_PREV and 0 <= dt < 0.25:
            prev = dialogue_frame(DLG_PREV[beat], ln["start"] - 0.001)
            frame = Image.blend(prev, frame, dt / 0.25)
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
