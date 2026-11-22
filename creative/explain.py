import math
from PIL import Image, ImageDraw

W, H = 1080, 1920

EPI = (247, 231, 210)       # epidermis band
EPI_EDGE = (216, 180, 150)
DERMIS = (238, 199, 178)    # dermis fill
VESSEL_WALL = (185, 66, 66)
BLOOD = (148, 38, 48)
CELL = (110, 26, 38)
NERVE = (245, 200, 90)
NERVE_DIM = (170, 135, 70)
WATER = (96, 170, 235)
INK = (16, 27, 51)


def _bez(p0, p1, p2, p3, n=64):
    pts = []
    for i in range(n + 1):
        t = i / n
        mt = 1 - t
        x = mt**3*p0[0] + 3*mt*mt*t*p1[0] + 3*mt*t*t*p2[0] + t**3*p3[0]
        y = mt**3*p0[1] + 3*mt*mt*t*p1[1] + 3*mt*t*t*p2[1] + t**3*p3[1]
        pts.append((x, y))
    return pts


class FingerCrossSection:
    """Fingertip cross-section filling the frame. Origin-free: draw(img, ...)."""

    def __init__(self):
        self.surf_base = 470.0          # resting y of skin surface center
        self.dips = [(400, 46), (480, 70), (560, 84), (640, 70), (720, 46)]  # x, depth
        self.pore_x = 295
        base = _bez((150, 1740), (210, 1400), (290, 1060), (430, 720), n=80)
        self.nerve_path = [(x + 16 * math.sin(y * 0.018), y) for x, y in base]
        self.vx0, self.vx1 = 170, 910   # vessel horizontal extent
        self.vy = 1180.0                # vessel center y
        self.vh = 150.0                 # vessel resting height
        self.pinch_x = 560.0
        self.cells = [(220 + i * 95, self.vy + (i % 3 - 1) * 26, i * 0.7) for i in range(8)]

    # ------------------------------------------------------------- surface
    def surface_y(self, x, wrinkle_p, wob=0.0):
        y = self.surf_base - 46 * math.cos((x - 540) / 700 * math.pi)  # gentle dome
        for mu, depth in self.dips:
            g = math.exp(-((x - mu) / 52) ** 2)
            y += depth * wrinkle_p * g
        return y

    def _surface_pts(self, wrinkle_p):
        return [(x, self.surface_y(x, wrinkle_p)) for x in range(40, 1041, 16)]

    # ---------------------------------------------------------------- draw
    def draw(self, img, water_p=0.0, nerve_p=0.0, squeeze_p=0.0, wrinkle_p=0.0, t=0.0):
        d = ImageDraw.Draw(img, "RGBA")
        sq = squeeze_p
        wr = wrinkle_p + 0.04 * math.sin(min(1.0, wrinkle_p) * math.pi * 3) * (0 < wrinkle_p < 1)

        # ---- dermis body (below surface, full width)
        surf = self._surface_pts(wr)
        poly = surf + [(1040, H), (40, H)]
        d.polygon(poly, fill=DERMIS)
        # watery world above the skin (tint grows as water arrives)
        above = surf + [(1040, 0), (40, 0)]
        wa = int(40 + 70 * water_p)
        d.polygon(above, fill=(60, 130, 200, wa))

        # ---- nerve (behind the vessel): wavy, tapered, branchlets at the bulb
        np_ = self.nerve_path
        act = min(1.0, nerve_p * 3) if nerve_p > 0 else 0.0
        ncol = tuple(int(NERVE_DIM[i] + (NERVE[i] - NERVE_DIM[i]) * (0.25 + 0.75 * act)) for i in range(3))
        nseg = len(np_) - 1
        for i in range(nseg):
            wd = 5 + 9 * (i / nseg)          # taper: thin root, thick near bulb
            d.line([np_[i], np_[i + 1]], fill=ncol, width=int(wd))
        bx, by = np_[-1]
        for ang in (-0.9, -0.35, 0.25):      # branchlets reaching for the surface
            ex, ey = bx + 70 * math.cos(ang - math.pi / 2), by + 70 * math.sin(ang - math.pi / 2)
            d.line([(bx, by), (ex, ey)], fill=ncol, width=6)
        # epidermis band
        band = surf + [(x, y + 92) for x, y in reversed(surf)]
        d.polygon(band, fill=EPI)
        d.line(surf, fill=EPI_EDGE, width=5, joint="curve")
        d.line([(x, y + 92) for x, y in surf], fill=(EPI_EDGE[0], EPI_EDGE[1], EPI_EDGE[2], 90), width=3)

        # ---- sweat pore (channel through epidermis into dermis)
        px = self.pore_x
        py0 = self.surface_y(px, wr) - 4
        pore = _bez((px, py0), (px - 26, py0 + 90), (px + 26, py0 + 170), (px - 8, py0 + 250), n=40)
        d.line(pore, fill=(190, 145, 120), width=26)
        d.line(pore, fill=DERMIS, width=18)

        # ---- water droplets into the pore
        if water_p > 0:
            for k in range(3):
                cyc = (t * 0.55 + k / 3) % 1.0
                # path: above surface -> pore mouth -> down the pore
                if cyc < 0.35:
                    q = cyc / 0.35
                    dx = px + 30 - 30 * q
                    dy = py0 - 150 + 150 * q * q
                else:
                    q = (cyc - 0.35) / 0.65
                    idx = min(len(pore) - 1, int(q * (len(pore) - 1)))
                    dx, dy = pore[idx]
                a = int(255 * water_p * (1 - max(0.0, cyc - 0.85) / 0.15))
                r = 13 - 4 * cyc
                d.ellipse([dx - r, dy - r * 1.25, dx + r, dy + r * 1.25], fill=WATER + (a,))
                d.ellipse([dx - r * 0.4, dy - r * 0.7, dx + r * 0.1, dy - r * 0.1],
                          fill=(200, 235, 255, a))

        # ---- blood vessel with animated pinch
        vx0, vx1, vy, vh = self.vx0, self.vx1, self.vy, self.vh
        pinch = 62 * sq
        def wall(x, sgn):
            g = math.exp(-((x - self.pinch_x) / 150) ** 2)
            return vy + sgn * (vh / 2 - pinch * g)
        top = [(x, wall(x, -1)) for x in range(vx0, vx1 + 1, 14)]
        bot = [(x, wall(x, +1)) for x in range(vx0, vx1 + 1, 14)]
        d.polygon(top + bot[::-1], fill=BLOOD)
        d.line(top, fill=VESSEL_WALL, width=10, joint="curve")
        d.line(bot, fill=VESSEL_WALL, width=10, joint="curve")
        # rounded caps
        for x in (vx0, vx1):
            d.ellipse([x - 8, wall(x, -1) - 5, x + 8, wall(x, 1) + 5], fill=BLOOD)
        # drifting blood cells, slowing as the squeeze grows
        speed = 46 * (1 - 0.75 * sq)
        for cx0, cy0, ph in self.cells:
            cxx = vx0 + ((cx0 - vx0 + t * speed + ph * 60) % (vx1 - vx0))
            g = math.exp(-((cxx - self.pinch_x) / 150) ** 2)
            cyy = cy0 * 0 + vy + (cy0 - vy) * (1 - 0.55 * sq * g) + (wall(cxx, -1) + wall(cxx, 1)) / 2 - vy
            rr = 15
            d.ellipse([cxx - rr, cyy - rr * 0.62, cxx + rr, cyy + rr * 0.62], fill=CELL)
        # squeeze force arrows while pinching
        if 0.04 < sq < 0.985:
            aa = int(255 * min(1.0, sq * 3))
            ax = self.pinch_x
            for sgn, y0 in ((-1, wall(ax, -1) - 70), (1, wall(ax, 1) + 70)):
                y1 = y0 + sgn * 44
                d.line([ax, y0, ax, y1], fill=(255, 214, 90, aa), width=7)
                d.polygon([(ax - 13, y1 - sgn * 4), (ax + 13, y1 - sgn * 4), (ax, y1 + sgn * 16)],
                          fill=(255, 214, 90, aa))

        # ---- traveling pulse over the nerve
        if 0 < nerve_p < 1:
            pos = nerve_p * (len(np_) - 1)
            i0 = int(pos)
            for j in range(14):  # trail
                idx = i0 - j
                if idx < 0:
                    break
                tx, ty = np_[idx]
                a = int(230 * (1 - j / 14))
                rr = 11 - j * 0.5
                d.ellipse([tx - rr, ty - rr, tx + rr, ty + rr], fill=(255, 236, 150, a))
            hx, hy = np_[i0]
            d.ellipse([hx - 13, hy - 13, hx + 13, hy + 13], fill=(255, 246, 190))
        if nerve_p >= 1:  # signal arrived: bulb flashes
            fr = 26 + 8 * math.sin(t * 9)
            d.ellipse([bx - fr, by - fr, bx + fr, by + fr], outline=(255, 236, 150, 200), width=6)
        d.ellipse([bx - 17, by - 17, bx + 17, by + 17], fill=NERVE if nerve_p > 0 else ncol)
        return d


# ===================================================== ep02 rigs (goosebumps)
MUSCLE = (198, 88, 80)
MUSCLE_D = (150, 58, 54)
FOLLICLE = (232, 199, 164)
FOLLICLE_EDGE = (188, 148, 116)
HAIR_COL = (56, 44, 38)
COLD_TINT = (90, 150, 220)
FUR_COL = (70, 54, 44)
WARM = (255, 196, 90)
CAT_COL = (52, 64, 96)


def _snowflake(d, x, y, s, a):
    col = (200, 225, 250, int(a))
    for ang in range(3):
        r = ang * math.pi / 3
        dx, dy = s * math.cos(r), s * math.sin(r)
        d.line([(x - dx, y - dy), (x + dx, y + dy)], fill=col, width=3)


class GoosebumpRig:
    """Skin cross-section: cold -> nerve signal -> arrector pili muscle pulls
    -> hair stands up + skin puckers into a goosebump.

    Params (continuous, ease per word timing):
      cold_p  0..1  chill arrives: snowflakes + cold tint over the skin
      nerve_p 0..1  pulse travels the wavy nerve up to the muscle
      pull_p  0..1  muscle contracts, follicle rotates upright, hair stands
      bump_p  0..1  surface puckers into the bump (couple to pull_p, lag ~0.4s)
    """

    def __init__(self):
        self.surf_base = 520.0
        self.exit_x = 470.0
        self.flen = 620.0
        self.tilt0 = math.radians(45)          # resting lean (from vertical)
        self.neighbor_x = 235.0
        ys0 = self.surface_y(self.exit_x, 0.0)
        self.anchor = (850.0, ys0 + 70.0)      # muscle anchor near the surface
        base = _bez((170, 1620), (240, 1300), (380, 1010), (640, 720), n=80)
        self.nerve_path = [(x + 14 * math.sin(y * 0.02), y) for x, y in base]

    # ------------------------------------------------------------- surface
    def surface_y(self, x, bump_p):
        y = self.surf_base - 40 * math.cos((x - 540) / 720 * math.pi)
        y -= 58 * bump_p * math.exp(-((x - self.exit_x) / 92) ** 2)   # bump
        y += 15 * bump_p * math.exp(-((x - self.exit_x) / 26) ** 2)   # dimple
        y -= 30 * bump_p * math.exp(-((x - self.neighbor_x) / 68) ** 2)
        y += 9 * bump_p * math.exp(-((x - self.neighbor_x) / 22) ** 2)
        return y

    def _surface_pts(self, bump_p):
        return [(x, self.surface_y(x, bump_p)) for x in range(40, 1041, 16)]

    def _axis(self, pull_p, bump_p, exit_x, flen, tilt0):
        th = tilt0 * (1 - pull_p)
        E = (exit_x, self.surface_y(exit_x, bump_p))
        ux, uy = math.sin(th), math.cos(th)
        B = (E[0] + flen * ux, E[1] + flen * uy)
        return E, B, ux, uy

    def _follicle(self, d, E, B, ux, uy, bulb_r, w_neck, w_base):
        # tapered follicle body from neck E to base B + round bulb
        dx, dy = B[0] - E[0], B[1] - E[1]
        L = math.hypot(dx, dy) or 1
        nx, ny = -dy / L, dx / L
        steps = 10
        left, right = [], []
        for i in range(steps + 1):
            p = i / steps
            w = w_neck + (w_base - w_neck) * p
            px, py = E[0] + dx * p, E[1] + dy * p
            left.append((px + nx * w / 2, py + ny * w / 2))
            right.append((px - nx * w / 2, py - ny * w / 2))
        d.polygon(left + right[::-1], fill=FOLLICLE, outline=FOLLICLE_EDGE)
        d.ellipse([B[0] - bulb_r, B[1] - bulb_r, B[0] + bulb_r, B[1] + bulb_r],
                  fill=FOLLICLE, outline=FOLLICLE_EDGE, width=5)

    # ---------------------------------------------------------------- draw
    def draw(self, img, cold_p=0.0, nerve_p=0.0, pull_p=0.0, bump_p=0.0, t=0.0):
        d = ImageDraw.Draw(img, "RGBA")
        surf = self._surface_pts(bump_p)

        # dermis body + cold world above the skin
        d.polygon(surf + [(1040, H), (40, H)], fill=DERMIS)
        ca = int(26 + 64 * cold_p)
        d.polygon(surf + [(1040, 0), (40, 0)], fill=COLD_TINT + (ca,))

        # nerve behind everything (to the muscle)
        np_ = self.nerve_path
        act = min(1.0, nerve_p * 3) if nerve_p > 0 else 0.0
        ncol = tuple(int(NERVE_DIM[i] + (NERVE[i] - NERVE_DIM[i]) * (0.25 + 0.75 * act)) for i in range(3))
        for i in range(len(np_) - 1):
            wd = 5 + 8 * (i / (len(np_) - 1))
            d.line([np_[i], np_[i + 1]], fill=ncol, width=int(wd))

        # neighbor follicle (simpler, rises with bump_p, slight lag)
        nb_pull = staging_smooth(bump_p * 1.15)
        En, Bn, uxn, uyn = self._axis(nb_pull, bump_p, self.neighbor_x, 470, math.radians(38))
        self._follicle(d, En, Bn, uxn, uyn, 40, 22, 44)
        tipn = (En[0] - 250 * uxn, En[1] - 250 * uyn)
        d.line([Bn, tipn], fill=HAIR_COL, width=10)

        # main follicle
        E, B, ux, uy = self._axis(pull_p, bump_p, self.exit_x, self.flen, self.tilt0)
        M = (E[0] + 0.45 * self.flen * ux, E[1] + 0.45 * self.flen * uy)
        self._follicle(d, E, B, ux, uy, 58, 26, 62)
        tip = (E[0] - 330 * ux, E[1] - 330 * uy)
        d.line([B, tip], fill=HAIR_COL, width=13)
        tr = 5
        d.ellipse([tip[0] - tr, tip[1] - tr, tip[0] + tr, tip[1] + tr], fill=HAIR_COL)

        # arrector pili muscle: anchor -> M, thicker as it contracts
        A = self.anchor
        mw = 26 + 18 * pull_p
        mx, my = (A[0] + M[0]) / 2, (A[1] + M[1]) / 2
        bulge = 14 * (1 - pull_p)          # relaxed muscle sags a little
        ddx, ddy = M[0] - A[0], M[1] - A[1]
        Lm = math.hypot(ddx, ddy) or 1
        mnx, mny = -ddy / Lm, ddx / Lm
        ctrl = (mx + mnx * bulge, my + mny * bulge)
        pts = []
        for i in range(17):
            tt = i / 16
            bx = (1 - tt) ** 2 * A[0] + 2 * (1 - tt) * tt * ctrl[0] + tt ** 2 * M[0]
            by = (1 - tt) ** 2 * A[1] + 2 * (1 - tt) * tt * ctrl[1] + tt ** 2 * M[1]
            pts.append((bx, by))
        d.line(pts, fill=MUSCLE_D, width=int(mw) + 8, joint="curve")
        d.line(pts, fill=MUSCLE, width=int(mw), joint="curve")
        d.ellipse([A[0] - mw / 2, A[1] - mw / 2, A[0] + mw / 2, A[1] + mw / 2], fill=MUSCLE)
        # contraction arrows along the muscle
        if 0.03 < pull_p < 0.985:
            aa = int(255 * min(1.0, pull_p * 3))
            for tt in (0.3, 0.7):
                px, py = pts[int(tt * 16)]
                ux2, uy2 = ddx / Lm, ddy / Lm
                if tt > 0.5:
                    ux2, uy2 = -ux2, -uy2
                ax, ay = px - ux2 * 26, py - uy2 * 26
                bx2, by2 = px + ux2 * 26, py + uy2 * 26
                d.line([(ax, ay), (bx2, by2)], fill=(255, 226, 120, aa), width=7)
                hx, hy = bx2 - ux2 * 18, by2 - uy2 * 18
                d.polygon([(hx + (-uy2) * 10, hy + ux2 * 10),
                           (hx - (-uy2) * 10, hy - ux2 * 10),
                           (bx2, by2)], fill=(255, 226, 120, aa))

        # epidermis band on top of the follicle necks
        band = surf + [(x, y + 92) for x, y in reversed(surf)]
        d.polygon(band, fill=EPI)
        d.line(surf, fill=EPI_EDGE, width=5, joint="curve")
        d.line([(x, y + 92) for x, y in surf], fill=(EPI_EDGE[0], EPI_EDGE[1], EPI_EDGE[2], 90), width=3)
        # cold tint settled on the epidermis
        if cold_p > 0:
            d.polygon(band, fill=COLD_TINT + (int(38 * cold_p),))

        # traveling nerve pulse
        if 0 < nerve_p < 1:
            pos = nerve_p * (len(np_) - 1)
            i0 = int(pos)
            for j in range(14):
                idx = i0 - j
                if idx < 0:
                    break
                tx, ty = np_[idx]
                a = int(230 * (1 - j / 14))
                rr = 11 - j * 0.5
                d.ellipse([tx - rr, ty - rr, tx + rr, ty + rr], fill=(255, 236, 150, a))
            hx, hy = np_[i0]
            d.ellipse([hx - 13, hy - 13, hx + 13, hy + 13], fill=(255, 246, 190))
        if nerve_p >= 1:
            fx, fy = np_[-1]
            fr = 24 + 8 * math.sin(t * 9)
            d.ellipse([fx - fr, fy - fr, fx + fr, fy + fr], outline=(255, 236, 150, 200), width=6)

        # snowflakes drifting down onto the skin
        if cold_p > 0.02:
            for k in range(7):
                cyc = (t * 0.22 + k / 7) % 1.0
                sx = 90 + k * 145 + 26 * math.sin(t * 0.9 + k * 2)
                sy = 40 + cyc * (self.surf_base - 120)
                a = 220 * cold_p * (1 - max(0.0, cyc - 0.85) / 0.15)
                _snowflake(d, sx, sy, 11 + 3 * math.sin(k), a)
        return d


def staging_smooth(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


class FurRig:
    """Why the trick exists (ep02 explanation part 2):
      scene A: fur stands up -> traps a warm air layer against the cold
      scene B: a puffed-up animal looks BIGGER (crossfades in at scene_p)
    Params: fur_p (fur grows), stand_p (hairs rise), warm_p (warm air layer),
            scene_p (0=A,1=B), puff_p (cat puffs up).
    """

    def __init__(self):
        self.skin_y = 1290.0
        # (x, rest tilt deg, length, sway phase)
        self.hairs = []
        import random
        rng = random.Random(7)
        for i, x in enumerate(range(95, 1000, 38)):
            self.hairs.append((float(x), 42 + rng.random() * 22,
                               300 + rng.random() * 90, rng.random() * 6.28))
        # cat geometry
        self.body = (540, 1210, 300, 165)     # cx, cy, rx, ry
        self.hump = (505, 1105, 235, 150)
        self.head = (800, 1075, 105)
        self.tail = [(300, 1180), (225, 1040), (200, 900), (240, 800)]

    # ------------------------------------------------------------- scene A
    def _hair_tip(self, x, tilt_deg, length, stand_p, t, ph):
        th = math.radians(tilt_deg) * (1 - stand_p)
        sway = 0.05 * math.sin(t * 2.2 + ph) * stand_p
        th += sway
        return (x + length * math.sin(th), self.skin_y - length * math.cos(th))

    def draw_scene_a(self, img, fur_p, stand_p, warm_p, t):
        d = ImageDraw.Draw(img, "RGBA")
        sy = self.skin_y
        # dermis + epidermis
        d.rectangle([40, sy, 1040, H], fill=DERMIS)
        d.rectangle([40, sy, 1040, sy + 92], fill=EPI)
        d.line([(40, sy), (1040, sy)], fill=EPI_EDGE, width=5)
        # trapped warm air layer
        if warm_p > 0.02:
            top = sy - 210
            for k in range(10):
                y0 = top + k * 18
                a = int(26 * warm_p * (1 - k / 12))
                d.rectangle([60, y0, 1020, y0 + 18], fill=WARM + (a,))
            # wavy warm currents
            for k in range(4):
                pts = []
                x0 = 150 + k * 210
                for i in range(25):
                    yy = sy - 12 - i * 8
                    xx = x0 + 16 * math.sin(i * 0.5 + t * 2.4 + k * 1.7)
                    pts.append((xx, yy))
                a = int(140 * warm_p)
                d.line(pts, fill=(255, 214, 110, a), width=5, joint="curve")
        # fur hairs
        for (x, tilt, length, ph) in self.hairs:
            L = 60 + fur_p * length
            tip = self._hair_tip(x, tilt, L, stand_p, t, ph)
            w = 8 + 3 * fur_p
            d.line([(x, sy), tip], fill=FUR_COL, width=int(w))
            # hair root
            d.ellipse([x - 9, sy - 6, x + 9, sy + 26], fill=FOLLICLE,
                      outline=FOLLICLE_EDGE, width=3)
        # cold arrows bouncing off the fur tips
        for k in range(4):
            ax = 170 + k * 230
            cyc = (t * 0.5 + k * 0.25) % 1.0
            ay = 120 + cyc * (sy - 420)
            fade = 1 - max(0.0, cyc - 0.8) / 0.2
            col = (140, 190, 240, int(200 * fade))
            d.line([(ax, ay), (ax, ay + 60)], fill=col, width=8)
            d.polygon([(ax - 13, ay + 48), (ax + 13, ay + 48), (ax, ay + 72)], fill=col)
        return d

    # ------------------------------------------------------------- scene B
    def draw_scene_b(self, img, puff_p, t):
        d = ImageDraw.Draw(img, "RGBA")
        cx, cy, rx, ry = self.body
        hx, hy, hr = self.head
        ux, uy, urx, ury = self.hump
        spike = 22 + 66 * puff_p
        j = 3 * math.sin(t * 7) * puff_p
        # fur spikes along back + tail (behind the silhouette)
        back = [(cx - rx + 30 + i * (2 * rx - 60) / 12,
                 cy - ry * math.sin(math.pi * (i + 0.7) / 13.4) - 14)
                for i in range(13)]
        for i, (bx, by) in enumerate(back):
            s = spike + j + 8 * math.sin(i * 1.7)
            d.polygon([(bx - 20, by + 10), (bx + 20, by + 10), (bx, by - s)], fill=CAT_COL)
        tp = self.tail
        tail_pts = _bez(tp[0], tp[1], tp[2], tp[3], n=20)
        for i, (bx, by) in enumerate(tail_pts):
            s = spike * 0.8 + j + 6 * math.sin(i * 1.3)
            d.polygon([(bx - 14, by + 12), (bx + 16, by - 12), (bx - 20, by - s)], fill=CAT_COL)
        # warm back-glow so the silhouette pops from the dark backdrop
        d.ellipse([cx - 420, cy - 330, cx + 420, cy + 330], fill=(58, 44, 34))
        d.ellipse([cx - 380, cy - 300, cx + 380, cy + 300], fill=(66, 50, 36))
        # silhouette: body + hump + head + ears + legs + tail
        d.line(tail_pts, fill=CAT_COL, width=34, joint="curve")
        d.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], fill=CAT_COL)
        d.ellipse([ux - urx, uy - ury, ux + urx, uy + ury], fill=CAT_COL)
        d.ellipse([hx - hr, hy - hr, hx + hr, hy + hr], fill=CAT_COL)
        d.polygon([(hx - 62, hy - hr + 30), (hx - 30, hy - hr - 58), (hx - 8, hy - hr + 18)], fill=CAT_COL)
        d.polygon([(hx + 18, hy - hr + 14), (hx + 52, hy - hr - 52), (hx + 70, hy - hr + 26)], fill=CAT_COL)
        for lx in (cx - 190, cx - 130, cx + 150, cx + 210):
            d.rounded_rectangle([lx - 26, cy + 60, lx + 26, cy + 240], radius=22, fill=CAT_COL)
        # angry amber eyes
        for sgn in (-1, 1):
            ex = hx + sgn * 42
            ey = hy - 12
            d.polygon([(ex - 20 * sgn, ey - 12), (ex + 22 * sgn, ey - 2),
                       (ex + 18 * sgn, ey + 10), (ex - 22 * sgn, ey + 2)], fill=(255, 196, 90))
        # size pulse arcs
        if 0.05 < puff_p:
            for sgn in (-1, 1):
                for k in range(2):
                    rr = (rx + 90 + k * 70 + 18 * math.sin(t * 5 + k)) * (0.6 + 0.4 * puff_p)
                    a = int(150 * puff_p * (1 - k * 0.35))
                    box = [cx - rr, cy - rr * 0.75, cx + rr, cy + rr * 0.75]
                    if sgn < 0:
                        d.arc(box, 120, 240, fill=(255, 196, 90, a), width=7)
                    else:
                        d.arc(box, -60, 60, fill=(255, 196, 90, a), width=7)
        return d

    def draw(self, img, fur_p=0.0, stand_p=0.0, warm_p=0.0, scene_p=0.0,
             puff_p=0.0, t=0.0):
        if scene_p >= 1.0:
            return self.draw_scene_b(img, puff_p, t)
        if scene_p <= 0.0:
            return self.draw_scene_a(img, fur_p, stand_p, warm_p, t)
        a_img = img.copy()
        self.draw_scene_a(a_img, fur_p, stand_p, warm_p, t)
        b_img = img.copy()
        self.draw_scene_b(b_img, puff_p, t)
        blended = Image.blend(a_img, b_img, staging_smooth(scene_p))
        img.paste(blended, (0, 0))
        return ImageDraw.Draw(img, "RGBA")


# ============================================================ ep03 rigs
MOUTH_CAV = (52, 24, 34)
SCOOP = (255, 205, 220)
SCOOP_EDGE = (232, 160, 185)
TONGUE = (214, 120, 130)
HEAD_SIL = (34, 46, 78)
BRAIN_COL = (238, 220, 196)
PAIN = (235, 110, 75)


class BrainFreezeRig:
    """Mouth cross-section (ep03 explanation part 1): the leading theory.
      cold_p    0..1 ice-cream scoop presses onto the palate, cold tint spreads
      squeeze_p 0..1 palate blood vessel pinches shut, blood cells slow
      dilate_p  0..1 vessel floods back open wider, cells rush bright
      nerve_p   0..1 pain signal pulse travels up the nerve toward the brain
    """

    def __init__(self):
        self.surface_base = 1080.0
        self.arch = 170.0
        self.vessel_y = 700.0
        self.vessel_pts = [(x, self.vessel_y + 22 * math.sin(x * 0.02 + 1.0))
                           for x in range(180, 901, 12)]
        base = _bez((700, 950), (760, 720), (830, 520), (930, 260), n=80)
        self.nerve_path = [(x + 12 * math.sin(y * 0.018), y) for x, y in base]
        import random
        rng = random.Random(11)
        self.cells = [(rng.random(), 5 + rng.random() * 7) for _ in range(16)]

    def surface_y(self, x):
        tt = max(0.0, min(1.0, (x - 140) / 800))
        return self.surface_base - self.arch * math.sin(math.pi * tt)

    def _surface_pts(self):
        return [(x, self.surface_y(x)) for x in range(40, 1041, 16)]

    def draw(self, img, cold_p=0.0, squeeze_p=0.0, dilate_p=0.0,
             nerve_p=0.0, t=0.0):
        d = ImageDraw.Draw(img, "RGBA")
        surf = self._surface_pts()

        # mouth cavity below the palate + tissue above
        d.polygon(surf + [(1040, H), (40, H)], fill=MOUTH_CAV)
        d.polygon(surf + [(1040, 380), (40, 380)], fill=DERMIS)

        # blood vessel inside the palate tissue
        r = 34 * (1 - 0.58 * squeeze_p) * (1 + 0.75 * dilate_p * (1 - squeeze_p))
        vp = self.vessel_pts
        d.line(vp, fill=VESSEL_WALL, width=int(2 * r) + 14, joint="curve")
        d.line(vp, fill=BLOOD, width=int(2 * r), joint="curve")
        speed = 0.030 * (1 - 0.75 * squeeze_p * (1 - dilate_p)) * (1 + 2.2 * dilate_p)
        flow = t * speed
        for off, size in self.cells:
            p = (off + flow) % 1.0
            idx = min(len(vp) - 1, int(p * (len(vp) - 1)))
            cx, cy = vp[idx]
            cc = (110, 26, 38) if dilate_p < 0.4 else (225, 90, 80)
            if squeeze_p > 0.4 and dilate_p < 0.3:
                cc = (96, 24, 36)
            rr = size * (r / 34)
            d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], fill=cc)

        # nerve to the brain (dim until the signal runs)
        np_ = self.nerve_path
        act = min(1.0, nerve_p * 3) if nerve_p > 0 else 0.0
        ncol = tuple(int(NERVE_DIM[i] + (NERVE[i] - NERVE_DIM[i]) * (0.25 + 0.75 * act)) for i in range(3))
        for i in range(len(np_) - 1):
            wd = 5 + 7 * (i / (len(np_) - 1))
            d.line([np_[i], np_[i + 1]], fill=ncol, width=int(wd))

        # palate skin band (epidermis) following the arch
        band = surf + [(x, y + 78) for x, y in reversed(surf)]
        d.polygon(band, fill=EPI)
        d.line(surf, fill=EPI_EDGE, width=5, joint="curve")
        # cold tint settling on the band near the contact point
        if cold_p > 0.02:
            cold_band = [(x, y) for x, y in surf if 380 <= x <= 740]
            if cold_band:
                cb = cold_band + [(x, y + 78) for x, y in reversed(cold_band)]
                d.polygon(cb, fill=COLD_TINT + (int(52 * cold_p),))

        # tongue resting at the bottom of the cavity
        d.ellipse([90, 1420, 750, 1680], fill=TONGUE, outline=(180, 90, 100), width=6)
        d.line([(200, 1540), (560, 1560)], fill=(180, 90, 100), width=5)

        # ice-cream scoop descending onto the palate
        sp = staging_smooth(min(1.0, cold_p * 1.25))
        scy = 1560 + (self.surface_y(560) + 112 - 1560) * sp
        scx = 560.0
        if cold_p > 0.02:
            for k, dx in enumerate((-46, 4, 44)):
                d.ellipse([scx + dx - 16, scy + 66, scx + dx + 16, scy + 66 + 34 + 10 * math.sin(t * 3 + k)],
                          fill=SCOOP)
            d.ellipse([scx - 118, scy - 118, scx + 118, scy + 118], fill=SCOOP,
                      outline=SCOOP_EDGE, width=7)
            d.ellipse([scx - 62, scy - 78, scx + 6, scy - 10], fill=(255, 228, 238))
            # cold wisps rising off the scoop
            for k in range(4):
                cyc = (t * 0.5 + k / 4) % 1.0
                wx = scx - 90 + k * 60 + 12 * math.sin(t * 2 + k)
                wy = scy - 130 - cyc * 120
                a = 200 * cold_p * (1 - cyc)
                _snowflake(d, wx, wy, 9 + 2 * k, a)
            # cold zap arrows from the scoop into the palate
            if cold_p > 0.65:
                for k, ax in enumerate((505, 560, 615)):
                    a = int(220 * (cold_p - 0.65) / 0.35)
                    cyc = (t * 1.6 + k * 0.33) % 1.0
                    ay = self.surface_y(ax) - 58 + cyc * 44
                    col = (140, 190, 240, a)
                    d.line([(ax, ay), (ax, ay + 26)], fill=col, width=7)
                    d.polygon([(ax - 10, ay + 20), (ax + 10, ay + 20), (ax, ay + 34)], fill=col)

        # traveling pain signal up the nerve
        if 0 < nerve_p < 1:
            pos = nerve_p * (len(np_) - 1)
            i0 = int(pos)
            for j in range(14):
                idx = i0 - j
                if idx < 0:
                    break
                tx, ty = np_[idx]
                a = int(230 * (1 - j / 14))
                rr = 11 - j * 0.5
                d.ellipse([tx - rr, ty - rr, tx + rr, ty + rr], fill=(255, 236, 150, a))
            hx, hy = np_[i0]
            d.ellipse([hx - 13, hy - 13, hx + 13, hy + 13], fill=(255, 246, 190))
        if nerve_p >= 1:
            fx, fy = np_[-1]
            fr = 24 + 8 * math.sin(t * 9)
            d.ellipse([fx - fr, fy - fr, fx + fr, fy + fr], outline=(255, 236, 150, 200), width=6)
        return d


class WrongAddressRig:
    """Referred pain (ep03 explanation part 2): the trigeminal nerve runs from
    the palate to a hub that also covers face and forehead, so the brain reads
    the mouth's alarm at the wrong address - the forehead lights up.
      nerve_p  0..1 nerve + branches draw in
      alarm_p  0..1 amber alarm pulses at the mouth source
      signal_p 0..1 the alarm travels mouth -> hub -> forehead
      wrong_p  0..1 pain star bursts at the forehead (the wrong address)
    """

    def __init__(self):
        self.skull = (600, 830, 350)
        self.face = [(345, 545), (300, 700), (272, 845), (240, 905),
                     (290, 950), (272, 1015), (300, 1060), (285, 1110),
                     (320, 1180), (470, 1290), (545, 1360), (545, 1560),
                     (990, 1560), (990, 830)]
        self.brain = (590, 720, 190, 130)
        self.source = (400, 1155)
        self.hub = (600, 1040)
        self.forehead = (420, 620)
        base = _bez((420, 1150), (480, 1100), (520, 1080), (600, 1040), n=40)
        self.nerve_main = [(x + 9 * math.sin(y * 0.03), y) for x, y in base]
        brf = _bez((600, 1040), (560, 900), (500, 760), (420, 620), n=50)
        self.branch_fore = [(x + 8 * math.sin(y * 0.025), y) for x, y in brf]
        brc = _bez((600, 1040), (520, 1000), (440, 960), (360, 920), n=30)
        self.branch_cheek = [(x + 7 * math.sin(y * 0.03), y) for x, y in brc]

    def _partial(self, pts, p):
        n = max(2, int(len(pts) * max(0.0, min(1.0, p))))
        return pts[:n]

    def draw(self, img, nerve_p=0.0, alarm_p=0.0, signal_p=0.0,
             wrong_p=0.0, t=0.0):
        d = ImageDraw.Draw(img, "RGBA")
        cx, cy, r = self.skull

        # head silhouette: skull circle + face profile polygon
        d.polygon(self.face, fill=HEAD_SIL)
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=HEAD_SIL)

        # brain
        bx, by, brx, bry = self.brain
        d.ellipse([bx - brx, by - bry, bx + brx, by + bry], fill=BRAIN_COL,
                  outline=(200, 176, 146), width=6)
        for k in range(3):
            pts = []
            for i in range(30):
                xx = bx - brx + 30 + i * (2 * brx - 60) / 29
                yy = by - 55 + k * 55 + 12 * math.sin(i * 0.7 + k * 2.1)
                pts.append((xx, yy))
            d.line(pts, fill=(200, 176, 146), width=5, joint="curve")

        # simple face: strained eye + open mouth with palate and tongue
        ex, ey = 372, 838
        sq = wrong_p
        d.line([(ex - 26, ey - 6 - 8 * sq), (ex + 20, ey)], fill=(240, 230, 210), width=7)
        d.line([(ex + 20, ey), (ex - 26, ey + 6 + 8 * sq)], fill=(240, 230, 210), width=7)
        d.ellipse([272, 1100, 420, 1200], fill=(20, 14, 26))
        d.line([(300, 1126), (560, 1112)], fill=EPI_EDGE, width=6)
        d.ellipse([322, 1152, 470, 1212], fill=TONGUE)
        # ice cream tint left on the palate
        d.line([(320, 1130), (470, 1121)], fill=SCOOP, width=5)

        # trigeminal nerve, drawn progressively
        main_p = min(1.0, nerve_p * 2)
        br_p = staging_smooth(nerve_p * 2 - 1)
        if main_p > 0:
            pts = self._partial(self.nerve_main, main_p)
            if len(pts) > 1:
                d.line(pts, fill=NERVE, width=11, joint="curve")
        if br_p > 0:
            for br in (self.branch_fore, self.branch_cheek):
                pts = self._partial(br, br_p)
                if len(pts) > 1:
                    d.line(pts, fill=NERVE, width=9, joint="curve")
        if nerve_p >= 0.5:
            hx, hy = self.hub
            d.ellipse([hx - 26, hy - 26, hx + 26, hy + 26], fill=NERVE,
                      outline=(255, 236, 150), width=5)

        # alarm pulsing at the mouth source
        if alarm_p > 0.02:
            dim = 1 - 0.55 * wrong_p
            for k in range(3):
                cyc = (t * 0.9 + k / 3) % 1.0
                rr = 18 + cyc * 70
                a = int(200 * alarm_p * (1 - cyc) * dim)
                d.ellipse([self.source[0] - rr, self.source[1] - rr,
                           self.source[0] + rr, self.source[1] + rr],
                          outline=(255, 214, 90, a), width=6)
            d.ellipse([self.source[0] - 13, self.source[1] - 13,
                       self.source[0] + 13, self.source[1] + 13],
                      fill=(255, 214, 90, int(255 * alarm_p * dim)))

        # the signal traveling mouth -> hub -> forehead
        if 0 < signal_p:
            path = self.nerve_main + self.branch_fore
            pos = min(len(path) - 1, int(signal_p * (len(path) - 1)))
            for j in range(12):
                idx = pos - j
                if idx < 0:
                    break
                tx, ty = path[idx]
                a = int(230 * (1 - j / 12))
                rr = 10 - j * 0.5
                d.ellipse([tx - rr, ty - rr, tx + rr, ty + rr], fill=(255, 236, 150, a))
            hx2, hy2 = path[pos]
            d.ellipse([hx2 - 13, hy2 - 13, hx2 + 13, hy2 + 13], fill=(255, 246, 190))

        # pain star at the forehead - the wrong address
        if wrong_p > 0.02:
            fx, fy = self.forehead
            base_r = (46 + 70 * wrong_p) * (1 + 0.10 * math.sin(t * 8))
            glow_r = base_r + 46
            d.ellipse([fx - glow_r, fy - glow_r, fx + glow_r, fy + glow_r],
                      fill=PAIN + (int(46 * wrong_p),))
            pts = []
            for k in range(16):
                rr = base_r if k % 2 == 0 else base_r * 0.42
                ang = k * math.pi / 8 + t * 0.6
                pts.append((fx + rr * math.cos(ang), fy + rr * math.sin(ang)))
            d.polygon(pts, fill=PAIN + (int(255 * wrong_p),))
            inner = base_r * 0.5
            pts2 = []
            for k in range(16):
                rr = inner if k % 2 == 0 else inner * 0.42
                ang = -k * math.pi / 8 - t * 0.8
                pts2.append((fx + rr * math.cos(ang), fy + rr * math.sin(ang)))
            d.polygon(pts2, fill=(255, 214, 90, int(255 * wrong_p)))
        return d


class VestibularRig:
    """Semicircular canal (ep04): why spinning makes you dizzy.
      spin_p   0..1 rotation arrows around the canal (the head is spinning)
      fluid_ph float  fluid circulation phase in cycles (caller integrates;
                      sign follows motion direction)
      bend_p   -1..1  cupula + hair-bundle bend at the canal gate
      t        time
    Signal pulses to the brain fire automatically while |bend_p| is high.
    """

    def __init__(self):
        self.c = (540.0, 950.0)
        self.r_mid = 295.0
        self.r_out = 360.0
        self.r_in = 230.0
        self.gate = math.pi / 2          # gate angle: bottom of the ring
        self.brain = (810.0, 330.0)
        base = _bez((610, 1150), (700, 900), (760, 620), (800, 420), n=70)
        self.nerve_path = [(x + 10 * math.sin(y * 0.02), y) for x, y in base]
        import random
        rng = random.Random(7)
        self.drops = [(rng.random(), 10 + rng.random() * 26, 6 + rng.random() * 7)
                      for _ in range(16)]

    def _polar(self, r, a):
        return (self.c[0] + r * math.cos(a), self.c[1] + r * math.sin(a))

    def draw(self, img, spin_p=0.0, fluid_ph=0.0, bend_p=0.0, t=0.0):
        d = ImageDraw.Draw(img, "RGBA")
        cx, cy = self.c

        # rotation arrows around the canal (head spinning)
        if spin_p > 0.02:
            rr = self.r_out + 62
            for k, a0 in enumerate((-0.5 + 0.25 * math.sin(t * 2),
                                    math.pi - 0.5 + 0.25 * math.sin(t * 2 + 1))):
                a1 = a0 + 1.5
                al = int(230 * spin_p)
                d.arc([cx - rr, cy - rr, cx + rr, cy + rr],
                      math.degrees(a0), math.degrees(a1), fill=(140, 200, 250, al), width=16)
                # arrowhead at the leading tip
                tx, ty = self._polar(rr, a1)
                ta = a1 + math.pi / 2
                ux, uy = math.cos(ta), math.sin(ta)
                px, py = math.cos(a1), math.sin(a1)
                s = 30
                d.polygon([(tx + ux * s, ty + uy * s),
                           (tx - ux * 6 + px * 16, ty - uy * 6 + py * 16),
                           (tx - ux * 6 - px * 16, ty - uy * 6 - py * 16)],
                          fill=(140, 200, 250, al))

        # canal wall ring + edges
        wall_w = int(self.r_out - self.r_in)
        d.arc([cx - self.r_mid, cy - self.r_mid, cx + self.r_mid, cy + self.r_mid],
              0, 360, fill=DERMIS, width=wall_w)
        d.arc([cx - self.r_out, cy - self.r_out, cx + self.r_out, cy + self.r_out],
              0, 360, fill=EPI_EDGE, width=7)
        d.arc([cx - self.r_in, cy - self.r_in, cx + self.r_in, cy + self.r_in],
              0, 360, fill=EPI_EDGE, width=7)

        # endolymph fluid band + moving droplets
        d.arc([cx - self.r_mid, cy - self.r_mid, cx + self.r_mid, cy + self.r_mid],
              0, 360, fill=WATER + (95,), width=wall_w - 34)
        for off, radj, size in self.drops:
            a = (off + fluid_ph) * 2 * math.pi
            r = self.r_mid + radj - 13
            x, y = self._polar(r, a)
            d.ellipse([x - size, y - size, x + size, y + size], fill=(150, 205, 250, 230))

        # cupula gate at the bottom: gel fin + bending hair bundles
        gx, gy = self._polar(self.r_mid, self.gate)
        tip_dx = bend_p * 52
        # gel fin (bends with the hairs)
        fin = [(gx - 52, gy + 62), (gx + 52, gy + 62),
               (gx + tip_dx + 20, gy - 74), (gx + tip_dx - 20, gy - 74)]
        d.polygon(fin, fill=NERVE + (150,))
        d.line(fin + [fin[0]], fill=NERVE_DIM, width=5, joint="curve")
        # hair bundles rooted on the outer wall, tips into the gel
        for k in range(6):
            hx = gx - 40 + k * 16
            base_y = gy + 60
            tipx = hx + tip_dx * (0.75 + 0.25 * math.sin(k))
            tipy = gy - 66
            d.line([(hx, base_y), (tipx, tipy)], fill=(250, 240, 210), width=6)
            d.ellipse([tipx - 5, tipy - 5, tipx + 5, tipy + 5], fill=(250, 240, 210))

        # nerve to the brain
        np_ = self.nerve_path
        act = min(1.0, abs(bend_p) * 2.2)
        ncol = tuple(int(NERVE_DIM[i] + (NERVE[i] - NERVE_DIM[i]) * (0.3 + 0.7 * act)) for i in range(3))
        d.line(np_, fill=ncol, width=8, joint="curve")
        # signal pulses while the hairs stay bent
        if act > 0.25:
            for k in range(3):
                cyc = (t * 0.9 + k / 3) % 1.0
                idx = min(len(np_) - 1, int(cyc * (len(np_) - 1)))
                tx, ty = np_[idx]
                aa = int(220 * act * (1 - abs(cyc - 0.5)))
                d.ellipse([tx - 10, ty - 10, tx + 10, ty + 10], fill=(255, 236, 150, aa))

        # brain icon
        bx, by = self.brain
        d.ellipse([bx - 118, by - 84, bx + 118, by + 84], fill=BRAIN_COL,
                  outline=(200, 176, 146), width=6)
        for k in range(3):
            pts = []
            for i in range(26):
                xx = bx - 92 + i * 184 / 25
                yy = by - 40 + k * 40 + 10 * math.sin(i * 0.8 + k * 2.2)
                pts.append((xx, yy))
            d.line(pts, fill=(200, 176, 146), width=4, joint="curve")
        if act > 0.25:
            fr = 26 + 10 * math.sin(t * 8)
            d.ellipse([bx - fr, by - fr, bx + fr, by + fr],
                      outline=(255, 236, 150, int(200 * act)), width=6)
        return d

def _star(d, cx, cy, r, col):
    import math as _m
    pts = []
    for k in range(8):
        rr = r if k % 2 == 0 else r * 0.42
        a = k * _m.pi / 4 - _m.pi / 2
        pts.append((cx + rr * _m.cos(a), cy + rr * _m.sin(a)))
    d.polygon(pts, fill=col)


ONION_SKIN = (196, 132, 96)
ONION_RING = (245, 238, 228)
ONION_RING_EDGE = (206, 180, 168)
GAS_COL = (168, 220, 130)
ACID_COL = (250, 200, 80)
EYE_WHITE = (246, 246, 240)
IRIS = (86, 130, 180)


class OnionRig:
    """Onion tears (ep05): cut cells -> enzymes build a gas -> gas dissolves
    on the eye's water -> mild acid -> tear glands flood.
      cut_p   0..1 knife slices the onion, cells break
      enz_p   0..1 enzyme sparks jump out of the broken cells
      gas_p   0..1 gas molecules form above the cut
      rise_p  0..1 gas cloud rises to the eye
      acid_p  0..1 molecules dissolve into the eye's water, acid tint + sting flash
      tears_p 0..1 tear gland floods, tears stream down
    """

    def __init__(self):
        self.onion = (400.0, 1420.0, 300.0)     # x, y, r (cross-section circle)
        self.eye = (620.0, 560.0, 300.0, 150.0)  # x, y, rx, ry
        import random
        rng = random.Random(4)
        self.mols = [(rng.random(), rng.random(), 7 + rng.random() * 7) for _ in range(22)]
        self.cells_n = 14

    def draw(self, img, cut_p=0.0, enz_p=0.0, gas_p=0.0, rise_p=0.0,
             acid_p=0.0, tears_p=0.0, t=0.0):
        d = ImageDraw.Draw(img, "RGBA")
        ox, oy, orr = self.onion
        ex, ey, erx, ery = self.eye

        # ---------------- eye (top right)
        d.ellipse([ex - erx, ey - ery, ex + erx, ey + ery], fill=EYE_WHITE,
                  outline=(200, 200, 210), width=7)
        # water film on the eye surface
        d.arc([ex - erx + 18, ey - ery + 18, ex + erx - 18, ey + ery - 18],
              20, 160, fill=WATER + (160,), width=22)
        d.ellipse([ex - 88, ey - 88, ex + 88, ey + 88], fill=IRIS)
        d.ellipse([ex - 40, ey - 40, ex + 40, ey + 40], fill=(20, 24, 36))
        d.ellipse([ex - 66, ey - 66, ex - 24, ey - 24], fill=(255, 255, 255, 200))
        # tear gland (upper outer corner)
        gx, gy = ex + erx - 60, ey - ery - 40
        d.ellipse([gx - 54, gy - 34, gx + 54, gy + 34], fill=(235, 170, 170),
                  outline=(200, 130, 130), width=5)
        # sting flash on the eye
        if acid_p > 0.05:
            for k in range(6):
                a = k * math.pi / 3 + 0.4
                sx, sy = ex + (erx + 42) * math.cos(a), ey + (ery + 42) * math.sin(a)
                al = int(230 * acid_p * (0.6 + 0.4 * math.sin(t * 7 + k)))
                _star(d, sx, sy, 15, (250, 200, 80, al))
        # tears streaming
        if tears_p > 0.03:
            for k in range(5):
                cyc = (t * 0.55 + k / 5) % 1.0
                tx = ex - 140 + k * 70 + 14 * math.sin(k * 2.3)
                ty = ey + ery - 30 + cyc * 620
                al = int(230 * tears_p * (1 - cyc * 0.6))
                d.ellipse([tx - 13, ty - 18, tx + 13, ty + 18], fill=WATER + (al,))
                d.ellipse([tx - 5, ty - 10, tx + 5, ty - 1], fill=(200, 230, 255, al))

        # ---------------- onion cross-section (bottom left)
        cut_ang = -0.5  # knife entry angle
        for k in range(5):
            rr = orr - k * 52
            col = ONION_RING if k % 2 == 0 else (232, 214, 224)
            d.ellipse([ox - rr, oy - rr, ox + rr, oy + rr], fill=col,
                      outline=ONION_RING_EDGE, width=5)
        d.ellipse([ox - orr, oy - orr, ox + orr, oy + orr], outline=ONION_SKIN, width=16)
        # cells: small blobs inside; broken ones near the cut spill
        for k in range(self.cells_n):
            a = k * 2 * math.pi / self.cells_n + 0.3
            rr = orr * (0.45 + 0.35 * ((k * 37) % 10) / 10)
            cxp, cyp = ox + rr * math.cos(a), oy + rr * math.sin(a)
            broken = cut_p > 0.15 and (k % 3 == 0)
            wob = 3 * math.sin(t * 2 + k)
            col = (250, 214, 120) if not broken else (250, 190, 90)
            d.ellipse([cxp - 24 + wob, cyp - 17, cxp + 24 + wob, cyp + 17],
                      fill=col, outline=(210, 160, 70), width=4)
            if broken:
                # sulfur bits spill out
                for j in range(3):
                    sp = min(1.0, (cut_p - 0.15) / 0.5)
                    sx = cxp + (j - 1) * 26 * sp + wob
                    sy = cyp - (20 + j * 14) * sp
                    d.ellipse([sx - 7, sy - 7, sx + 7, sy + 7], fill=(250, 230, 130))

        # knife descending from the top onto the onion
        kp = staging_smooth(min(1.0, cut_p * 1.3))
        kx0, ky0 = ox - 180, oy - orr - 330 + 300 * kp
        blade = [(kx0, ky0), (kx0 + 190, ky0 + 40), (kx0 + 210, ky0 + 86), (kx0 + 20, ky0 + 66)]
        d.polygon(blade, fill=(215, 222, 232), outline=(150, 158, 170))
        d.rounded_rectangle([kx0 - 130, ky0 - 16, kx0 + 16, ky0 + 34], radius=16,
                            fill=(90, 70, 60))
        # slice line through the onion once the knife lands
        if cut_p > 0.4:
            sp = min(1.0, (cut_p - 0.4) / 0.5)
            d.line([(ox - orr * sp, oy - 10), (ox + orr * sp, oy - 10)],
                   fill=(120, 70, 50), width=10)

        # enzyme sparks jumping out of broken cells
        if enz_p > 0.03:
            for k in range(8):
                cyc = (t * 0.9 + k / 8) % 1.0
                a = k * math.pi / 4 + 0.2
                rr = orr * 0.4 + cyc * orr * 0.75
                sx, sy = ox + rr * math.cos(a), oy - abs(rr * math.sin(a)) * 0.9
                al = int(240 * enz_p * (1 - cyc))
                _star(d, sx, sy, 11, (255, 240, 150, al))

        # gas molecules forming over the cut, then rising to the eye
        if gas_p > 0.03:
            for off, radj, size in self.mols:
                cyc = (off + t * 0.05) % 1.0
                bx = ox - 60 + (off * 7 % 1.0) * 220 + 20 * math.sin(t * 1.3 + off * 9)
                by = oy - orr - 40 - cyc * 240
                # rise path toward the eye
                rx = bx + (ex - bx) * rise_p
                ry = by + (ey + 40 - by) * rise_p
                col = GAS_COL if rise_p < 0.999 else ACID_COL
                al = int(235 * gas_p)
                d.ellipse([rx - size, ry - size, rx + size, ry + size], fill=col + (al,))
                d.ellipse([rx - size * 0.4, ry - size * 0.4, rx + size * 0.1, ry + size * 0.1],
                          fill=(255, 255, 255, int(al * 0.7)))

        # acid tint spreading over the eye's water film
        if acid_p > 0.03:
            d.arc([ex - erx + 18, ey - ery + 18, ex + erx - 18, ey + ery - 18],
                  20, 160, fill=ACID_COL + (int(150 * acid_p),), width=26)
        # gland flood glow
        if tears_p > 0.03:
            gl = 20 + 9 * math.sin(t * 6)
            d.ellipse([gx - gl * 2, gy - gl * 1.4, gx + gl * 2, gy + gl * 1.4],
                      outline=(120, 190, 240, int(200 * tears_p)), width=6)
        return d

# ---- ep06 hiccups palette
TORSO = (58, 66, 108)
TORSO_EDGE = (96, 106, 158)
LUNG = (235, 150, 150)
LUNG_EDGE = (200, 105, 105)
DIAPH = (245, 190, 90)
DIAPH_EDGE = (205, 145, 55)
AIRWAY = (150, 190, 235)
AIRWAY_EDGE = (110, 150, 205)
GATE = (250, 220, 140)
HIC_COL = (255, 226, 120)
TRIG_COL = (255, 180, 90)


class HiccupRig:
    """Hiccups (ep06): side-view torso. A nerve signal reaches the diaphragm,
    the dome snaps down (spasm), air is yanked in, and the glottis gate slams
    shut: the slam is the HIC.
      spasm_p   0..1 diaphragm dome pulled flat/down (the squeeze)
      nerve_p   0..1 signal pulse traveling down the nerve to the diaphragm
      irrit_p   0..1 trigger sparks (fast eating, fizz, excitement) hit the nerve
      air_p     0..1 air chevrons rushing down the airway
      gate_p    0..1 glottis flaps slammed shut
      hic_p     0..1 HIC burst flash at the gate
      calm_p    0..1 everything settled, dome relaxed (finale)
    """

    def __init__(self):
        self.throat = (540.0, 420.0)        # glottis gate center
        self.airway_top = (540.0, 200.0)
        self.split_y = 780.0                # where the airway forks
        self.lungL = (360.0, 1050.0)
        self.lungR = (720.0, 1050.0)
        self.diaph_y0 = 1330.0              # resting dome center height
        self.nerve_pts = _bez((880, 300), (940, 640), (800, 1000), (760, 1300), n=70)

    def dome_y(self, x, spasm_p):
        # dome arc under the lungs: center rises at rest, flattens + drops on spasm
        cx, half = 540.0, 330.0
        u = max(-1.0, min(1.0, (x - cx) / half))
        arch = (1 - u * u)
        y = self.diaph_y0 - 120 * arch * (1 - spasm_p) + 90 * spasm_p
        return y

    def draw(self, img, spasm_p=0.0, nerve_p=0.0, irrit_p=0.0, air_p=0.0,
             gate_p=0.0, hic_p=0.0, calm_p=0.0, t=0.0):
        d = ImageDraw.Draw(img, "RGBA")
        tx, ty = self.throat

        # ---------------- torso silhouette
        d.rounded_rectangle([170, 140, 910, 1620], radius=90, fill=TORSO + (255,),
                            outline=TORSO_EDGE, width=8)

        # ---------------- lungs (they bulge a touch on the inhale)
        bulge = 1.0 + 0.06 * air_p
        for (lx, ly) in (self.lungL, self.lungR):
            rw, rh = 150 * bulge, 260 * bulge
            d.ellipse([lx - rw, ly - rh, lx + rw, ly + rh], fill=LUNG,
                      outline=LUNG_EDGE, width=7)

        # ---------------- diaphragm dome
        pts = [(x, self.dome_y(x, spasm_p)) for x in range(210, 871, 22)]
        pts += [(880, 1500), (200, 1500)]
        d.polygon(pts, fill=DIAPH, outline=DIAPH_EDGE)
        # spasm shiver marks on the dome while it squeezes
        if spasm_p > 0.25:
            for k in range(4):
                x = 330 + k * 140
                y = self.dome_y(x, spasm_p) - 26
                a = int(220 * spasm_p)
                d.line([(x - 14, y), (x, y - 16), (x + 14, y)], fill=(120, 70, 30, a), width=6)

        # ---------------- airway tube + fork
        ax, ay_top = self.airway_top
        d.rounded_rectangle([ax - 34, ay_top, ax + 34, self.split_y], radius=24,
                            fill=AIRWAY, outline=AIRWAY_EDGE, width=6)
        for sgn, (lx, ly) in ((-1, self.lungL), (1, self.lungR)):
            d.line([(ax, self.split_y), (lx, ly - 220)], fill=AIRWAY, width=52)
            d.line([(ax, self.split_y), (lx, ly - 220)], fill=AIRWAY_EDGE, width=6)
        # mouth opening at top
        d.ellipse([ax - 40, ay_top - 34, ax + 40, ay_top + 10], fill=(20, 24, 44),
                  outline=AIRWAY_EDGE, width=6)

        # ---------------- air chevrons rushing in
        if air_p > 0.03:
            for k in range(4):
                cyc = (t * 1.4 + k / 4) % 1.0
                y = ay_top + 30 + cyc * (self.split_y - ay_top - 60)
                stop = gate_p > 0.6 and y > ty - 50
                if stop:
                    continue
                a = int(235 * air_p)
                d.line([(ax - 18, y), (ax, y + 20), (ax + 18, y)],
                       fill=(255, 255, 255, a), width=8)

        # ---------------- glottis gate (two flaps)
        gap = 30 * (1 - gate_p)
        ang = 40 - 36 * gate_p
        for sgn in (-1, 1):
            x0, y0 = tx + sgn * 52, ty
            x1 = x0 - sgn * (52 - gap)
            y1 = ty - 60 + ang
            d.line([(x0, y0 - 4), (x1, y1)], fill=GATE, width=16)
            d.line([(x0, y0 + 4), (x1, y1 + 44)], fill=GATE, width=16)
        d.arc([tx - 70, ty - 74, tx + 70, ty + 74], 0, 360,
              fill=(200, 160, 90, 160), width=5)

        # ---------------- nerve path + traveling pulse
        pts = self.nerve_pts
        d.line(pts, fill=NERVE, width=10, joint="curve")
        # brainstem dot
        bx, by = pts[0]
        d.ellipse([bx - 20, by - 20, bx + 20, by + 20], fill=NERVE,
                  outline=NERVE_DIM, width=5)
        if nerve_p > 0.01:
            # pulse dot travels; rings ripple behind it
            idx = min(len(pts) - 1, int(nerve_p * (len(pts) - 1)))
            px, py = pts[idx]
            d.ellipse([px - 16, py - 16, px + 16, py + 16], fill=(255, 240, 170),
                      outline=NERVE_DIM, width=5)
            for k in range(3):
                lag = idx - (k + 1) * 7
                if lag > 0:
                    lx2, ly2 = pts[lag]
                    r = 12 + 8 * k
                    a = int(160 * (1 - k / 3) * nerve_p)
                    d.ellipse([lx2 - r, ly2 - r, lx2 + r, ly2 + r],
                              outline=(255, 240, 170, a), width=4)

        # ---------------- trigger sparks flying at the nerve start
        if irrit_p > 0.03:
            for k in range(6):
                cyc = (t * 0.8 + k / 6) % 1.0
                sx = 120 + cyc * (bx - 140)
                sy = by - 40 + 80 * ((k * 41) % 10) / 10
                a = int(230 * irrit_p * (1 - cyc * 0.4))
                _star(d, sx, sy, 11, TRIG_COL + (a,))

        # ---------------- HIC burst at the gate
        if hic_p > 0.02:
            for k in range(8):
                a = k * math.pi / 4 + 0.2
                rr = 60 + 90 * hic_p
                sx, sy = tx + rr * math.cos(a), ty + rr * math.sin(a)
                al = int(240 * hic_p)
                _star(d, sx, sy, 14, HIC_COL + (al,))
            ring_r = 40 + 130 * (1 - hic_p)
            d.ellipse([tx - ring_r, ty - ring_r, tx + ring_r, ty + ring_r],
                      outline=(255, 240, 170, int(200 * hic_p)), width=7)

        # ---------------- calm shimmer
        if calm_p > 0.03:
            for k in range(5):
                cyc = (t * 0.25 + k / 5) % 1.0
                sx = 300 + k * 120
                sy = 700 + 500 * cyc
                a = int(120 * calm_p * (1 - cyc))
                _star(d, sx, sy, 9, (190, 230, 255, a))
        return d


# ---------------------------------------------------------------- ep07 gut
GUT = (238, 168, 132)
GUT_EDGE = (198, 120, 88)
LUMEN = (250, 214, 176)
CRUMB = (146, 92, 48)
BUBBLE = (190, 225, 250)
WAVE_COL = (255, 214, 110)
SENSE_COL = (255, 235, 150)
RUMBLE_COL = (255, 226, 140)


class GutRig:
    """Stomach growl (ep07): belly cutaway. A muscular gut tube squeezes in
    waves (peristalsis), pushing food + juice + air; the pushing makes the
    rumble. When empty ~2h, wall sensors trigger the migrating motor complex:
    a cleaning wave that sweeps leftovers down, and the empty tube cannot
    muffle the sound.
      squeeze_p 0..1 ambient peristalsis strength (contraction bands travel)
      rumble_p  0..1 sound arcs + tube wobble at the squeeze
      empty_p   0..1 lumen dims, gas bubbles multiply (hungry gut)
      sensor_p  0..1 spark burst on the stomach wall (sensors fire)
      wave_p    0..1 cleaning-wave front position along the tube (0=off)
      crumbs_p  0..1 leftover crumbs visible inside the lumen
      loud_p    0..1 big sound burst (empty tube = no muffling)
      fed_p     0..1 calm settled gut (finale: fed, rumbling stops)
    """

    def __init__(self):
        self.belly = (170, 200, 910, 1700)
        self.stom = (540.0, 470.0)          # stomach sac center
        # serpentine gut path under the stomach
        spine = [(540, 660), (330, 800), (750, 800), (750, 970), (330, 970),
                 (330, 1140), (750, 1140), (750, 1310), (430, 1310)]
        pts = []
        for i in range(len(spine) - 1):
            x0, y0 = spine[i]
            x1, y1 = spine[i + 1]
            n = 46
            for k in range(n):
                u = k / n
                pts.append((x0 + (x1 - x0) * u, y0 + (y1 - y0) * u))
        pts.append(spine[-1])
        self.path = pts
        self.cum = [0.0]
        for i in range(1, len(pts)):
            dx = pts[i][0] - pts[i - 1][0]
            dy = pts[i][1] - pts[i - 1][1]
            self.cum.append(self.cum[-1] + math.hypot(dx, dy))
        self.total = self.cum[-1]
        self.crumbs_u = [0.08, 0.2, 0.31, 0.45, 0.57, 0.7, 0.82]
        self.bubble_u = [0.05, 0.25, 0.5, 0.66, 0.9]

    def pos_at(self, u):
        u = max(0.0, min(1.0, u))
        target = u * self.total
        lo, hi = 0, len(self.cum) - 1
        while lo + 1 < hi:
            mid = (lo + hi) // 2
            if self.cum[mid] <= target:
                lo = mid
            else:
                hi = mid
        seg = max(1e-6, self.cum[hi] - self.cum[lo])
        f = (target - self.cum[lo]) / seg
        x = self.path[lo][0] + (self.path[hi][0] - self.path[lo][0]) * f
        y = self.path[lo][1] + (self.path[hi][1] - self.path[lo][1]) * f
        return x, y

    def draw(self, img, squeeze_p=0.0, rumble_p=0.0, empty_p=0.0, sensor_p=0.0,
             wave_p=0.0, crumbs_p=0.0, loud_p=0.0, fed_p=0.0, t=0.0):
        d = ImageDraw.Draw(img, "RGBA")
        wob = 7.0 * max(rumble_p, loud_p) * math.sin(t * 9.0)

        # ---------------- belly silhouette
        x0, y0, x1, y1 = self.belly
        d.rounded_rectangle([x0, y0, x1, y1], radius=100, fill=TORSO + (255,),
                            outline=TORSO_EDGE, width=8)

        # ---------------- stomach sac (J-ish blob)
        sx, sy = self.stom
        d.ellipse([sx - 190, sy - 150, sx + 190, sy + 170], fill=GUT,
                  outline=GUT_EDGE, width=9)
        d.ellipse([sx - 150, sy - 110, sx + 150, sy + 130], fill=LUMEN)
        # esophagus stub on top
        d.rounded_rectangle([sx - 42, sy - 260, sx + 42, sy - 110], radius=28,
                            fill=GUT, outline=GUT_EDGE, width=7)

        # ---------------- gut tube (wall + lumen), wobbling with the rumble
        wall = [(px + wob, py) for px, py in self.path]
        d.line(wall, fill=GUT, width=104, joint="curve")
        for px, py in wall[::24]:
            d.ellipse([px - 52, py - 52, px + 52, py + 52], fill=GUT)
        lum_col = tuple(int(c * (1 - 0.35 * empty_p) + 40 * 0.35 * empty_p)
                        for c in LUMEN)
        # cleaning-wave halo UNDER the lumen (drawn before it)
        if wave_p > 0.0:
            tail = [(px + wob, py) for i, (px, py) in enumerate(self.path)
                    if self.cum[i] <= wave_p * self.total]
            if len(tail) > 1:
                d.line(tail, fill=WAVE_COL + (90,), width=88, joint="curve")
                for px, py in tail[::24]:
                    d.ellipse([px - 44, py - 44, px + 44, py + 44],
                              fill=WAVE_COL + (90,))
        d.line([(px + wob, py) for px, py in self.path], fill=lum_col, width=64,
               joint="curve")
        for px, py in wall[::24]:
            d.ellipse([px - 32, py - 32, px + 32, py + 32], fill=lum_col)

        # ---------------- leftover crumbs riding the lumen (swept by the wave)
        if crumbs_p > 0.03:
            for i, cu in enumerate(self.crumbs_u):
                if wave_p > 0.0 and wave_p >= cu - 0.03:
                    du = min(1.02, wave_p + 0.02)   # pushed just ahead of front
                    if du > 1.0:
                        continue
                else:
                    du = cu
                cx, cy = self.pos_at(du)
                a = int(235 * crumbs_p)
                r = 13 + (i % 3) * 4
                d.ellipse([cx + wob - r, cy - r, cx + wob + r, cy + r],
                          fill=CRUMB + (a,))

        # ---------------- gas bubbles (multiply when empty)
        nb = 2 + int(3 * empty_p)
        for k in range(nb):
            bu = (self.bubble_u[k] + t * 0.02) % 1.0
            bx, by = self.pos_at(bu)
            r = 15 + 6 * math.sin(t * 2.0 + k * 2.3)
            a = int(120 + 90 * empty_p)
            d.ellipse([bx + wob - r, by - r, bx + wob + r, by + r],
                      outline=BUBBLE + (a,), width=5)

        # ---------------- peristalsis contraction bands
        if squeeze_p > 0.03:
            for band in range(2):
                bu = (t * 0.16 + band * 0.5) % 1.0
                bx, by = self.pos_at(bu)
                a = int(210 * squeeze_p * (1.0 - 0.35 * band))
                d.ellipse([bx + wob - 62, by - 62, bx + wob + 62, by + 62],
                          outline=GUT_EDGE + (a,), width=10)
                d.ellipse([bx + wob - 40, by - 40, bx + wob + 40, by + 40],
                          outline=WAVE_COL + (a,), width=6)

        # ---------------- wall sensors firing on the stomach
        if sensor_p > 0.03:
            for k in range(6):
                ang = k * math.pi / 3 + 0.35
                px = sx + 200 * math.cos(ang)
                py = sy + 165 * math.sin(ang)
                a = int(240 * sensor_p)
                _star(d, px, py, 12, SENSE_COL + (a,))

        # ---------------- the cleaning wave front (migrating motor complex)
        if wave_p > 0.0:
            wx, wy = self.pos_at(wave_p)
            _star(d, wx + wob, wy, 26, WAVE_COL + (240,))
            _star(d, wx + wob, wy, 13, (255, 245, 200, 255))

        # ---------------- rumble sound arcs (from stomach / current squeeze)
        amp = max(rumble_p, loud_p)
        if amp > 0.03:
            cx0, cy0 = self.stom
            if squeeze_p > 0.05:
                cx0, cy0 = self.pos_at((t * 0.16) % 1.0)
            big = 1.0 + 0.9 * loud_p
            for k in range(3):
                cyc = (t * 0.9 + k / 3) % 1.0
                rr = (60 + cyc * 190) * big
                a = int(220 * amp * (1 - cyc))
                d.arc([cx0 - rr, cy0 - rr, cx0 + rr, cy0 + rr],
                      start=-55, end=55, fill=RUMBLE_COL + (a,), width=9)
                d.arc([cx0 - rr, cy0 - rr, cx0 + rr, cy0 + rr],
                      start=125, end=235, fill=RUMBLE_COL + (a,), width=9)

        # ---------------- fed calm shimmer
        if fed_p > 0.03:
            for k in range(5):
                cyc = (t * 0.25 + k / 5) % 1.0
                px = 300 + k * 120
                py = 700 + 500 * cyc
                a = int(120 * fed_p * (1 - cyc))
                _star(d, px, py, 9, (190, 230, 255, a))
        return d
