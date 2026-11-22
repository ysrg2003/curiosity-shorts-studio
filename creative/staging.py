import math
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1920
QB = str(Path(__file__).parent / "fonts/Quicksand-Bold.ttf")
QM = str(Path(__file__).parent / "fonts/Quicksand-Medium.ttf")

def font(path, size): return ImageFont.truetype(path, size)

# ------------------------------------------------------------------ easings
def smooth(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)

def ease_out(t):
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 3

def ease_in(t):
    t = max(0.0, min(1.0, t))
    return t ** 3

def ease_out_back(t, k=1.7):
    t = max(0.0, min(1.0, t))
    return 1 + (k + 1) * (t - 1) ** 3 + k * (t - 1) ** 2

def push_in(t, amt=0.10):
    """Slow camera push over a beat: scale 1 -> 1+amt."""
    return 1.0 + amt * smooth(t)

# ------------------------------------------------------------- backgrounds
def make_bg2(top=(22, 34, 66), bottom=(10, 16, 36), glow=None, glow_xy=None,
             glow_r=560, vignette=0.30):
    """Soft gradient + optional radial glow + vignette. glow: (r,g,b) low-alpha tint."""
    img = Image.new("RGB", (W, H))
    px = img.load()
    for y in range(H):
        p = y / H
        row = tuple(int(top[i] + (bottom[i] - top[i]) * p) for i in range(3))
        for x in range(W):
            px[x, y] = row
    if glow:
        g = Image.new("L", (W, H), 0)
        gd = ImageDraw.Draw(g)
        gx, gy = glow_xy or (W // 2, H // 2)
        for r in range(glow_r, 0, -8):
            a = int(90 * (1 - r / glow_r) ** 2)
            gd.ellipse([gx - r, gy - r, gx + r, gy + r], fill=a)
        tint = Image.new("RGB", (W, H), tuple(glow))
        img = Image.composite(Image.blend(img, tint, 0.5), img, g.point(lambda v: v // 2))
    v = Image.new("L", (W, H), 0)
    vd = ImageDraw.Draw(v)
    vd.ellipse([-W * 0.25, -H * 0.18, W * 1.25, H * 1.18], fill=255)
    v = v.resize((W // 4, H // 4)).resize((W, H))
    dark = Image.new("RGB", (W, H), (4, 7, 18))
    img = Image.composite(img, Image.blend(img, dark, vignette), v)
    return img

# --------------------------------------------------------- karaoke caption
class KaraokeCap:
    """One-line bottom caption. words: [{start,end,text}]. Renders a cached
    RGBA strip; highlight word index -1 = none."""
    SIZE = 68
    Y = 1530
    MAXW = 910

    def __init__(self, words):
        self.words = words
        self.f = font(QB, self.SIZE)
        self._cache = {}
        self.lines, cur = [], []
        measure = ImageDraw.Draw(Image.new('RGB',(8,8)))
        for i,w in enumerate(words):
            trial = ' '.join(words[j]['text'] for j in cur+[i])
            if cur and (len(cur)>=4 or measure.textlength(trial,font=self.f)>self.MAXW):
                self.lines.append(cur); cur=[]
            cur.append(i)
        if cur: self.lines.append(cur)

    def span(self, li):
        ws = self.lines[li]
        return self.words[ws[0]]["start"] - 0.05, self.words[ws[-1]]["end"] + 0.45

    def n_lines(self):
        return len(self.lines)

    def render(self, li, cur_word):
        key = (li, cur_word)
        if key in self._cache:
            return self._cache[key]
        idxs = self.lines[li]
        f = self.f
        tmp = ImageDraw.Draw(Image.new("RGB", (8, 8)))
        parts = [(self.words[i]["text"], i) for i in idxs]
        widths = [tmp.textlength(t + " ", font=f) for t, _ in parts]
        total = sum(widths)
        img = Image.new("RGBA", (int(total) + 60, self.SIZE + 46), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.rounded_rectangle((2,5,img.width-2,img.height-5),radius=24,fill=(5,11,25,165))
        x = 30
        for (t,i),wdt in zip(parts,widths):
            on = i==cur_word
            if on:
                d.rounded_rectangle((x-8,12,x+wdt-7,self.SIZE+34),radius=14,fill=(255,211,88,250))
            col=(12,24,42,255) if on else (247,246,238,255)
            if not on:
                d.text((x+2,22),t,font=f,fill=(0,0,0,220))
            d.text((x,20),t,font=f,fill=col)
            x+=wdt
        self._cache[key] = img
        return img

# ------------------------------------------------------------- leader label
class LeaderLabel:
    """In-scene explanation label with an animated leader line.
    Appears with fade+slide, line draws from label to target point."""

    def __init__(self, text, target, side="left", size=46):
        self.text = text
        self.tx, self.ty = target
        self.side = side
        self.f = font(QB, size)
        tmp = ImageDraw.Draw(Image.new("RGB", (8, 8)))
        self.tw = tmp.textlength(text, font=self.f)
        self.th = size + 14

    def draw(self, d, p, dim=1.0):
        """p: 0..1 appearance progress. dim: 1 full .. 0.35 background label."""
        if p <= 0:
            return
        p = smooth(min(1.0, p))
        a = int(255 * min(1.0, p * 1.6) * dim)
        lx = self.tx + (260 if self.side == "left" else -260) - self.tw / 2
        ly = self.ty - 170
        # slide-in from its side
        off = int((1 - p) * (60 if self.side == "left" else -60))
        lx += off
        # leader line draws from label toward target
        x1, y1 = lx + self.tw / 2, ly + self.th
        x2, y2 = self.tx, self.ty
        ex = x1 + (x2 - x1) * p
        ey = y1 + (y2 - y1) * p
        d.line([x1, y1, ex, ey], fill=(255, 214, 90, a), width=5)
        r = 8
        d.ellipse([ex - r, ey - r, ex + r, ey + r], fill=(255, 214, 90, a))
        # text with soft plate
        d.rounded_rectangle([lx - 18, ly - 12, lx + self.tw + 18, ly + self.th + 6],
                            radius=16, fill=(10, 16, 36, int(170 * dim)),
                            outline=(255, 214, 90, int(120 * dim)), width=2)
        d.text((lx, ly), self.text, font=self.f, fill=(255, 255, 255, a))

# --------------------------------------------------------------- transitions
def iris_open(frame, inner, p, center=None):
    """Composite `inner` image onto `frame` through an expanding circle."""
    cx, cy = center or (W // 2, H // 2)
    r = ease_out(p) * (W * 1.2)
    m = Image.new("L", (W, H), 0)
    md = ImageDraw.Draw(m)
    md.ellipse([cx - r, cy - r, cx + r, cy + r], fill=255)
    m = m.resize((W // 4, H // 4)).resize((W, H), Image.BILINEAR)
    frame.paste(inner, (0, 0), m)

def fade_to(frame, other, p):
    return Image.blend(frame.convert("RGB"), other.convert("RGB"), smooth(p))
