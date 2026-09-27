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
# Nico palette roles (fixed)
# --------------------------------------------------------------------------
INK = "void"
COAT = ("space-700", "space-900", "space-950")  # hi, base, lo
SHEEN = "indigo-600"
GLINT = "ant-50"
EYE = "burg-900"
MOUTH = "burg-800"
TONGUE = "rasp-200"
TONGUE_LO = "rasp-400"
TOOTH = "ant-50"
PLAID = ("rasp-700", "burg-700", "ant-100")  # base, stripe, cross


def plaid(x, y):
    sx, sy = x % 4 == 0, y % 4 == 0
    if sx and sy:
        return PLAID[2]
    if sx or sy:
        return PLAID[1]
    return PLAID[0]


# --------------------------------------------------------------------------
# Nico hero: smiling, head + chest + front paws, 3/4 facing
# --------------------------------------------------------------------------
def nico_hero():
    c = Canvas(58, 54)
    cx = 29
    # Shoulders / chest (behind head)
    c.ellipse(cx, 44, 19, 11, None, lit=COAT)
    # Front legs + paws
    for lx in (15, 36):
        c.rect(lx, 40, 8, 9, COAT[1])
        c.rect(lx, 40, 2, 8, COAT[0])
        c.rect(lx + 7, 41, 1, 8, COAT[2])
        c.ellipse(lx + 4, 50.5, 5.4, 2.8, None, lit=COAT)
        for tx in (lx + 2, lx + 4, lx + 6):
            c.set(tx, 52, COAT[2])
    # Rose ears: small flaps folding out to the sides
    c.poly([(16, 10), (8, 8), (5, 12), (7, 16), (15, 15)], COAT[1])
    c.poly([(42, 10), (50, 8), (53, 12), (51, 16), (43, 15)], COAT[1])
    c.poly([(14, 11), (9, 10), (8, 13), (13, 14)], "burg-900")
    c.poly([(44, 11), (49, 10), (50, 13), (45, 14)], "burg-900")
    c.line(8, 9, 12, 9, COAT[0])
    # Skull (flat, broad) + big jaw / cheeks
    c.ellipse(cx, 16, 16, 10.5, None, lit=COAT)
    c.ellipse(cx, 26, 19, 11, None, lit=COAT)
    # Muzzle
    c.ellipse(cx, 25.5, 10, 6.5, None, lit=(COAT[0], COAT[0], COAT[1]))
    for x, y in [(cx - 5, 21), (cx - 6, 22), (cx - 6, 23), (cx + 5, 21)]:
        c.set(x, y, "space-600")
    # Forehead groove + wrinkle
    c.line(cx, 9, cx, 17, COAT[2])
    c.line(cx - 4, 18, cx - 2, 19, COAT[2])
    c.line(cx + 4, 18, cx + 2, 19, COAT[2])
    # Skull sheen
    for x, y in [(19, 8), (20, 7), (21, 7), (22, 6), (23, 6), (24, 6)]:
        c.set(x, y, SHEEN)
    c.set(21, 8, "indigo-500")
    c.set(22, 7, "indigo-500")
    # Eyes: warm brown iris, pupil, glint, brow
    for ex in (18, 36):
        c.rect(ex, 15, 5, 5, EYE)
        c.rect(ex + 1, 14, 3, 1, EYE)
        c.rect(ex + 2, 16, 2, 3, INK)
        c.rect(ex + 1, 15, 2, 2, GLINT)
        c.set(ex + 3, 18, "sandy-800")
        c.set(ex + 4, 17, "sandy-800")
        c.set(ex, 15, COAT[1])
        c.set(ex + 4, 15, COAT[1])
    for x, y in [(17, 12), (18, 11), (19, 11), (20, 11), (21, 12), (37, 12), (38, 11), (39, 11), (40, 11), (41, 12)]:
        c.set(x, y, COAT[0])
    # cheek + chest muscle sheen (like the photo's glossy coat)
    for x, y in [(12, 24), (12, 25), (13, 27), (45, 24), (45, 25), (44, 27), (14, 43), (15, 42), (16, 42),
                 (42, 42), (43, 42), (44, 43)]:
        c.set(x, y, SHEEN)
    # Nose
    c.ellipse(cx, 22, 4.6, 2.6, INK)
    c.set(cx - 2, 23, "void")
    c.set(cx + 2, 23, "void")
    c.set(cx - 3, 21, "space-500")
    c.set(cx - 2, 21, "space-600")
    c.set(cx - 2, 20, "space-600")
    c.line(cx, 24, cx, 26, INK)
    # Ear-to-ear grin
    c.ellipse(cx, 31, 10.5, 4.4, MOUTH)
    c.rect(cx - 9, 28, 19, 1, "burg-900")
    c.rect(cx - 10, 27, 21, 1, INK)
    for x, y in [(cx - 11, 27), (cx - 12, 26), (cx - 13, 25), (cx + 11, 27), (cx + 12, 26), (cx + 13, 25)]:
        c.set(x, y, INK)
    # Teeth
    for x in (cx - 8, cx - 7, cx + 7, cx + 8):
        c.set(x, 28, TOOTH)
    c.set(cx - 8, 29, TOOTH)
    c.set(cx + 8, 29, TOOTH)
    # Lower lip
    for x in range(cx - 8, cx + 9):
        c.set(x, 35, INK)
    # Tongue out, hanging past the lip
    c.ellipse(cx + 0.5, 34, 5.2, 5, TONGUE)
    c.ellipse(cx + 0.5, 36.2, 3.6, 2.4, "rasp-200")
    c.line(cx, 31, cx, 36, TONGUE_LO)
    c.set(cx - 3, 31, "ant-200")
    c.set(cx - 2, 31, "ant-200")
    # Bandana (red plaid): neck band + point
    band = Canvas(58, 54)
    band.poly([(12, 37), (46, 37), (44, 41), (14, 41)], "x")
    band.poly([(17, 40), (41, 40), (29, 51)], "x")
    for (x, y) in band.px:
        if not (abs(x - cx) <= 4 and y <= 39):  # tongue sits in front
            c.set(x, y, plaid(x, y))
    for x in range(12, 47):
        if (x, 41) in band.px and not (17 <= x <= 41):
            c.set(x, 41, "burg-800")
    c.outline(INK)
    return c


# --------------------------------------------------------------------------
# Nico side view (run cycle, jump, sit) for credits + eggs
# --------------------------------------------------------------------------
def _leg(c, x0, y0, x1, y1, key, paw=True):
    """2px-thick leg from hip/shoulder (x0,y0) to foot (x1,y1) + a paw nub."""
    c.line(x0, y0, x1, y1, key)
    c.line(x0 + 1, y0, x1 + 1, y1, key)
    if paw:
        c.set(x1 + 2, y1, key)


def _head(c, hx, hy, open_mouth=False, tongue=True):
    base = COAT
    c.ellipse(hx, hy + 1, 5.5, 5, None, lit=base)
    c.ellipse(hx + 4.5, hy + 3, 3.6, 2.8, None, lit=(base[0], base[0], base[1]))  # broad muzzle
    c.poly([(hx - 4, hy - 2), (hx - 2, hy - 5), (hx + 1, hy - 3)], base[1])        # rose ear
    c.set(hx - 2, hy - 3, "burg-900")
    c.set(hx + 1, hy, EYE)
    c.set(hx + 2, hy, GLINT)
    c.set(hx + 8, hy + 2, INK)
    c.set(hx + 7, hy + 2, INK)
    if open_mouth:
        c.rect(hx + 3, hy + 4, 5, 2, MOUTH)
        c.set(hx + 7, hy + 4, TOOTH)
    else:
        c.line(hx + 3, hy + 5, hx + 7, hy + 5, MOUTH)
    c.set(hx + 2, hy + 4, INK)
    if tongue:
        c.set(hx + 3, hy + 6, TONGUE)
        c.set(hx + 4, hy + 6, TONGUE)
        c.set(hx + 4, hy + 7, TONGUE_LO)
    # plaid bandana at the neck
    for (x, y) in [(hx - 3, hy + 5), (hx - 2, hy + 5), (hx - 1, hy + 6), (hx, hy + 6),
                   (hx - 3, hy + 6), (hx - 2, hy + 6), (hx - 2, hy + 7), (hx - 1, hy + 7), (hx - 1, hy + 8)]:
        c.set(x, y, plaid(x, y) if (x + y) % 3 else "burg-700")


def _rim(c, key=SHEEN, skip=(INK, GLINT, EYE, MOUTH, TONGUE, TONGUE_LO, TOOTH) + PLAID + ("burg-900",)):
    """1px top rim light so the black coat reads against dark scenery."""
    for (x, y), k in list(c.px.items()):
        if k in skip:
            continue
        if (x, y - 1) not in c.px:
            c.set(x, y, key)


def nico_side(frame="run0"):
    """Facing right. frames: run0..run3, jump, sit."""
    c = Canvas(36, 26)
    B = COAT
    if frame == "sit":
        c.ellipse(12, 18, 7, 5.5, None, lit=B)          # haunch
        c.ellipse(19, 13, 5, 7, None, lit=B)            # upright chest
        c.poly([(9, 13), (18, 7), (22, 12), (12, 16)], B[1])  # back line
        _leg(c, 19, 17, 19, 23, B[1])
        _leg(c, 22, 17, 22, 23, B[0])
        c.ellipse(11, 23, 5, 1.6, None, lit=B)          # hind foot
        c.line(5, 22, 2, 20, B[1])                      # tail
        c.set(2, 19, B[1])
        _head(c, 22, 4)
    elif frame == "jump":
        c.ellipse(11, 13, 7, 4.2, None, lit=B)          # rear
        c.ellipse(19, 10, 7, 4.8, None, lit=B)          # chest, raised
        _leg(c, 22, 12, 28, 8, B[1])                    # front legs reaching
        _leg(c, 20, 13, 26, 11, B[0])
        _leg(c, 8, 15, 2, 20, B[1])                     # hind legs pushing off
        _leg(c, 11, 16, 6, 21, B[0])
        c.line(4, 11, 1, 8, B[1])                       # tail up
        _head(c, 26, 3, open_mouth=True, tongue=False)
    else:
        i = int(frame[-1])
        bob = (0, -1, 0, 1)[i]
        c.ellipse(12, 12 + bob, 8, 4.6, None, lit=B)    # barrel
        c.ellipse(20, 11 + bob, 6, 5.4, None, lit=B)    # deep chest
        fronts = [((21, 15), (25, 21)), ((21, 15), (22, 22)), ((21, 15), (18, 21)), ((21, 15), (23, 22))]
        backs = [((9, 15), (4, 21)), ((9, 15), (8, 22)), ((9, 15), (12, 21)), ((9, 15), (6, 22))]
        f2 = fronts[(i + 2) % 4]
        b2 = backs[(i + 2) % 4]
        _leg(c, f2[0][0] - 2, f2[0][1] + bob, f2[1][0] - 2, f2[1][1], B[2])   # far legs, darker
        _leg(c, b2[0][0] + 2, b2[0][1] + bob, b2[1][0] + 2, b2[1][1], B[2])
        (fx0, fy0), (fx1, fy1) = fronts[i]
        (bx0, by0), (bx1, by1) = backs[i]
        _leg(c, fx0, fy0 + bob, fx1, fy1, B[1])
        _leg(c, bx0, by0 + bob, bx1, by1, B[1])
        c.line(4, 10 + bob, 1, 7 + bob + (i % 2), B[1])  # tail
        _head(c, 25, 5 + bob)
    _rim(c)
    c.outline(INK)
    return c


def nico_mini():
    """Tiny sitting Nico for background easter eggs (15x13)."""
    rows = [
        ".....ooooo.....",
        "oo.oobbbbboo.oo",
        "ohoobbbbbbbooho",
        "obbbbbbbbbbbbbo",
        ".obbwebbbwebbo.",
        ".obbbbnnnbbbbo.",
        "..obmmmmmmmbo..",
        "..oobmmtmmboo..",
        "...oRDRtRDRo...",
        "..obRRRDRRRbo..",
        ".obbbbRRRbbbbo.",
        ".obbbbbobbbbbo.",
        ".ooooo.o.ooooo.",
    ]
    km = {"o": INK, "b": COAT[1], "h": COAT[0], "w": GLINT, "e": "sandy-800", "n": INK,
          "m": MOUTH, "t": TONGUE, "R": PLAID[0], "D": PLAID[2]}
    c = Canvas(15, 13)
    c.from_ascii(rows, km)
    return c


def nico_peek(rows=8):
    """Just Nico's head and paws-up over a ledge."""
    full = nico_mini()
    c = Canvas(full.w, rows)
    for (x, y), k in full.px.items():
        if y < rows:
            c.set(x, y, k)
    return c


# --------------------------------------------------------------------------
# Props
# --------------------------------------------------------------------------
def ball():
    """Nico's red/blue ball (from the reference photo), 10x10."""
    c = Canvas(12, 12)
    c.ellipse(6, 6, 5, 5, None, lit=("rasp-400", "rasp-600", "rasp-700"))
    for y in range(1, 11):
        c.set(3 + (y > 5), y, "indigo-600")
        c.set(8 + (y > 5), y, "indigo-600")
        c.set(4 + (y > 5), y, "indigo-700")
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
    eggs = [(nico_mini(), 52, 155, "trail")]
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
    eggs = [(nico_mini(), 251, 146, "harbor")]
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
    write_sprite("nico-hero", nico_hero(), "Nico")
    write_sprite("nico-mini", nico_mini(), "Nico")
    for f in ("run0", "run1", "run2", "run3", "jump", "sit"):
        write_sprite("nico-" + f, nico_side(f), "Nico")
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
