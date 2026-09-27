#!/usr/bin/env python3
"""Peak Arcade pixel-art generator for Story Scout Next v2 (stdlib only).

Not a build step: the SVGs it writes are committed under v2/assets/px/.
Re-run only when you want to redraw the art:

    python3 v2/tools/pixelart.py

Every pixel is a unit square merged into one <path> per colour, rendered
with shape-rendering="crispEdges", so the art stays razor sharp at any size.

Sprites (Nico, ball, farmhouse...) use fixed palette hex fills.
Scenes use role classes (s-sky0, s-far, ...) that css/style.css maps to
palette tokens per theme, so night/day recolour the same art.
"""
import math
import os
import random

from palette import P
from nico_data import SPRITES as NICO

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "assets", "px")


# --------------------------------------------------------------------------
# Raster core
# --------------------------------------------------------------------------
class Canvas:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.px = {}

    def get(self, x, y):
        return self.px.get((x, y))

    def set(self, x, y, k):
        if 0 <= x < self.w and 0 <= y < self.h and k is not None:
            self.px[(x, y)] = k

    def clear(self, x, y):
        self.px.pop((x, y), None)

    def rect(self, x0, y0, w, h, k):
        for y in range(y0, y0 + h):
            for x in range(x0, x0 + w):
                self.set(x, y, k)

    def ellipse(self, cx, cy, rx, ry, k, lit=None):
        """Filled ellipse. lit=(hi, base, lo) shades by surface normal, light top-left."""
        for y in range(int(cy - ry - 1), int(cy + ry + 2)):
            for x in range(int(cx - rx - 1), int(cx + rx + 2)):
                dx, dy = (x + 0.5 - cx) / rx, (y + 0.5 - cy) / ry
                if dx * dx + dy * dy <= 1.0:
                    if lit:
                        light = -(dx * 0.6 + dy * 0.8)
                        c = lit[0] if light > 0.55 else lit[2] if light < -0.45 else lit[1]
                        self.set(x, y, c)
                    else:
                        self.set(x, y, k)

    def poly(self, pts, k):
        ys = [p[1] for p in pts]
        for y in range(int(min(ys)), int(max(ys)) + 1):
            yc = y + 0.5
            xs = []
            n = len(pts)
            for i in range(n):
                (x1, y1), (x2, y2) = pts[i], pts[(i + 1) % n]
                if (y1 <= yc < y2) or (y2 <= yc < y1):
                    xs.append(x1 + (yc - y1) * (x2 - x1) / (y2 - y1))
            xs.sort()
            for a, b in zip(xs[::2], xs[1::2]):
                for x in range(int(math.ceil(a - 0.5)), int(math.floor(b - 0.5)) + 1):
                    self.set(x, y, k)

    def line(self, x0, y0, x1, y1, k):
        n = int(max(abs(x1 - x0), abs(y1 - y0))) + 1
        for i in range(n + 1):
            t = i / max(n, 1)
            self.set(int(round(x0 + (x1 - x0) * t)), int(round(y0 + (y1 - y0) * t)), k)

    def outline(self, k, diag=False):
        """Paint k into empty cells touching any filled cell."""
        add = []
        nb = [(1, 0), (-1, 0), (0, 1), (0, -1)]
        if diag:
            nb += [(1, 1), (-1, -1), (1, -1), (-1, 1)]
        for y in range(self.h):
            for x in range(self.w):
                if (x, y) in self.px:
                    continue
                if any((x + dx, y + dy) in self.px for dx, dy in nb):
                    add.append((x, y))
        for x, y in add:
            self.set(x, y, k)

    def stamp(self, other, ox, oy, flip=False):
        for (x, y), k in other.px.items():
            self.set(ox + (other.w - 1 - x if flip else x), oy + y, k)

    def from_ascii(self, rows, keymap, ox=0, oy=0):
        for y, row in enumerate(rows):
            for x, ch in enumerate(row):
                if ch in keymap:
                    self.set(ox + x, oy + y, keymap[ch])


def svg_paths(canvas, colour_attr):
    """Merge horizontal runs into one path per key. colour_attr(key) -> attr string."""
    runs = {}
    for y in range(canvas.h):
        x = 0
        while x < canvas.w:
            k = canvas.get(x, y)
            if k is None:
                x += 1
                continue
            x0 = x
            while x < canvas.w and canvas.get(x, y) == k:
                x += 1
            runs.setdefault(k, []).append("M%d %dh%dv1h-%dz" % (x0, y, x - x0, x - x0))
    return "".join('<path %s d="%s"/>' % (colour_attr(k), "".join(d)) for k, d in runs.items())


def write_sprite(name, canvas, title):
    body = svg_paths(canvas, lambda k: 'fill="%s"' % P.get(k, k))
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" width="%d" height="%d" '
        'shape-rendering="crispEdges"><title>%s</title>%s</svg>\n'
        % (canvas.w, canvas.h, canvas.w * 4, canvas.h * 4, title, body)
    )
    with open(os.path.join(OUT, name + ".svg"), "w") as f:
        f.write(svg)
    return svg


def write_scene(name, canvas, eggs=(), title="", front=None):
    """Scene: role keys become classes; eggs = [(canvas, x, y, id)] get their own <g>.
    front: optional Canvas painted over the eggs (so Nico can hide behind things)."""
    body = svg_paths(canvas, lambda k: 'class="s-%s"' % k)
    egg_svg = ""
    for ec, ex, ey, eid in eggs:
        inner = svg_paths(ec, lambda k: 'fill="%s"' % P.get(k, k))
        egg_svg += (
            '<g class="nico-egg" data-egg="%s" transform="translate(%d %d)" tabindex="-1">'
            '<rect x="-2" y="-2" width="%d" height="%d" fill="transparent"/><g class="egg-body">%s</g></g>'
            % (eid, ex, ey, ec.w + 4, ec.h + 4, inner)
        )
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" '
        'preserveAspectRatio="xMidYMax slice" shape-rendering="crispEdges" aria-hidden="true">'
        "<title>%s</title>%s%s%s</svg>\n"
        % (canvas.w, canvas.h, title, body, egg_svg,
           svg_paths(front, lambda k: 'class="s-%s"' % k) if front else "")
    )
    with open(os.path.join(OUT, "scene-" + name + ".svg"), "w") as f:
        f.write(svg)


# --------------------------------------------------------------------------
# Nico: every sprite comes from the owner's art (see extract_nico.py);
# nico_data.py holds the palette-keyed pixel grids.
# --------------------------------------------------------------------------
INK = "void"


def from_grid(grid):
    c = Canvas(len(grid[0]), len(grid))
    for y, row in enumerate(grid):
        for x, k in enumerate(row):
            if k:
                c.set(x, y, k)
    return c


def nico_egg():
    """Tiny sitting Nico (from the sprite sheet) for the hidden background eggs."""
    return from_grid(NICO["nico-egg"])


def nico_peek(rows=8):
    """Just Nico's head over a ledge."""
    full = nico_egg()
    c = Canvas(full.w, rows)
    for (x, y), k in full.px.items():
        if y < rows:
            c.set(x, y, k)
    return c


# --------------------------------------------------------------------------
# Props
# --------------------------------------------------------------------------
def ball():
    """Nico's orange ball with the blue seam (as in the owner's sprite sheet), 10x10."""
    c = Canvas(12, 12)
    c.ellipse(6, 6, 5, 5, None, lit=("sandy-600", "sandy-700", "sandy-800"))
    for x in range(1, 11):                     # curved seam, like the sheet's ball
        y = int(round(3 + 0.09 * (x - 6) ** 2 + (x - 1) * 0.35))
        c.set(x, y, "indigo-600")
        c.set(x, y + 1, "indigo-700")
    c.set(4, 3, "ant-50")
    c.outline(INK)
    return c


def farmhouse():
    c = Canvas(64, 44)
    # barn body
    c.rect(6, 18, 34, 22, "burg-700")
    for x in range(6, 40, 3):
        c.rect(x, 18, 1, 22, "burg-800")
    c.poly([(3, 19), (23, 4), (43, 19)], "space-900")
    c.poly([(7, 18), (23, 7), (39, 18)], "indigo-800")
    for y in range(9, 18, 2):
        c.line(23 - (y - 7) * 1.4, y, 23 + (y - 7) * 1.4, y, "indigo-900")
    # hay door
    c.rect(19, 10, 8, 6, "ant-100")
    c.rect(20, 11, 6, 4, "sandy-400")
    c.line(20, 11, 25, 14, "ant-100")
    c.line(25, 11, 20, 14, "ant-100")
    # big door with X trim
    c.rect(16, 26, 14, 14, "ant-100")
    c.rect(17, 27, 12, 13, "burg-600")
    c.line(17, 27, 28, 39, "ant-100")
    c.line(28, 27, 17, 39, "ant-100")
    # lit windows
    for wx in (9, 33):
        c.rect(wx, 23, 5, 5, "ant-100")
        c.rect(wx + 1, 24, 3, 3, "sandy-600")
        c.set(wx + 1, 24, "ant-50")
    # farmhouse annex
    c.rect(40, 24, 20, 16, "ant-200")
    c.poly([(38, 25), (50, 15), (62, 25)], "space-900")
    c.rect(44, 29, 4, 4, "sandy-600")
    c.rect(52, 29, 4, 4, "sandy-600")
    c.rect(48, 33, 4, 7, "indigo-700")
    c.rect(55, 13, 3, 6, "burg-800")  # chimney
    c.outline(INK)
    return c


def convertible():
    """Not used in the final sequence; kept small for future vignettes."""
    return None


# --------------------------------------------------------------------------
# Logo badge (pixel rendition of The Daily Goods smile mark)
# --------------------------------------------------------------------------
def medallion(size=40):
    """Sunburst disc Nico sits on so the black coat reads on dark UIs."""
    c = Canvas(size, size)
    r = size / 2
    for y in range(size):
        for x in range(size):
            dx, dy = x + 0.5 - r, y + 0.5 - r
            d = math.hypot(dx, dy)
            if d <= r - 0.5:
                a = math.atan2(dy, dx)
                ray = int((a + math.pi) / (2 * math.pi) * 16) % 2
                if d > r - 2.5:
                    c.set(x, y, "rasp-600")
                elif d > r - 3.5:
                    c.set(x, y, "burg-700")
                else:
                    c.set(x, y, "sandy-600" if ray else "sandy-400")
    return c


# --------------------------------------------------------------------------
# Scene helpers (role keys -> classes)
# --------------------------------------------------------------------------
BAYER = [[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]


def sky(c, bands, top=0, bottom=None):
    """Vertical gradient between role keys with ordered-dither transitions."""
    bottom = bottom if bottom is not None else c.h
    n = len(bands) - 1
    for y in range(top, bottom):
        t = (y - top) / max(1, bottom - top - 1) * n
        i = min(int(t), n - 1)
        f = t - i
        for x in range(c.w):
            thresh = (BAYER[y % 4][x % 4] + 0.5) / 16
            # flat band, then an ordered-dither seam over its last 40%
            seam = (f - 0.6) / 0.4
            c.set(x, y, bands[i + 1] if seam > thresh else bands[i])


def stars(c, rng, n, ymax, keys=("star", "star", "star2")):
    for _ in range(n):
        x, y = rng.randrange(c.w), rng.randrange(ymax)
        c.set(x, y, rng.choice(keys))
    # a few 4-point twinkles
    for _ in range(max(1, n // 18)):
        x, y = rng.randrange(4, c.w - 4), rng.randrange(3, max(4, ymax - 10))
        c.set(x, y, "star")
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            c.set(x + dx, y + dy, "star2")


def ridge(c, rng, base_y, amp, freq, key, hi=None, seed=0, jag=0):
    ph = seed * 1.7
    for x in range(c.w):
        y = base_y - amp * (0.6 * math.sin(x * freq + ph) + 0.4 * math.sin(x * freq * 2.3 + ph * 2))
        if jag:
            y -= (x * 7 + seed) % jag
        y = int(round(y))
        for yy in range(y, c.h):
            c.set(x, yy, key)
        if hi:
            c.set(x, y, hi)


def pine(c, x, y, h, key, hi=None):
    for i in range(h):
        w = 1 + (i * 2) // 3 if i % 3 else (i * 2) // 3
        c.rect(x - w, y - h + i, w * 2 + 1, 1, key)
        if hi and i % 3 == 1:
            c.set(x - w, y - h + i, hi)
    c.rect(x, y, 1, 2, key)


def building(c, x, w, top, key, win, win2=None, rng=None, lit=0.35, roof=None):
    c.rect(x, top, w, c.h - top, key)
    if roof:
        c.rect(x, top, w, 1, roof)
    for yy in range(top + 3, c.h - 3, 4):
        for xx in range(x + 2, x + w - 2, 3):
            if rng.random() < lit:
                c.set(xx, yy, win if (win2 is None or rng.random() < 0.8) else win2)
                if rng.random() < 0.4:
                    c.set(xx, yy + 1, win)


# --------------------------------------------------------------------------
# Scenes
# --------------------------------------------------------------------------
def scene_city():
    """Intro: golden-age night city with striped sunset sun."""
    rng = random.Random(7)
    c = Canvas(320, 180)
    sky(c, ["sky0", "sky1", "sky2", "sky3"], 0, 150)
    stars(c, rng, 70, 80)
    # Striped retro sun
    sx, sy, r = 160, 112, 38
    for y in range(sy - r, sy + 1):
        for x in range(sx - r, sx + r + 1):
            if (x - sx) ** 2 + (y - sy) ** 2 <= r * r:
                band = (sy - y)
                gap = band < 26 and band % 6 in (0, 1) and band > 2
                if not gap:
                    c.set(x, y, "sun0" if band > 24 else "sun1" if band > 12 else "sun2")
    # Far skyline
    for x, w, top in [(0, 22, 104), (20, 16, 96), (36, 26, 110), (60, 14, 90), (72, 30, 100),
                      (100, 20, 112), (206, 22, 106), (226, 14, 92), (238, 28, 102),
                      (264, 18, 94), (280, 22, 108), (300, 20, 98)]:
        building(c, x, w, top, "far", "farwin", rng=rng, lit=0.18)
    # Broadcast tower (Toronto nod)
    c.rect(246, 40, 2, 70, "far")
    c.rect(243, 62, 8, 5, "far")
    c.rect(244, 60, 6, 2, "farwin")
    c.set(246, 38, "beacon")
    c.set(247, 38, "beacon")
    # Near skyline
    for x, w, top in [(-4, 30, 124), (24, 18, 132), (40, 34, 118), (72, 22, 128),
                      (92, 36, 122), (126, 16, 136), (140, 40, 128), (178, 20, 134),
                      (196, 36, 120), (230, 20, 130), (248, 38, 116), (284, 20, 128), (302, 22, 122)]:
        building(c, x, w, top, "near", "win", "win2", rng=rng, lit=0.33, roof="nearhi")
    # Water tank on a far-left roof; Nico peeks over the parapet beside it
    c.rect(52, 106, 10, 7, "nearhi")
    c.rect(53, 113, 1, 5, "nearhi")
    c.rect(60, 113, 1, 5, "nearhi")
    c.rect(51, 105, 12, 1, "near")
    # Street
    c.rect(0, 168, 320, 12, "ground")
    for x in range(4, 320, 16):
        c.rect(x, 173, 8, 1, "lane")
    front = Canvas(320, 180)
    front.rect(62, 117, 14, 3, "nearhi")  # parapet ledge in front of Nico
    eggs = [(nico_peek(8), 63, 111, "city")]
    write_scene("city", c, eggs, "Night city skyline", front)


def scene_trail():
    """Rundown picker: dusk trail to the farmhouse."""
    rng = random.Random(11)
    c = Canvas(320, 180)
    sky(c, ["sky0", "sky1", "sky2", "sky3", "sky4"], 0, 130)
    stars(c, rng, 26, 40)
    # low sun
    for y in range(92, 118):
        for x in range(220, 262):
            if (x - 241) ** 2 + (y - 112) ** 2 <= 19 * 19:
                c.set(x, y, "sun1" if y < 104 else "sun2")
    # clouds
    for cx, cy, w in [(60, 44, 34), (110, 60, 22), (270, 52, 28)]:
        c.rect(cx, cy, w, 3, "cloud")
        c.rect(cx + 4, cy - 2, w - 10, 2, "cloud")
        c.rect(cx + 2, cy + 3, w - 4, 1, "cloudlo")
    ridge(c, rng, 108, 10, 0.03, "far", "farhi", seed=1)
    ridge(c, rng, 126, 8, 0.045, "mid", "midhi", seed=4)
    for x in range(8, 320, 13):
        pine(c, x + (x * 7) % 5, 128 + (x * 3) % 6, 12 + (x * 5) % 7, "tree", "treehi")
    # Farmhouse on the hill (drawn with role keys)
    hx, hy = 86, 118
    c.rect(hx, hy, 22, 14, "wall")
    c.poly([(hx - 2, hy + 1), (hx + 11, hy - 8), (hx + 24, hy + 1)], "roof")
    c.rect(hx + 3, hy + 4, 3, 3, "win")
    c.rect(hx + 16, hy + 4, 3, 3, "win")
    c.rect(hx + 9, hy + 6, 4, 8, "trim")
    c.rect(hx + 22, hy + 5, 12, 9, "wall2")
    c.poly([(hx + 21, hy + 6), (hx + 28, hy), (hx + 35, hy + 6)], "roof")
    c.rect(hx + 26, hy + 8, 3, 3, "win")
    ridge(c, rng, 146, 5, 0.05, "near", "nearhi", seed=9)
    # Winding trail from the farmhouse down to the foreground
    for y in range(132, 180):
        t = (y - 132) / 48
        cx = 98 + math.sin(t * 3.2) * 40 + t * 70
        w = 2 + t * 26
        for x in range(int(cx - w), int(cx + w)):
            if c.get(x, y) in ("near", "nearhi", "mid", "midhi", "tree", "treehi"):
                edge = x < cx - w + 2 or x > cx + w - 3
                c.set(x, y, "trailhi" if edge else "trail")
    # fence
    for x in range(0, 70, 6):
        c.rect(x, 150 - (x // 20), 1, 6, "fence")
    c.rect(0, 151, 70, 1, "fence")
    # grass tufts
    for _ in range(90):
        x, y = rng.randrange(320), rng.randrange(150, 180)
        if c.get(x, y) == "near":
            c.set(x, y, "nearhi")
            c.set(x, y - 1, "nearhi")
    # fireflies
    for _ in range(18):
        x, y = rng.randrange(320), rng.randrange(128, 172)
        c.set(x, y, "win")
    # bush Nico hides behind (front layer)
    front = Canvas(320, 180)
    front.ellipse(52, 170, 13, 7, "bush")
    front.ellipse(44, 166, 6, 4, "bush")
    front.ellipse(47, 165, 3, 2, "bushhi")
    front.ellipse(58, 167, 3, 2, "bushhi")
    for x in range(40, 66, 3):
        front.set(x, 163 + (x % 2), "bushhi")
    eggs = [(nico_egg(), 52, 148, "trail")]
    write_scene("trail", c, eggs, "Dusk trail to the farmhouse", front)


def scene_harbor():
    """Edition view: Toronto-ish harbour skyline at night over the lake."""
    rng = random.Random(23)
    c = Canvas(320, 180)
    sky(c, ["sky0", "sky1", "sky2"], 0, 132)
    stars(c, rng, 55, 70)
    # moon
    c.ellipse(64, 34, 11, 11, "moon")
    c.ellipse(68, 31, 9, 9, "sky0")
    # far skyline
    for x in range(0, 320, 9):
        top = 104 - int(10 * abs(math.sin(x * 0.07))) - (x * 13) % 9
        building(c, x, 9, top, "far", "farwin", rng=rng, lit=0.15)
    # tower
    tx = 214
    c.rect(tx, 36, 3, 84, "near")
    c.rect(tx - 1, 60, 5, 60, "near")
    c.ellipse(tx + 1.5, 64, 6, 3.4, "near")
    c.rect(tx - 4, 63, 11, 1, "win")
    c.set(tx + 1, 34, "beacon")
    c.set(tx + 1, 35, "beacon")
    # near skyline
    for x, w, top in [(0, 26, 110), (24, 20, 100), (44, 30, 114), (74, 16, 94), (90, 28, 106),
                      (118, 22, 116), (140, 34, 98), (174, 20, 112), (190, 18, 104),
                      (224, 30, 108), (254, 18, 96), (272, 26, 112), (298, 22, 102)]:
        building(c, x, w, top, "near", "win", "win2", rng=rng, lit=0.3, roof="nearhi")
    # waterline
    c.rect(0, 132, 320, 48, "water")
    for y in range(134, 180, 3):
        for x in range(0, 320):
            src = c.get(x, 131 - (y - 132) // 2)
            if src in ("win", "win2", "beacon") and rng.random() < 0.7:
                c.rect(x - 1, y, 3, 1, "reflect")
        for _ in range(8):
            x = rng.randrange(320)
            c.rect(x, y + 1, rng.randrange(3, 9), 1, "waterhi")
    # moon reflection
    for i, y in enumerate(range(136, 176, 4)):
        c.rect(58 + (i % 2) * 2, y, 10 - i % 3 * 2, 1, "moonlo")
    # pier, lower right
    c.rect(222, 158, 98, 3, "pier")
    for x in range(224, 320, 8):
        c.rect(x, 161, 2, 12, "pier")
    front = Canvas(320, 180)
    front.rect(262, 152, 5, 6, "pier")       # bollard
    front.rect(261, 151, 7, 2, "nearhi")
    front.rect(248, 153, 14, 1, "pier")      # coiled rope
    front.rect(250, 155, 11, 1, "pier")
    front.rect(246, 154, 2, 2, "pier")
    eggs = [(nico_egg(), 251, 137, "harbor")]
    write_scene("harbor", c, eggs, "Harbour skyline at night", front)


def scene_alley():
    """Junk dialog strip: back alley with bins; Nico peeks out of one."""
    rng = random.Random(5)
    c = Canvas(200, 44)
    c.rect(0, 0, 200, 44, "far")
    # brick courses with mortar
    for y in range(0, 34, 4):
        c.rect(0, y, 200, 1, "sky0")
        off = 0 if (y // 4) % 2 else 5
        for x in range(off, 200, 10):
            c.rect(x, y + 1, 1, 3, "sky0")
    for _ in range(40):
        x, y = rng.randrange(200), rng.randrange(34)
        if c.get(x, y) == "far":
            c.set(x, y, "farhi")
    # street lamp pool of light
    c.rect(96, 2, 8, 2, "nearhi")
    c.rect(98, 4, 4, 1, "win")
    for y in range(5, 34):
        w = (y - 5) // 2
        for x in range(100 - w, 100 + w):
            edge = x < 100 - w + 2 or x >= 100 + w - 2
            if c.get(x, y) in ("far", "farhi") and (not edge or (x + y) % 2 == 0):
                c.set(x, y, "farhi")
    # ground + curb
    c.rect(0, 34, 200, 10, "ground")
    c.rect(0, 34, 200, 1, "lane")
    c.rect(84, 40, 30, 1, "reflect")
    c.rect(90, 42, 16, 1, "reflect")
    # dumpster
    c.rect(19, 17, 42, 17, "roof")
    c.rect(20, 18, 40, 16, "mid")
    c.rect(17, 14, 46, 4, "roof")
    c.rect(18, 15, 44, 2, "midhi")
    for x in range(24, 58, 6):
        c.rect(x, 20, 2, 12, "cloudlo")
    c.rect(34, 24, 12, 5, "wall2")
    c.rect(35, 25, 10, 3, "trim")
    c.rect(22, 34, 3, 2, "near")
    c.rect(55, 34, 3, 2, "near")
    # bins (lids + ribs)
    for bx in (130, 152, 174):
        c.rect(bx, 20, 16, 14, "wall")
        c.rect(bx - 1, 18, 18, 3, "roof")
        c.rect(bx + 6, 16, 4, 2, "roof")
        for rx in (bx + 3, bx + 8, bx + 12):
            c.rect(rx, 23, 1, 9, "wall2")
    # lifted lid on Nico's bin
    c.clear(152, 18)
    for x in range(151, 170):
        for y in range(15, 21):
            if c.get(x, y) == "roof":
                c.set(x, y, "far")
    c.line(150, 13, 167, 8, "roof")
    c.line(150, 14, 167, 9, "roof")
    eggs = [(nico_peek(8), 153, 12, "alley")]
    write_scene("alley", c, eggs, "Back alley")


def scene_credits_layers():
    """Credits: separate tileable layers for parallax (320 wide)."""
    rng = random.Random(3)
    sky_c = Canvas(320, 180)
    sky(sky_c, ["sky0", "sky1", "sky2", "sky3", "sky4"], 0, 180)
    stars(sky_c, rng, 40, 50)
    sx, sy, r = 160, 92, 24
    for y in range(sy - r, sy + r + 1):
        for x in range(sx - r, sx + r + 1):
            if (x - sx) ** 2 + (y - sy) ** 2 <= r * r:
                band = sy + r - y
                if band > 16 or band % 5 not in (0, 1):
                    sky_c.set(x, y, "sun0" if band > 34 else "sun1" if band > 18 else "sun2")
    write_scene("credits-sky", sky_c, (), "Credits sky")

    def tile(name, fn, h):
        t = Canvas(320, h)
        fn(t)
        write_scene("credits-" + name, t, (), "Credits " + name)

    def far(t):
        for x in range(320):
            y = int(round(20 - 9 * math.sin(x * 2 * math.pi / 160) - 4 * math.sin(x * 2 * math.pi / 64 + 1)))
            for yy in range(y, t.h):
                t.set(x, yy, "far")
            t.set(x, y, "farhi")
            if y < 11:
                t.set(x, y + 1, "snow")
                t.set(x, y + 2, "snow")

    def mid(t):
        for x in range(320):
            y = int(20 - 7 * math.sin(x * 2 * math.pi / 160) - 3 * math.sin(x * 2 * math.pi / 64))
            for yy in range(y, t.h):
                t.set(x, yy, "mid")
            t.set(x, y, "midhi")
        for x in range(6, 320, 16):
            pine(t, x, 24 + (x * 5) % 6, 13 + (x * 3) % 6, "tree", "treehi")

    def ground(t):
        t.rect(0, 0, 320, t.h, "near")
        t.rect(0, 0, 320, 1, "nearhi")
        t.rect(0, 6, 320, 10, "trail")
        t.rect(0, 6, 320, 1, "trailhi")
        t.rect(0, 15, 320, 1, "trailhi")
        r = random.Random(9)
        for _ in range(60):
            x, y = r.randrange(320), r.randrange(7, 15)
            t.set(x, y, "trailhi")
        for x in range(0, 320, 5):
            t.set(x, 2 + x % 3, "nearhi")
            t.set(x + 2, 19 + x % 3, "nearhi")
        for x in range(0, 320, 40):
            t.rect(x + 10, 0, 1, 5, "fence")
        t.rect(0, 1, 320, 1, "fence")

    tile("far", far, 60)
    tile("mid", mid, 50)
    tile("ground", ground, 24)


def main():
    os.makedirs(OUT, exist_ok=True)
    for name, grid in NICO.items():
        write_sprite(name, from_grid(grid), "Nico")
    write_sprite("ball", ball(), "Ball")
    write_sprite("farmhouse", farmhouse(), "Farmhouse")
    write_sprite("medallion", medallion(), "")
    scene_city()
    scene_trail()
    scene_harbor()
    scene_alley()
    scene_credits_layers()
    print("wrote", sorted(os.listdir(OUT)))


if __name__ == "__main__":
    main()
