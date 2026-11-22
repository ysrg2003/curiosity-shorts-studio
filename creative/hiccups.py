import json, math, os, subprocess
from PIL import Image, ImageDraw
import chars, staging
from explain import HiccupRig
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

RIG = HiccupRig()

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
T_MUSCLE = word_time(L_EXPLAIN, "muscle") or T_EX0 + 1.2
T_SQUEEZES = word_time(L_EXPLAIN, "squeezes") or T_EX0 + 3.5
T_EX_END = LINES[L_EXPLAIN]["end"]

T_B0 = LINES[L_EXPLAIN1B]["start"]
T_EATING = word_time(L_EXPLAIN1B, "Eating") or T_B0 + 1.0
T_NERVES1B = word_time(L_EXPLAIN1B, "nerves") or T_B0 + 5.0
T_B_END = LINES[L_EXPLAIN1B]["end"]

T_C0 = LINES[L_EXPLAIN2]["start"]
T_VAGUS = word_time(L_EXPLAIN2, "vagus") or T_C0 + 0.8
T_PHRENIC = word_time(L_EXPLAIN2, "phrenic") or T_C0 + 1.6
T_SPASMS = word_time(L_EXPLAIN2, "spasms") or T_C0 + 5.5
T_C_END = LINES[L_EXPLAIN2]["end"]

T_D0 = LINES[L_EXPLAIN2B]["start"]
T_YANKS = word_time(L_EXPLAIN2B, "yanks") or T_D0 + 1.2
T_SLAMS = word_time(L_EXPLAIN2B, "slams") or T_D0 + 3.2
T_HICW = word_time(L_EXPLAIN2B, "hic") or T_D0 + 6.5
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
    spasm_p = pulse(t, T_SQUEEZES)
    for k in range(3):
        spasm_p = max(spasm_p, 0.9 * pulse(t, T_SPASMS + k * 1.7, 0.22, 0.3, 0.8))
    spasm_p = max(spasm_p, pulse(t, T_YANKS - 0.2, 0.25, 0.5, 1.6))
    nerve_p = max(0.0, min(1.0, (t - T_VAGUS) / max(0.4, (T_SPASMS - T_VAGUS))))
    nerve_p = max(nerve_p, 0.6 * pulse(t, T_NERVES1B, 0.4, 1.2, 1.0))
    if t > T_C_END:
        nerve_p = 0.0
    irrit_p = staging.smooth((t - T_EATING) / 0.8) * (1 - staging.smooth((t - (T_B_END - 0.4)) / 0.6))
    air_p = staging.smooth((t - (T_YANKS - 0.2)) / 0.5) * (1 - staging.smooth((t - T_SLAMS) / 0.15))
    air_p = max(air_p, 0.55 * staging.smooth((t - T_SQUEEZES) / 0.4) * (1 - staging.smooth((t - (T_SQUEEZES + 0.9)) / 0.4)))
    gate_p = staging.smooth((t - T_SLAMS) / 0.15) * (1 - staging.smooth((t - (T_HICW + 0.6)) / 0.8))
    hic_p = pulse(t, T_HICW - 0.1, 0.12, 0.25, 0.9)
    return spasm_p, nerve_p, irrit_p, air_p, gate_p, hic_p

LABELS_A = [
    (staging.LeaderLabel("your diaphragm", (820, 1470), "right"), T_MUSCLE - 0.2),
    (staging.LeaderLabel("a big breathing muscle", (250, 1230), "left"), T_MUSCLE + 0.7),
    (staging.LeaderLabel("it SQUEEZES on its own!", (280, 300), "left"), T_SQUEEZES - 0.2),
]
LABELS_B = [
    (staging.LeaderLabel("eating fast, fizz, excitement", (750, 250), "right"), T_EATING + 0.2),
    (staging.LeaderLabel("irritated nerves!", (300, 1560), "left"), T_NERVES1B - 0.2),
]
LABELS_C = [
    (staging.LeaderLabel("vagus + phrenic nerves", (225, 380), "left"), T_VAGUS - 0.2),
    (staging.LeaderLabel("the signal races down", (820, 950), "right"), T_PHRENIC + 0.4),
    (staging.LeaderLabel("the diaphragm SPASMS!", (270, 1640), "left"), T_SPASMS - 0.2),
]
LABELS_D = [
    (staging.LeaderLabel("air gets yanked in", (820, 250), "right"), T_YANKS - 0.2),
    (staging.LeaderLabel("the glottis SLAMS shut", (265, 560), "left"), T_SLAMS - 0.2),
    (staging.LeaderLabel("that slam is the HIC!", (790, 700), "right"), T_HICW - 0.3),
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
    elif kind == "hic":
        for k in range(3):
            cyc = (line_t * 0.5 + k / 3) % 1.0
            a = int(255 * (1 - cyc) * pop)
            d.text((cx + (k % 2) * 60 - 30, y - k * 12 - 40 * cyc), "HIC!",
                   font=staging.font(staging.QB, max(8, int(58 * pop))),
                   fill=(255, 226, 120, a), anchor="mm",
                   stroke_width=4, stroke_fill=(16, 27, 51, a))
    elif kind == "fish":
        s = pop
        fx, fy = cx + 150, y - 40
        col = (120, 190, 235)
        d.ellipse([fx - 70 * s, fy - 30 * s, fx + 50 * s, fy + 30 * s],
                  fill=col, outline=(70, 120, 170), width=5)
        d.polygon([(fx + 50 * s, fy), (fx + 95 * s, fy - 28 * s), (fx + 95 * s, fy + 28 * s)],
                  fill=col, outline=(70, 120, 170))
        d.ellipse([fx - 45 * s, fy - 8 * s, fx - 30 * s, fy + 6 * s], fill=(20, 24, 44))
    elif kind == "glass":
        s = pop
        gx, gy = cx - 170, y - 20
        d.polygon([(gx - 36 * s, gy - 44 * s), (gx + 36 * s, gy - 44 * s),
                   (gx + 26 * s, gy + 40 * s), (gx - 26 * s, gy + 40 * s)],
                  outline=(190, 220, 250), width=6)
        d.polygon([(gx - 29 * s, gy - 10 * s), (gx + 29 * s, gy - 10 * s),
                   (gx + 26 * s, gy + 36 * s), (gx - 26 * s, gy + 36 * s)],
                  fill=(120, 190, 240, 200))

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
    spasm_p, nerve_p, irrit_p, air_p, gate_p, hic_p = rig_params(t)
    beat_t = min(1.0, max(0.0, (t - T_EX0) / (T_D_END - T_EX0)))
    scale = staging.push_in(beat_t, 0.08)
    img = BG_RIG.copy()
    RIG.draw(img, spasm_p=spasm_p, nerve_p=nerve_p, irrit_p=irrit_p,
             air_p=air_p, gate_p=gate_p, hic_p=hic_p, t=t)
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
        draw_prop(frame, "hic", "PIP", t, t - ln["start"])
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
        draw_two_shot(frame, "PIP", ln, t, "confused", action=("head_bob", 2.4))
        draw_prop(frame, "?", "PIP", t, t - ln["start"])
        draw_caption(frame, L_ASK3, t)
        return frame
    if beat == "gag2":
        ln = LINES[L_GAG2]
        draw_two_shot(frame, "PIP", ln, t, "amazed")
        draw_prop(frame, "hic", "PIP", t, t - ln["start"])
        draw_caption(frame, L_GAG2, t)
        return frame
    if beat == "watch":
        ln = LINES[L_WATCH]
        line_t = t - ln["start"]
        gp = min(1.0, max(0.0, line_t / 0.55))
        draw_two_shot(frame, "RAY", ln, t, "smart", glasses_ray=True, ray_gp=gp,
                      action=("nod", 1.4))
        draw_prop(frame, "fish", "RAY", t, max(0.0, line_t - 5.2))
        draw_caption(frame, L_WATCH, t)
        return frame
    if beat == "gag3":
        ln = LINES[L_GAG3]
        t_fish = word_time(L_GAG3, "FISH") or ln["end"] - 2.0
        expr = "amazed" if t < t_fish else "delighted"
        draw_two_shot(frame, "PIP", ln, t, expr, glasses_ray=True, action=("double_take", 2.8))
        draw_prop(frame, "!?", "PIP", t, t - ln["start"])
        draw_prop(frame, "fish", "PIP", t, t - ln["start"])
        draw_caption(frame, L_GAG3, t)
        return frame
    if beat == "finale":
        ln = LINES[L_FINALE]
        draw_two_shot(frame, "RAY", ln, t, "proud", glasses_ray=True, action=("nod", 1.6))
        draw_prop(frame, "glass", "RAY", t, t - ln["start"])
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
