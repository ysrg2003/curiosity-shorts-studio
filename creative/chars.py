import math
from PIL import Image, ImageDraw

INK = (16, 27, 51)
AMBER = (245, 184, 65)
SKIN_PIP = (247, 242, 231)
SKIN_RAY = (233, 216, 186)
HAIR = (52, 63, 88)
GLASS = (38, 42, 54)
MOUTH_IN = (122, 46, 46)
TONGUE = (196, 96, 90)

# ---------------------------------------------------------------- face params
DEFAULT_FACE = dict(
    brow_h=0.0,        # -1 lowered .. +1 raised
    brow_tilt=0.0,     # >0 inner end down (serious/angry), <0 inner end up (sad/worried)
    brow_h_l=None, brow_tilt_l=None, brow_h_r=None, brow_tilt_r=None,
    eye_open=1.0,      # 0 closed .. 1 open
    eye_open_l=None, eye_open_r=None,
    eye_scale=1.0, pupil=1.0, lid=0.0,   # lid: 0 none .. 0.6 heavy upper lid
    look_x=0.0, look_y=0.0,              # -1..1
    eye_closed_style="line",             # 'line' | 'happy' (^^ arcs)
    mouth="small",     # small|smile|grin|frown|flat|open|o|open_big|smirk|wavy
    m_curve=0.35, m_w=1.0, m_open=0.0,
    blush=0.0, sweat=False, spark=False,
    tears=0.0,         # 0 none .. 1 full tear streaks + drops
)

def face(**kw):
    f = dict(DEFAULT_FACE); f.update(kw); return f

def lerp_face(a, b, p):
    """Numeric params interpolate; discrete ones switch at halfway."""
    out = {}
    keys = set(a) | set(b)
    for k in keys:
        va, vb = a.get(k), b.get(k)
        if isinstance(va, (int, float)) and isinstance(vb, (int, float)) and not isinstance(va, bool):
            if va is None or vb is None:
                out[k] = vb if p >= 0.5 else va
            else:
                out[k] = va + (vb - va) * p
        elif va is None and isinstance(vb, (int, float)):
            base = DEFAULT_FACE.get(_root_key(k), 0.0)
            out[k] = base + (vb - base) * p
        elif vb is None and isinstance(va, (int, float)):
            base = DEFAULT_FACE.get(_root_key(k), 0.0)
            out[k] = va + (base - va) * p
        else:
            out[k] = vb if p >= 0.5 else va
    return out

def _root_key(k):
    for suf in ("_l", "_r"):
        if k.endswith(suf):
            return k[:-2]
    return k

# ------------------------------------------------------- expression library
# Grounded in Ekman's basics (joy, surprise, fear, sadness, anger, disgust) and
# Plutchik's wheel (anticipation, trust + dyads), plus dialogue-acting states.
PRESETS = {
    # --- neutral / baseline
    "neutral":      face(mouth="small", m_curve=0.25),
    "listening":    face(brow_h=0.15, eye_scale=1.06, mouth="small", m_curve=0.45),
    "talking":      face(mouth="open", m_open=0.4),
    # --- joy family (Ekman: enjoyment; Plutchik: joy, joy+anticipation)
    "happy":        face(mouth="smile", m_curve=0.7, m_w=1.05),
    "delighted":    face(eye_scale=1.12, spark=True, mouth="grin", m_open=0.35),
    "laugh":        face(eye_open=0.0, eye_closed_style="happy", mouth="grin", m_open=0.5),
    "giggling":     face(eye_open=0.0, eye_closed_style="happy", mouth="grin", m_open=0.25, blush=0.6),
    "excited":      face(brow_h=0.5, eye_scale=1.1, mouth="smile", m_curve=0.9, m_w=1.15),
    "proud":        face(brow_h=0.2, lid=0.18, mouth="smile", m_curve=0.6, look_y=-0.2),
    "relieved":     face(eye_open=0.0, eye_closed_style="happy", mouth="smile", m_curve=0.5),
    "smug":         face(lid=0.35, brow_h=0.15, mouth="smirk"),
    "mischievous":  face(brow_h_r=0.45, lid=0.1, mouth="smirk", look_x=0.4),
    # --- trust / affection family (Plutchik: trust; dyads love, optimism)
    "trusting":     face(brow_tilt=-0.15, eye_scale=1.04, mouth="smile", m_curve=0.55),
    "hopeful":      face(brow_tilt=-0.25, brow_h=0.2, look_y=-0.4, spark=True, mouth="smile", m_curve=0.5),
    "shy":          face(look_x=0.5, look_y=0.35, eye_open=0.9, blush=1.0, mouth="smile", m_curve=0.4, m_w=0.8),
    "dreamy":       face(lid=0.35, look_y=-0.45, spark=True, mouth="smile", m_curve=0.45),
    # --- surprise family (Ekman: surprise; Plutchik: surprise, amazement)
    "curious":      face(brow_h_l=0.45, brow_h_r=0.1, eye_scale=1.06, mouth="small", m_curve=0.2),
    "amazed":       face(brow_h=0.6, eye_scale=1.16, pupil=1.1, mouth="o"),
    "shocked":      face(brow_h=0.85, eye_scale=1.22, pupil=1.15, mouth="o", m_open=0.35),
    "gasp":         face(brow_h=0.9, eye_scale=1.2, pupil=1.05, mouth="o", m_open=0.15),
    # --- anticipation / thinking (Plutchik: anticipation)
    "thinking":     face(brow_h_l=-0.25, lid=0.22, look_x=0.5, look_y=-0.4, mouth="flat"),
    "smart":        face(lid=0.28, brow_tilt=0.3, mouth="smirk"),   # Ray's signature (+glasses)
    "determined":   face(brow_tilt=0.55, brow_h=-0.15, eye_open=0.92, mouth="flat", m_w=0.9),
    "pondering":    face(brow_h_l=0.35, lid=0.15, look_x=-0.3, look_y=-0.55, mouth="flat", m_w=0.7),
    # --- skepticism / disgust family (Ekman: disgust, contempt)
    "skeptical":    face(brow_h_l=0.5, lid=0.3, mouth="flat", m_w=0.85, look_x=0.25),
    "suspicious":   face(lid=0.45, brow_tilt=0.4, look_x=0.5, eye_open_r=0.68, mouth="flat", m_w=0.8),
    "unimpressed":  face(lid=0.55, brow_h=-0.2, look_y=0.4, eye_scale=0.95, mouth="flat", m_w=0.95),
    "confused":     face(brow_h_l=0.3, brow_tilt_r=0.35, mouth="wavy", look_x=0.3),
    "disgusted":    face(brow_tilt=0.5, brow_h=-0.1, lid=0.3, eye_open=0.85, look_x=-0.4, mouth="frown", m_curve=-0.45, m_w=0.75),
    # --- fear family (Ekman: fear)
    "nervous":      face(brow_tilt=-0.3, eye_open=1.05, sweat=True, mouth="wavy"),
    "worried":      face(brow_tilt=-0.55, brow_h=0.15, mouth="frown", m_curve=-0.3),
    "scared":       face(brow_tilt=-0.5, brow_h=0.6, eye_scale=1.2, pupil=0.8, mouth="open", m_open=0.3),
    "terrified":    face(brow_tilt=-0.45, brow_h=0.8, eye_scale=1.28, pupil=0.7, sweat=True, mouth="open_big", m_open=0.3),
    "guilty":       face(brow_tilt=-0.35, look_x=-0.45, look_y=0.4, sweat=True, mouth="wavy", m_w=0.75),
    # --- sadness family (Ekman: sadness)
    "disappointed": face(brow_tilt=-0.35, brow_h=0.1, eye_open=0.9, look_y=0.4, mouth="frown", m_curve=-0.3),
    "sad":          face(brow_tilt=-0.6, eye_open=0.8, lid=0.15, look_y=0.3, mouth="frown", m_curve=-0.6),
    "embarrassed":  face(blush=1.0, eye_open=0.85, look_y=0.3, mouth="wavy"),
    "teary":        face(brow_tilt=-0.4, brow_h=0.15, pupil=1.12, tears=0.3, mouth="wavy", m_w=0.8),
    "crying":       face(eye_open=0.0, brow_tilt=-0.55, brow_h=0.35, tears=1.0, mouth="open_big", m_open=0.15),
    # --- anger family (Ekman: anger) - kept child-safe, mild
    "annoyed":      face(brow_tilt=0.75, brow_h=-0.25, lid=0.2, mouth="frown", m_curve=-0.25, m_w=0.85),
    "angry":        face(brow_tilt=0.9, brow_h=-0.3, eye_open=0.85, mouth="frown", m_curve=-0.5),
    # --- low energy
    "bored":        face(lid=0.5, eye_open=0.8, brow_h=0.05, look_y=0.45, mouth="flat", m_w=0.9),
    "sleepy":       face(lid=0.75, eye_open=0.5, brow_h=-0.05, look_y=0.35, mouth="flat", m_w=0.6),
    "yawning":      face(eye_open=0.0, brow_h=0.1, mouth="open_big", m_open=0.55),
    "exhausted":    face(lid=0.85, eye_open=0.42, brow_h=-0.1, look_y=0.45, sweat=True, mouth="flat", m_w=0.55),
    # --- playful extras
    "wink":         face(eye_open_r=0.04, mouth="smirk", brow_h_l=0.2),
    "dizzy":        face(eye_open=0.9, mouth="wavy"),
}
EXPRESSIONS = sorted(PRESETS.keys())

def preset(name, who=None):
    f = dict(PRESETS[name])
    if who == "PIP":
        f["blush"] = max(f.get("blush", 0.0), 0.45)
    return f

# ------------------------------------------------------------------- drawing
def _geom(who, r, cy):
    if who == "PIP":
        return dict(ex=0.36 * r, ey=cy - 0.14 * r, ew=0.34 * r, eh=0.44 * r, pr=0.15 * r)
    return dict(ex=0.38 * r, ey=cy - 0.16 * r, ew=0.24 * r, eh=0.21 * r, pr=0.095 * r)

def _star(d, x, y, s, fill):
    pts = []
    for i in range(10):
        rr = s if i % 2 == 0 else s * 0.45
        a = -math.pi / 2 + i * math.pi / 5
        pts.append((x + rr * math.cos(a), y + rr * math.sin(a)))
    d.polygon(pts, fill=fill)

def render_head(who, r, f=None, glasses=False, glasses_p=1.0, glasses_dy=0.0, blink=False, turn=0.0):
    """Render one character head to a transparent RGBA tile. f: face dict.
    turn: -1 (facing left) .. +1 (facing right), 0 = front. Shifts the whole
    feature cluster, narrows the far eye, and biases the pupils: a flat-style
    three-quarter turn for two-shots where characters face each other."""
    f = dict(DEFAULT_FACE) if f is None else dict(DEFAULT_FACE, **f)
    pad = int(r * 0.5)
    s = 2 * (r + pad)
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img, "RGBA")
    cx, cy = s / 2, s / 2 + (r * 0.08 if who == "PIP" else 0)
    skin = SKIN_PIP if who == "PIP" else SKIN_RAY
    ow = max(6, r // 16)

    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=skin)
    if who == "RAY":
        d.chord([cx - r, cy - r, cx + r, cy + r], 180, 360, fill=HAIR)
        d.ellipse([cx - r * 0.72, cy - r * 0.60, cx + r * 0.18, cy + r * 0.60], fill=skin)
        d.ellipse([cx - r * 0.28, cy - r * 0.52, cx + r * 0.62, cy + r * 0.70], fill=skin)
        d.ellipse([cx + r * 0.22, cy - r * 0.64, cx + r * 0.92, cy + r * 0.50], fill=skin)
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=INK, width=ow)
    if who == "PIP":
        cfx = turn * 0.10 * r
        d.arc([cx - r * 0.20 + cfx, cy - r * 1.28, cx + r * 0.20 + cfx, cy - r * 0.88], 195, 350, fill=INK, width=max(9, r // 13))
        d.arc([cx - r * 0.10 + cfx, cy - r * 1.18, cx + r * 0.14 + cfx, cy - r * 0.98], 300, 480, fill=INK, width=max(9, r // 13))

    t_ = max(-1.0, min(1.0, turn))
    ta = abs(t_)
    fx = t_ * 0.12 * r                      # feature-cluster shift
    tsign = 1 if t_ >= 0 else -1

    g = _geom(who, r, cy)
    ex, ey, ew0, eh0, pr0 = g["ex"], g["ey"], g["ew"], g["eh"], g["pr"]
    ew = ew0 * f["eye_scale"]
    pr = pr0 * f["pupil"]
    open_l = f["eye_open_l"] if f["eye_open_l"] is not None else f["eye_open"]
    open_r = f["eye_open_r"] if f["eye_open_r"] is not None else f["eye_open"]

    for sgn, eopen in ((-1, open_l), (1, open_r)):
        far = t_ != 0 and sgn != tsign
        ews = ew * ((1 - 0.20 * ta) if far else (1 + 0.05 * ta))
        x = cx + sgn * ex * ((1 - 0.15 * ta) if far else 1.0) + fx
        eh = eh0 * f["eye_scale"] * max(eopen, 0.02)
        closed = eopen < 0.08
        if blink or closed:
            if f["eye_closed_style"] == "happy" and not blink:
                d.arc([x - ews / 2, ey - eh0 * 0.3, x + ews / 2, ey + eh0 * 0.4], 200, 340, fill=INK, width=8)
            else:
                d.arc([x - ews / 2, ey + eh0 * 0.2 - 6, x + ews / 2, ey + eh0 * 0.2 + 8], 180, 360, fill=INK, width=7)
        else:
            d.ellipse([x - ews / 2, ey - eh / 2, x + ews / 2, ey + eh / 2], fill=(255, 255, 255), outline=INK, width=5)
            px = x + max(-1.0, min(1.0, f["look_x"] + t_ * 0.85)) * ews * 0.26
            py = ey + f["look_y"] * eh * 0.30 + 2
            d.ellipse([px - pr, py - pr, px + pr, py + pr], fill=INK)
            hl = pr * 0.45
            d.ellipse([px - hl, py - pr * 0.6, px + hl * 0.2, py - pr * 0.6 + hl * 1.2], fill=(255, 255, 255))
            if f["spark"]:
                _star(d, px + pr * 0.9, py - pr * 0.9, pr * 0.5, (255, 226, 120))
            if f["lid"] > 0.02:
                cov = eh * min(f["lid"], 0.8)
                cap = [x - ews / 2, ey - eh / 2 - cov, x + ews / 2, ey + eh / 2 - cov]
                d.ellipse(cap, fill=skin)
                d.arc(cap, 20, 160, fill=INK, width=5)
                d.ellipse([px - pr * 0.95, py - pr * 0.5, px + pr * 0.95, py + pr], fill=INK)
                d.ellipse([px - hl * 0.8, py - pr * 0.3, px - hl * 0.1, py + pr * 0.1], fill=(255, 255, 255))

    # eyebrows
    gap = r * (0.14 if who == "PIP" else 0.11)
    wdt = max(5, r // 24) if who == "PIP" else max(8, r // 14)
    for sgn in (-1, 1):
        far = t_ != 0 and sgn != tsign
        ewb = ew * ((1 - 0.20 * ta) if far else (1 + 0.05 * ta))
        x = cx + sgn * ex * ((1 - 0.15 * ta) if far else 1.0) + fx
        side = "l" if sgn == -1 else "r"
        bh = f[f"brow_h_{side}"] if f[f"brow_h_{side}"] is not None else f["brow_h"]
        bt = f[f"brow_tilt_{side}"] if f[f"brow_tilt_{side}"] is not None else f["brow_tilt"]
        eh = eh0 * f["eye_scale"] * max(open_l if sgn == -1 else open_r, 0.02)
        yb = ey - eh / 2 - gap - bh * r * 0.10
        inner_dy = -bt * r * 0.055 * -sgn  # tilt>0: inner end goes down
        x0, x1 = x - ewb * 0.75, x + ewb * 0.75
        y0 = yb + (inner_dy if sgn == 1 else 0) - (inner_dy if sgn == -1 else 0)
        y1 = yb + (inner_dy if sgn == -1 else 0) - (inner_dy if sgn == 1 else 0)
        # slight curve via midpoint
        mx, my = (x0 + x1) / 2, min(y0, y1) - r * 0.02
        pts = []
        for i in range(9):
            tt = i / 8
            bx = (1 - tt) ** 2 * x0 + 2 * (1 - tt) * tt * mx + tt ** 2 * x1
            by2 = (1 - tt) ** 2 * y0 + 2 * (1 - tt) * tt * my + tt ** 2 * y1
            pts.append((bx, by2))
        d.line(pts, fill=INK, width=wdt, joint="curve")

    # mouth
    cx = cx + fx
    my = cy + (0.36 if who == "PIP" else 0.34) * r
    mk, mw, mc, mo = f["mouth"], f["m_w"] * (1 - 0.08 * ta), f["m_curve"], f["m_open"]
    if mk == "small":
        d.arc([cx - r * 0.20 * mw, my - r * 0.10, cx + r * 0.20 * mw, my + r * 0.10 + r * 0.06 * mc], 25, 155, fill=INK, width=7)
    elif mk == "smile":
        d.arc([cx - r * 0.30 * mw, my - r * 0.16, cx + r * 0.30 * mw, my + r * (0.05 + 0.15 * mc)], 15, 165, fill=INK, width=8)
    elif mk == "grin":
        h = r * (0.16 + 0.30 * mo)
        d.pieslice([cx - r * 0.32 * mw, my - h * 0.4, cx + r * 0.32 * mw, my + h], 0, 180, fill=MOUTH_IN, outline=INK, width=5)
        if who == "PIP":
            d.rectangle([cx - r * 0.07, my - h * 0.4 + 3, cx + r * 0.07, my + h * 0.15], fill=(255, 255, 255), outline=INK, width=3)
        else:
            d.rectangle([cx - r * 0.22 * mw, my - h * 0.4 + 3, cx + r * 0.22 * mw, my + h * 0.02], fill=(255, 255, 255), outline=INK, width=3)
    elif mk == "frown":
        d.arc([cx - r * 0.24 * mw, my + r * 0.02, cx + r * 0.24 * mw, my + r * 0.02 + r * 0.22 * abs(mc)], 200, 340, fill=INK, width=8)
    elif mk == "flat":
        d.line([(cx - r * 0.22 * mw, my + r * 0.05), (cx + r * 0.22 * mw, my + r * 0.05)], fill=INK, width=8)
    elif mk == "open":
        hh = r * (0.10 + 0.14 * mo)
        d.ellipse([cx - r * 0.16, my - hh / 2, cx + r * 0.16, my + hh / 2], fill=MOUTH_IN, outline=INK, width=5)
        d.ellipse([cx - r * 0.16 + 6, my + hh / 2 - hh * 0.4, cx + r * 0.16 - 6, my + hh / 2 - 4], fill=TONGUE)
    elif mk == "o":
        rr2 = r * (0.10 + 0.08 * mo)
        d.ellipse([cx - rr2, my - rr2, cx + rr2, my + rr2], fill=MOUTH_IN, outline=INK, width=5)
        d.ellipse([cx - rr2 * 0.5, my + rr2 * 0.15, cx + rr2 * 0.5, my + rr2 * 0.75], fill=TONGUE)
    elif mk == "open_big":
        hh = r * (0.26 + 0.30 * mo)
        ww = r * 0.20
        d.ellipse([cx - ww, my - hh * 0.5, cx + ww, my + hh * 0.5], fill=MOUTH_IN, outline=INK, width=6)
        d.ellipse([cx - ww * 0.55, my + hh * 0.02, cx + ww * 0.55, my + hh * 0.40], fill=TONGUE)
    elif mk == "smirk":
        if t_ < -0.3:  # mirror the crooked corner toward the facing direction
            d.arc([cx - r * 0.26, my - r * 0.10, cx + r * 0.22, my + r * 0.12], 30, 160, fill=INK, width=8)
            d.arc([cx - r * 0.26, my - r * 0.10, cx - r * 0.16, my + r * 0.02], 120, 270, fill=INK, width=6)
        else:
            d.arc([cx - r * 0.22, my - r * 0.10, cx + r * 0.26, my + r * 0.12], 20, 150, fill=INK, width=8)
            d.arc([cx + r * 0.16, my - r * 0.10, cx + r * 0.26, my + r * 0.02], 270, 60, fill=INK, width=6)
    elif mk == "wavy":
        pts = []
        w2 = r * 0.22 * mw
        for i in range(17):
            tt = i / 16
            pts.append((cx - w2 + 2 * w2 * tt, my + r * 0.04 + math.sin(tt * math.pi * 3) * r * 0.035))
        d.line(pts, fill=INK, width=7, joint="curve")

    # blush: pre-blend over skin at FULL alpha (semi-alpha pixels in the tile
    # would composite against the background, not the face)
    if f["blush"] > 0.02:
        w = min((40 + 100 * min(f["blush"], 1)) / 255.0, 0.6)
        bc = tuple(int(255 * w * c1 / 255 * 255 + 0) if False else int((255, 150, 120)[i] * w + skin[i] * (1 - w)) for i in range(3))
        d.ellipse([cx - r * 0.72 + fx * 0.5, cy + r * 0.16, cx - r * 0.40 + fx * 0.5, cy + r * 0.36], fill=bc)
        d.ellipse([cx + r * 0.40 + fx * 0.5, cy + r * 0.16, cx + r * 0.72 + fx * 0.5, cy + r * 0.36], fill=bc)

    # sweat drop
    if f["sweat"]:
        sx, sy2, ss = cx + r * 0.75, cy - r * 0.45, r * 0.11
        d.polygon([(sx, sy2 - ss), (sx + ss * 0.7, sy2 + ss * 0.4), (sx - ss * 0.7, sy2 + ss * 0.4)], fill=(140, 200, 240))
        d.ellipse([sx - ss * 0.7, sy2 - ss * 0.1, sx + ss * 0.7, sy2 + ss * 1.1], fill=(140, 200, 240))

    # tears: full-alpha blue streaks + drops below the eyes (pre-blend safe)
    if f["tears"] > 0.02:
        tc = (120, 190, 235)
        for sgn in (-1, 1):
            x = cx + sgn * ex
            ty = ey + eh0 * 0.4
            tl = r * 0.28 * min(f["tears"], 1)
            d.rounded_rectangle([x - r * 0.045, ty, x + r * 0.045, ty + tl], radius=r * 0.045, fill=tc)
            d.ellipse([x - r * 0.085, ty + tl - r * 0.08, x + r * 0.085, ty + tl + r * 0.11], fill=tc)

    # glasses: thin rectangular charcoal frames (Ray)
    if glasses:
        gy = (1 - glasses_p) * -r * 1.2 + glasses_dy
        gh = eh0 * 1.9
        gwdt = max(4, r // 28)
        xs = {}
        for sgn in (-1, 1):
            far = t_ != 0 and sgn != tsign
            gws = ew0 * 1.75 * ((1 - 0.15 * ta) if far else (1 + 0.04 * ta))
            x = cx + sgn * ex * ((1 - 0.15 * ta) if far else 1.0) + fx
            xs[sgn] = (x, gws)
            d.rectangle([x - gws / 2, ey - gh / 2 + gy, x + gws / 2, ey + gh / 2 + gy], outline=GLASS, width=gwdt)
            d.line([(x - gws * 0.30, ey - gh * 0.18 + gy), (x - gws * 0.12, ey - gh * 0.38 + gy)],
                   fill=(230, 236, 244), width=max(2, gwdt - 2))
        (xl, gl), (xr, gr) = xs[-1], xs[1]
        d.line([(xl + gl / 2, ey - gh * 0.15 + gy), (xr - gr / 2, ey - gh * 0.15 + gy)], fill=GLASS, width=gwdt)
        d.line([(xl - gl / 2, ey - gh * 0.15 + gy), (cx - fx - r * 0.99, ey - r * 0.10 + gy)], fill=GLASS, width=gwdt)
        d.line([(xr + gr / 2, ey - gh * 0.15 + gy), (cx - fx + r * 0.99, ey - r * 0.10 + gy)], fill=GLASS, width=gwdt)
    return img

def place_head(frame, tile, cx, cy, rot=0.0, scale=1.0, squash=1.0):
    """Paste a head tile with rotation/scale/squash (motion transforms)."""
    t2 = tile
    if scale != 1.0 or squash != 1.0:
        t2 = t2.resize((max(1, int(t2.width * scale)), max(1, int(t2.height * scale * squash))), Image.LANCZOS)
    if rot:
        t2 = t2.rotate(rot, expand=True, resample=Image.BICUBIC)
    frame.paste(t2, (int(cx - t2.width / 2), int(cy - t2.height / 2)), t2)

# ------------------------------------------------------------------ actions
# Reusable animation clips. Each returns per-phase (0..1) transform dict:
#   dx, dy px offset; rot deg; scale; squash; glasses_p; face override dict.
def _idle(p):      return dict(dy=3 * math.sin(p * math.pi * 2))
def _nod(p):       return dict(rot=9 * math.sin(p * math.pi * 4))
def _shake(p):     return dict(dx=11 * math.sin(p * math.pi * 5))
def _tilt(p):      return dict(rot=13 * min(1, p * 4) * (1 if p < 0.8 else (1 - p) * 5))
def _tilt_shake(p):return dict(rot=12 + 2.5 * math.sin(p * math.pi * 8))
def _bounce(p):    return dict(dy=-16 * abs(math.sin(p * math.pi * 3)), squash=1 - 0.06 * abs(math.sin(p * math.pi * 3)))
def _hop(p):
    y = -34 * math.sin(min(p, 1) * math.pi)
    return dict(dy=y, squash=0.93 if p < 0.15 else 1.0)
def _tremble(p):   return dict(dx=2.5 * math.sin(p * math.pi * 24))
def _lean_in(p):   return dict(scale=1 + 0.08 * min(1, p * 3) * (1 if p < 0.8 else (1 - p) * 5))
def _recoil(p):    return dict(dy=-10 * math.sin(p * math.pi), scale=1 - 0.05 * math.sin(p * math.pi))
def _sigh(p):      return dict(squash=1 - 0.06 * math.sin(p * math.pi), dy=6 * math.sin(p * math.pi))
def _anticipate(p):
    if p < 0.4:  return dict(squash=1 - 0.08 * (p / 0.4))
    q = (p - 0.4) / 0.6
    return dict(dy=-30 * math.sin(q * math.pi), squash=1 + 0.05 * math.sin(q * math.pi))
def _dizzy_spin(p):return dict(rot=8 * math.sin(p * math.pi * 3))
def _glasses_put_on(p):
    gp = min(1.0, p / 0.35)
    return dict(glasses_p=gp, rot=3 * math.sin(p * math.pi))
def _glasses_push(p):
    return dict(glasses_dy=-7 * math.sin(p * math.pi))
def _glasses_off(p):
    gp = max(0.0, 1 - p / 0.35)
    return dict(glasses_p=gp)
def _glasses_glint(p):
    return dict(glint=p)   # white sweep position 0..1 across lenses
def _double_take(p):
    if p < 0.35:
        return dict(rot=4 * math.sin(p / 0.35 * math.pi))
    q = (p - 0.35) / 0.65
    return dict(rot=-11 * math.sin(q * math.pi), scale=1 + 0.07 * math.sin(q * math.pi))
def _droop(p):
    k = min(1, p * 3) * (1 if p < 0.8 else (1 - p) * 5)
    return dict(dy=14 * k, squash=1 - 0.04 * k)
def _sway(p):      return dict(dx=10 * math.sin(p * math.pi * 2), rot=4 * math.sin(p * math.pi * 2))
def _startle(p):
    k = math.sin(min(p * 1.4, 1) * math.pi)
    return dict(dy=-26 * k, scale=1 + 0.08 * k)
def _sniffle(p):
    k = max(0.0, math.sin(p * math.pi * 6))
    return dict(squash=1 - 0.03 * k, dy=2 * k)
def _head_bob(p):  return dict(rot=5 * math.sin(p * math.pi * 2))
def _glasses_look_over(p):
    k = min(1, p * 3) * (1 if p < 0.75 else max(0.0, (1 - p) * 4))
    return dict(glasses_dy=20 * k, glasses_dy_hold=k)

ACTIONS = dict(idle=_idle, nod=_nod, shake=_shake, tilt=_tilt, tilt_shake=_tilt_shake,
               bounce=_bounce, hop=_hop, tremble=_tremble, lean_in=_lean_in, recoil=_recoil,
               sigh=_sigh, anticipate=_anticipate, dizzy_spin=_dizzy_spin,
               double_take=_double_take, droop=_droop, sway=_sway, startle=_startle,
               sniffle=_sniffle, head_bob=_head_bob,
               glasses_put_on=_glasses_put_on, glasses_push=_glasses_push,
               glasses_off=_glasses_off, glasses_glint=_glasses_glint,
               glasses_look_over=_glasses_look_over)
ACTION_NAMES = sorted(ACTIONS.keys())

# ------------------------------------------------------- legacy compat layer
def draw_head(d, who, cx, cy, r, expr="neutral", mouth="closed", glasses=False,
              glasses_p=1.0, look=0, blink=False, t=0.0):
    """Compat wrapper for the v1 callers (render.py, charsheet.py)."""
    f = preset(expr if expr in PRESETS else "neutral", who)
    if mouth == "open":
        f["mouth"] = "open"; f["m_open"] = 0.6
    f["look_x"] = look * 0.6
    tile = render_head(who, r, f, glasses=glasses, glasses_p=glasses_p, blink=blink)
    frame = d._image
    frame.paste(tile, (int(cx - tile.width / 2), int(cy - tile.height / 2)), tile)

def head_image(who, r, expr="neutral", mouth="closed", glasses=False, look=0, blink=False, pad=None):
    f = preset(expr if expr in PRESETS else "neutral", who)
    if mouth == "open":
        f["mouth"] = "open"; f["m_open"] = 0.6
    f["look_x"] = look * 0.6
    return render_head(who, r, f, glasses=glasses, blink=blink)
