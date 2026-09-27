"""Nico, the Story Scout mascot: detailed pixel master + derived sprites.

The master (nico_master) is painted as lit volumes: each body part is an
ellipsoid with a surface normal, lit from the top-left front and quantised
onto the coat ramp with a narrow ordered-dither seam between tones (the
glossy-black-Staffy sheen from the reference photo). Face, mouth, ears and
bandana are then hand-placed on top.

Everything smaller (header badge, footer/tab/egg mini, side poses) is derived
from the same design: same ramp, same features, same plaid.
"""
import math

# Coat ramp, darkest -> brightest (all from PALETTE.md: space + indigo ramps)
COAT_RAMP = ["space-950", "space-900", "space-700", "indigo-800", "indigo-600", "indigo-500"]
INK = "void"
BAYER = [[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]
LIGHT = (-0.45, -0.62, 0.64)  # top-left, towards viewer
_ln = math.sqrt(sum(v * v for v in LIGHT))
LIGHT = tuple(v / _ln for v in LIGHT)


class Body:
    """Height-field sculpt: volumes merge into one surface, then one light
    pass shades it, so tones flow across forms instead of per-blob."""

    def __init__(self, w, h):
        self.w, self.h = w, h
        self.hgt = {}
        self.flat = {}   # (x, y) -> fixed normal (ears, flat planes)

    def ellipsoid(self, cx, cy, rx, ry, z=0.0, depth=1.0, **_):
        for y in range(int(cy - ry - 1), int(cy + ry + 2)):
            for x in range(int(cx - rx - 1), int(cx + rx + 2)):
                dx, dy = (x + 0.5 - cx) / rx, (y + 0.5 - cy) / ry
                d = dx * dx + dy * dy
                if d <= 1.0 and 0 <= x < self.w and 0 <= y < self.h:
                    hz = z + math.sqrt(1.0 - d) * min(rx, ry) * depth
                    if hz >= self.hgt.get((x, y), -1e9):
                        self.hgt[(x, y)] = hz
                        self.flat.pop((x, y), None)

    def poly(self, pts, normal=(0, 0, 1), **_):
        ys = [p[1] for p in pts]
        for y in range(int(min(ys)), int(max(ys)) + 1):
            yc = y + 0.5
            xs = []
            for i in range(len(pts)):
                (x1, y1), (x2, y2) = pts[i], pts[(i + 1) % len(pts)]
                if (y1 <= yc < y2) or (y2 <= yc < y1):
                    xs.append(x1 + (yc - y1) * (x2 - x1) / (y2 - y1))
            xs.sort()
            for a, b in zip(xs[::2], xs[1::2]):
                for x in range(int(math.ceil(a - 0.5)), int(math.floor(b - 0.5)) + 1):
                    if 0 <= x < self.w and 0 <= y < self.h and (x, y) not in self.hgt:
                        self.flat[(x, y)] = normal

    def _smooth(self, passes=2):
        H = dict(self.hgt)
        for _ in range(passes):
            N = {}
            for (x, y), v in H.items():
                acc, n = 0.0, 0
                for dy in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        acc += H.get((x + dx, y + dy), -2.0)
                        n += 1
                N[(x, y)] = acc / n
            H = N
        return H

    def shade(self, canvas, ramp=None, cuts=None, seam=0.03, relief=0.95, occlude=None):
        ramp = ramp or COAT_RAMP
        cuts = cuts or [0.50, 0.70, 0.84, 0.93, 0.98]
        H = self._smooth(1)
        pts = list(H.items()) + [(k, None) for k in self.flat]
        for (x, y), hv in pts:
            if hv is None:
                nx, ny, nz = self.flat[(x, y)]
            else:
                gx = (H.get((x + 1, y), -2.0) - H.get((x - 1, y), -2.0)) / 2
                gy = (H.get((x, y + 1), -2.0) - H.get((x, y - 1), -2.0)) / 2
                nx, ny, nz = -gx * relief, -gy * relief, 1.0
            ln = math.sqrt(nx * nx + ny * ny + nz * nz) or 1
            nx, ny, nz = nx / ln, ny / ln, nz / ln
            i = nx * LIGHT[0] + ny * LIGHT[1] + nz * LIGHT[2]
            if occlude:
                i *= occlude(x, y)
            i = max(0.0, min(1.0, i))
            th = (BAYER[y % 4][x % 4] + 0.5) / 16
            k = 0
            for j, cut in enumerate(cuts):
                if i >= cut + seam * (th - 0.5):
                    k = j + 1
            canvas.set(x, y, ramp[k])
            # cool bounce light on the shadow-side rim
            if nx > 0.72 and nz < 0.62 and k <= 1 and ny > -0.4:
                canvas.set(x, y, "space-700")


def plaid(x, y):
    """Red tartan: raspberry field, burgundy bands, warm pinstripe."""
    bx = x % 9 in (0, 1, 2)
    by = y % 9 in (0, 1, 2)
    if (x % 9 == 6 or y % 9 == 6) and not (bx and by):
        return "sandy-800" if not (bx or by) else "burg-600"
    if bx and by:
        return "burg-800"
    if bx or by:
        return "burg-700"
    return "rasp-700"


# --------------------------------------------------------------------------
# Master: 96 x 96, head + chest + front paws, smiling, tongue out
# --------------------------------------------------------------------------
def nico_master(Canvas):
    W = H = 96
    c = Canvas(W, H)
    b = Body(W, H)
    cx = 48

    # --- volumes (height field; z = how far toward the viewer) ------------
    b.ellipsoid(cx, 84, 38, 22, z=0, depth=0.6)            # chest + shoulders
    b.ellipsoid(cx - 23, 71, 14, 12, z=2, depth=0.8)       # shoulder muscle L
    b.ellipsoid(cx + 23, 71, 14, 12, z=2, depth=0.8)       # shoulder muscle R
    for lx in (28, 68):
        b.ellipsoid(lx, 84, 9, 13, z=6, depth=0.9)         # forearms
        b.ellipsoid(lx, 92, 11, 5, z=10, depth=0.8)        # paws
    b.ellipsoid(cx, 31, 27, 16, z=4, depth=0.9)            # broad, flat skull
    b.ellipsoid(cx - 16, 45, 18, 15, z=6, depth=0.9)       # cheek L (jaw muscle)
    b.ellipsoid(cx + 16, 45, 18, 15, z=6, depth=0.9)       # cheek R
    b.ellipsoid(cx, 26, 12, 9, z=14, depth=0.5)            # forehead dome
    b.ellipsoid(cx, 46, 15, 10, z=17, depth=0.9)           # short, broad muzzle
    # rose ears: small folded flaps on the skull sides, tips turned back/down
    b.poly([(29, 18), (20, 15), (13, 17), (6, 24), (13, 24), (19, 25), (25, 25)], normal=(-0.2, -0.3, 0.9))
    b.poly([(67, 18), (76, 15), (83, 17), (90, 24), (83, 24), (77, 25), (71, 25)], normal=(0.5, -0.1, 0.8))
    def occlude(x, y):
        # studio falloff: the head is the hero; chest sits in the jaw's shadow
        if y < 58:
            return 1.0
        return max(0.72, 1.0 - (y - 58) * 0.011)

    b.shade(c, occlude=occlude)

    # ear fold: inner leather shows where the flap turns over
    for pts in ([(24, 21), (17, 19), (11, 22), (18, 23), (24, 23)],
                [(72, 21), (79, 19), (85, 22), (78, 23), (72, 23)]):
        c.poly(pts, "burg-900")
    for x, y in [(18, 20), (19, 21), (77, 20), (78, 21)]:
        c.set(x, y, "mauve")
    for i in range(0, 12):                                     # lit fold edge
        c.set(19 - i + (i // 2) * 0, 16 + i // 2, "indigo-600" if i < 8 else "indigo-800")
        c.set(77 + i, 16 + i // 2, "space-700" if i < 8 else "space-900")

    # --- forehead: soft centre groove + relaxed wrinkles -------------------
    for y in range(20, 32):
        c.set(cx, y, "space-950")
    for x, y in [(44, 24), (43, 25), (52, 24), (53, 25)]:
        c.set(x, y, "space-950")
    # raised, happy brows: a lit ridge arching over each eye
    for ex in (35, 61):
        for dx in range(-7, 8):
            y = 28 - int(round(2.6 * (1 - (dx / 7.5) ** 2)))
            c.set(ex + dx, y, "indigo-600" if dx <= 0 else "indigo-800")
            if abs(dx) < 6:
                c.set(ex + dx, y - 1, "space-700")

    # --- eyes: round-almond, warm brown, big key glint ---------------------
    for ex, side in ((35, -1), (61, 1)):
        ey = 35
        for y in range(ey - 5, ey + 5):
            for x in range(ex - 7, ex + 8):
                dx, dy = (x + 0.5 - ex) / 6.4, (y + 0.5 - ey) / 4.6
                if dx * dx + dy * dy <= 1:
                    c.set(x, y, INK)
        for y in range(ey - 4, ey + 4):
            for x in range(ex - 5, ex + 6):
                dx, dy = (x + 0.5 - ex) / 5.0, (y + 0.5 - ey) / 3.7
                if dx * dx + dy * dy <= 1:
                    c.set(x, y, "sandy-800" if y > ey - 3 else "burg-800")
        for x in range(ex - 3, ex + 4):
            c.set(x, ey + 2, "ember")
        c.set(ex - 1, ey + 3, "sandy-700")
        c.set(ex + 1, ey + 3, "sandy-700")
        for y in range(ey - 3, ey + 3):
            for x in range(ex - 3, ex + 3):
                if (x + 0.5 - ex) ** 2 + (y + 0.5 - ey + 0.5) ** 2 <= 6.8:
                    c.set(x, y, INK)
        c.rect(ex - 3, ey - 3, 2, 2, "ant-50")                # key glint
        c.set(ex - 1, ey - 3, "ant-200")
        c.set(ex + 2, ey + 1, "ant-100")                      # fill glint
        c.set(ex + 6 * side, ey + 1, "ant-300")               # sclera sliver (outer corner)
        for x in range(ex - 5, ex + 5):                       # lower-lid catch-light
            c.set(x, ey + 5, "space-700")
        c.set(ex - 6, ey + 4, "space-700")

    # --- muzzle definition: stop highlight + cheek creases ----------------
    for y in range(30, 37):
        c.set(cx - 1, y, "space-700")
        c.set(cx + 1, y, "space-900")
    for i in range(10):
        t = i / 9
        xl = int(round(cx - 9 - 6 * t))
        xr = int(round(cx + 9 + 6 * t))
        yy = int(round(40 + 8 * t))
        c.set(xl, yy, "space-950")
        c.set(xr, yy, "space-950")
        c.set(xl + 1, yy, "space-700" if i < 6 else c.get(xl + 1, yy))
    # --- nose leather -------------------------------------------------------
    for y in range(37, 46):
        for x in range(cx - 8, cx + 9):
            dx, dy = (x + 0.5 - cx) / 8.2, (y + 0.5 - 41.5) / 4.4
            if dx * dx + dy * dy <= 1:
                c.set(x, y, INK)
    for x in range(cx - 6, cx + 2):
        c.set(x, 38, "space-700")
    for x in range(cx - 5, cx):
        c.set(x, 39, "space-600")
    c.set(cx - 4, 38, "space-500")
    c.set(cx - 3, 38, "space-500")
    for x, y in [(cx - 6, 42), (cx - 5, 43), (cx - 4, 43), (cx + 4, 43), (cx + 5, 43), (cx + 6, 42)]:
        c.set(x, y, "space-900")
    for y in range(46, 50):
        c.set(cx, y, INK)
    for x, y in [(37, 46), (39, 48), (36, 49), (41, 47), (59, 46), (57, 48), (60, 49), (55, 47)]:
        c.set(x, y, "space-950")
    for x, y in [(38, 45), (40, 46), (42, 45)]:
        c.set(x, y, "indigo-800")

    # --- the grin: wide open, corners pulled up into the cheeks -------------
    mouth = []
    for y in range(44, 70):
        for x in range(20, 77):
            t = (x + 0.5 - cx) / 21.5
            if abs(t) >= 1:
                continue
            top = 49.5 + 2.6 * (1 - t * t) - 2.0 * t ** 4
            bot = 51.0 + 7.5 * (1 - t * t) ** 0.9
            if top <= y + 0.5 <= bot:
                mouth.append((x, y))
    mset = set(mouth)
    for x, y in mouth:
        c.set(x, y, "burg-800")
    for x, y in mouth:
        if (x, y - 3) in mset and (x, y + 2) in mset and abs(x - cx) < 16:
            c.set(x, y, "burg-900")                            # throat depth
    for x, y in mouth:
        if (x, y - 1) not in mset:
            c.set(x, y - 1, INK)
            c.set(x, y, "rasp-400" if abs(x - cx) > 4 else "burg-800")   # upper gum
        if (x, y + 1) not in mset:
            c.set(x, y + 1, INK)
            c.set(x, y + 2, "space-700" if x < cx else "space-900")    # lower-lip catch-light
    for x, y in [(26, 48), (25, 47), (24, 46), (23, 45), (70, 48), (71, 47), (72, 46), (73, 45)]:
        c.set(x, y, INK)                                        # smile lines up the cheeks
    for x, y in [(24, 47), (72, 47), (25, 49), (71, 49)]:
        c.set(x, y, "indigo-800")
    # teeth: a friendly hint of incisors at the corners, no fangs
    for kx in (31, 32, 64, 65):
        c.set(kx, 51, "ant-50")
        c.set(kx, 52, "ant-300")

    # tongue: long and happy, lolling a touch right, over the lower lip
    tongue = []
    for y in range(53, 79):
        for x in range(37, 64):
            dx, dy = (x + 0.5 - 50) / 8.6, (y + 0.5 - 65.5) / 10.5
            if dx * dx + dy * dy <= 1 and y >= 54:
                tongue.append((x, y, dx, dy))
    tset = {(x, y) for x, y, _, _ in tongue}
    for x, y, dx, dy in tongue:
        light = -(dx * 0.6 + dy * 0.35)
        c.set(x, y, "rasp-200" if light > -0.28 else "rasp-400")
        if light > 0.5:
            c.set(x, y, "sandy-200" if (x + y) % 2 else "rasp-200")
    for y in range(57, 75):
        c.set(50 + (y > 68), y, "rasp-400")                    # centre groove
    for x, y, dx, dy in tongue:
        if dx * dx + dy * dy > 0.8 and dy > 0.1:
            c.set(x, y, "rasp-700")                            # underside curl
    c.rect(44, 59, 2, 2, "ant-50")                             # wet highlight
    c.set(46, 60, "ant-200")
    c.set(45, 62, "ant-200")

    # --- bandana: neck band + draped point, red tartan ---------------------
    band = set()
    for x in range(13, 84):
        t = (x + 0.5 - cx) / 35.5
        y0 = int(round(71 + 3.5 * t * t))
        y1 = int(round(78.5 + 2.5 * (1 - t * t)))
        for y in range(y0, y1 + 1):
            band.add((x, y))
    for y in range(77, 96):
        half = (95.5 - y) * 1.02 + 1
        sag = 0.8 * math.sin((95 - y) / 19 * math.pi)
        for x in range(int(cx - half + sag), int(cx + half + sag) + 1):
            band.add((x, y))
    band -= tset
    for x, y in band:
        c.set(x, y, plaid(x, y))
    for x, y in band:
        if (x, y - 1) not in band:
            c.set(x, y, "rasp-600" if x < cx + 12 else "rasp-700")      # lit top hem
            if (x, y + 1) in band and x < cx + 4:
                c.set(x, y + 1, "rasp-600" if plaid(x, y + 1) == "rasp-700" else plaid(x, y + 1))
        elif (x + 1, y) not in band or (x, y + 1) not in band:
            c.set(x, y, "burg-900")                                     # shadow hem
        elif x > cx + 14 and (x * 3 + y) % 4 == 0 and plaid(x, y) == "rasp-700":
            c.set(x, y, "burg-700")                                     # turning away
    for i in range(14):                                                 # drape creases
        for x, y in [(cx - 14 + i, 81 + i), (cx + 5 + i // 2, 80 + i)]:
            if (x, y) in band:
                c.set(x, y, "burg-800")
        for x, y in [(cx - 13 + i, 81 + i), (cx + 6 + i // 2, 80 + i)]:
            if (x, y) in band and plaid(x, y) == "rasp-700":
                c.set(x, y, "rasp-600")

    # --- paws: toe splits + nail glints ------------------------------------
    for lx in (28, 68):
        for tx in (lx - 5, lx - 1, lx + 3):
            for ty in (91, 92, 93, 94):
                c.set(tx, ty, "space-950")
        for tx in (lx - 7, lx - 3, lx + 1, lx + 5):
            c.set(tx, 95, "space-600")

    # --- glossy coat: specular streaks following the muscles ---------------
    streaks = [
        [(26, 22), (28, 21), (30, 20), (32, 19), (34, 18), (36, 18)],          # skull
        [(40, 16), (42, 15), (44, 15), (46, 15)],
        [(16, 38), (16, 40), (17, 42), (17, 44)],                               # cheek L
        [(22, 36), (23, 37), (24, 37)],
        [(14, 64), (16, 63), (18, 62), (20, 61), (22, 61)],                    # shoulder L
        [(20, 76), (21, 78), (21, 80), (22, 82)],                               # forearm L
        [(60, 76), (61, 78), (61, 80)],                                         # forearm R
    ]
    for line in streaks:
        for x, y in line:
            if c.get(x, y) in COAT_RAMP:
                c.set(x, y, "indigo-600")
        x, y = line[0]
        if c.get(x - 1, y + 1) in COAT_RAMP:
            c.set(x - 1, y + 1, "indigo-800")

    c.outline(INK)
    return c


# --------------------------------------------------------------------------
# Derived: header badge (head only, 1:2 downsample with feature priority)
# --------------------------------------------------------------------------
PRIORITY = [
    "ant-50", "ant-200", "rasp-200", "rasp-400", "sandy-800", "ember", "ant-100",
    "rasp-600", "rasp-700", "burg-700", "burg-800", "sandy-400", "burg-900",
]


def downsample(Canvas, src, x0, y0, w, h, f=2):
    out = Canvas(w, h)
    for ty in range(h):
        for tx in range(w):
            cell = [src.get(x0 + tx * f + i, y0 + ty * f + j) for j in range(f) for i in range(f)]
            filled = [k for k in cell if k]
            if len(filled) < (f * f) / 2:
                continue
            pick = None
            for k in PRIORITY:
                if k in filled:
                    pick = k
                    break
            if pick is None:
                pick = max(set(filled), key=filled.count)
            out.set(tx, ty, pick)
    return out


def nico_badge(Canvas, master):
    """Head + neck for the header medallion (42 x 34), 1:2 from the master."""
    c = downsample(Canvas, master, 6, 12, 42, 34, 2)
    # re-crisp the eyes: glint top-left, pupil, warm iris below
    for ex in (35, 61):
        tx, ty = (ex - 6) // 2, (35 - 12) // 2
        c.set(tx - 1, ty - 1, "ant-50")
        c.set(tx, ty, INK)
        c.set(tx, ty + 1, "sandy-800")
    c.outline(INK)
    return c


# --------------------------------------------------------------------------
# Derived: mini (footer, tab icon, hidden eggs) - hand-tuned 17 x 15
# --------------------------------------------------------------------------
MINI_ROWS = [
    "......ooooo......",
    "oooo.oiiIIioo.ooo",
    "obIioiiIIIiiiobso",
    ".ooiiiiiiiiiiiso.",
    "..oiwEiiiiiwEso..",
    "..oieEiiiiieEso..",
    "..osiiinnniiisso.",
    "..oomrrtttrrmoo..",
    "...oomtttttmoo...",
    "..oRRDRtttRDRRo..",
    ".oRRDRRRtRRRDRRo.",
    ".osRRDRRRRRDRRso.",
    ".ossiRRRDRRRisso.",
    ".oiio.oRRRo.oiso.",
    ".oooo..ooo..oooo.",
]
MINI_KEYS = {
    "o": INK, "i": "space-900", "I": "space-700", "s": "space-950", "b": "indigo-800",
    "w": "ant-50", "E": "sandy-800", "e": "burg-800", "n": INK, "m": INK,
    "r": "burg-800", "t": "rasp-200", "R": "rasp-700", "D": "burg-700",
}


def nico_mini(Canvas):
    c = Canvas(17, 15)
    c.from_ascii(MINI_ROWS, MINI_KEYS)
    return c


# --------------------------------------------------------------------------
# Derived: side poses (credits, loadout banner, gallery) - same engine
# --------------------------------------------------------------------------
def _side_head(c, b, hx, hy, open_mouth=False):
    b.ellipsoid(hx, hy + 1, 5.6, 5.2, z=4, depth=1.0)             # skull
    b.ellipsoid(hx - 1, hy + 4, 5, 3.6, z=3, depth=0.9)           # cheek
    b.ellipsoid(hx + 4.8, hy + 3.2, 3.6, 2.9, z=6, depth=0.8)     # short muzzle


def _side_face(c, hx, hy, open_mouth=False):
    # pointed rose ear folding back
    for x, y in [(hx - 1, hy - 4), (hx - 2, hy - 4), (hx - 3, hy - 3), (hx - 2, hy - 3),
                 (hx - 4, hy - 2), (hx - 3, hy - 2), (hx - 5, hy - 1), (hx - 4, hy - 1)]:
        c.set(x, y, "space-900")
    c.set(hx - 3, hy - 2, "burg-900")
    c.set(hx - 4, hy - 1, "burg-900")
    c.set(hx - 1, hy - 5, "space-700")
    c.set(hx - 2, hy - 5, "space-700")
    c.set(hx - 3, hy - 4, "indigo-800")
    # muzzle bridge catch-light
    for x in range(hx + 3, hx + 7):
        c.set(x, hy + 1, "space-700")
    # eye: iris + pupil + glint
    c.set(hx + 1, hy, "sandy-800")
    c.set(hx + 2, hy, INK)
    c.set(hx + 1, hy - 1, "ant-50")
    c.set(hx + 2, hy - 1, INK)
    # brow sheen
    c.set(hx, hy - 2, "indigo-600")
    c.set(hx + 1, hy - 2, "indigo-800")
    # nose
    c.set(hx + 8, hy + 2, INK)
    c.set(hx + 7, hy + 2, INK)
    c.set(hx + 7, hy + 1, "space-600")
    if open_mouth:
        c.rect(hx + 3, hy + 4, 5, 2, "burg-800")
        c.set(hx + 7, hy + 4, "ant-50")
        c.set(hx + 3, hy + 3, INK)
    else:
        for x in range(hx + 3, hx + 8):
            c.set(x, hy + 5, INK)
        c.set(hx + 2, hy + 4, INK)
        c.set(hx + 7, hy + 4, "rasp-400")
        c.set(hx + 3, hy + 6, "rasp-200")
        c.set(hx + 4, hy + 6, "rasp-200")
        c.set(hx + 4, hy + 7, "rasp-400")
    # plaid bandana at the neck
    for (x, y) in [(hx - 4, hy + 5), (hx - 3, hy + 5), (hx - 2, hy + 6), (hx - 1, hy + 6), (hx, hy + 6),
                   (hx - 4, hy + 6), (hx - 3, hy + 6), (hx - 2, hy + 7), (hx - 1, hy + 7), (hx - 1, hy + 8)]:
        c.set(x, y, plaid(x * 3, y * 3))
    c.set(hx - 4, hy + 5, "rasp-600")
    c.set(hx - 3, hy + 5, "rasp-600")


def nico_side(Canvas, frame="run0"):
    """Facing right, 36 x 26. frames: run0..run3, jump, sit."""
    c = Canvas(36, 26)
    b = Body(36, 26)
    legs = []
    if frame == "sit":
        b.ellipsoid(12, 18, 7, 5.5, z=0)                  # haunch
        b.ellipsoid(19, 13, 5, 7, z=2)                    # upright chest
        b.ellipsoid(14, 13, 5, 4, z=1)
        legs = [(19, 17, 19, 23), (22, 17, 22, 23)]
        b.ellipsoid(11, 23, 5, 1.6, z=2)                  # hind foot
        hx, hy, mouth = 22, 4, False
        tail = [(5, 22), (4, 21), (3, 21), (2, 20)]
    elif frame == "jump":
        b.ellipsoid(11, 13, 7, 4.2, z=0)
        b.ellipsoid(19, 10, 7, 4.8, z=2)
        legs = [(22, 12, 28, 8), (20, 13, 26, 11), (8, 15, 2, 20), (11, 16, 6, 21)]
        hx, hy, mouth = 26, 3, True
        tail = [(4, 11), (3, 10), (2, 9), (1, 8)]
    else:
        i = int(frame[-1])
        bob = (0, -1, 0, 1)[i]
        b.ellipsoid(12, 12 + bob, 8, 4.6, z=0)
        b.ellipsoid(20, 11 + bob, 6, 5.4, z=2)
        fronts = [((21, 15), (25, 21)), ((21, 15), (22, 22)), ((21, 15), (18, 21)), ((21, 15), (23, 22))]
        backs = [((9, 15), (4, 21)), ((9, 15), (8, 22)), ((9, 15), (12, 21)), ((9, 15), (6, 22))]
        (fx0, fy0), (fx1, fy1) = fronts[i]
        (bx0, by0), (bx1, by1) = backs[i]
        legs = [(fx0, fy0 + bob, fx1, fy1), (bx0, by0 + bob, bx1, by1)]
        f2, b2 = fronts[(i + 2) % 4], backs[(i + 2) % 4]
        far = [(f2[0][0] - 2, f2[0][1] + bob, f2[1][0] - 2, f2[1][1]),
               (b2[0][0] + 2, b2[0][1] + bob, b2[1][0] + 2, b2[1][1])]
        for x0, y0, x1, y1 in far:
            c.line(x0, y0, x1, y1, "space-950")
            c.line(x0 + 1, y0, x1 + 1, y1, "space-950")
            c.set(x1 + 2, y1, "space-950")
        hx, hy, mouth = 25, 5 + bob, False
        tail = [(4, 10 + bob), (3, 9 + bob), (2, 8 + bob), (1, 7 + bob + (i % 2))]
    _side_head(c, b, hx, hy)
    b.shade(c, relief=0.8, cuts=[0.66, 0.84, 0.94, 0.985, 0.999])
    for x0, y0, x1, y1 in legs:
        c.line(x0, y0, x1, y1, "space-900")
        c.line(x0 + 1, y0, x1 + 1, y1, "space-700" if y1 >= y0 else "space-900")
        c.set(x1 + 2, y1, "space-900")
    for x, y in tail:
        c.set(x, y, "space-900")
    _side_face(c, hx, hy, open_mouth=mouth)
    c.outline(INK)
    return c
