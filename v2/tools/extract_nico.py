#!/usr/bin/env python3
"""Extract Nico sprites from the owner's source art (v2/assets/src/*.jpg).

Dev-only helper (needs Pillow: `pip install pillow`). It is NOT a build step:
it writes palette-keyed pixel grids to tools/nico_data.py, which is committed.
pixelart.py (stdlib only) then turns those grids into the SVGs in assets/px/.

Source of truth (owner-approved art; shapes, faces and poses come from here):
  nico-v3-front.jpg  -> hero medallion (head, circle-framed)
  nico-v3-sit.jpg    -> header badge, loadout banner, footer, tab icon, eggs
  nico-v3-leap.jpg   -> leap pose + run cycle frame
  nico-v3-trot.jpg   -> run cycle frame
  nico-v3-bark.jpg   -> run cycle frame
  nico-sprite-sheet.jpg -> sit/bow poses, pose gallery (kept from approved sheet)
  nico-closeup.jpg   -> superseded by nico-v3-front.jpg (kept on disk only)
  nico-title-mockup.jpg  -> title-screen composition reference (not sampled)
  nico-reference-photo.jpg -> likeness check only (not sampled)

Colours are re-mapped into the site palette (PALETTE.md): the coat onto a
charcoal ramp by luminance rank, tongue/mouth/ears/eyes/ball onto the matching
ramps. No bandana: the owner removed the bandana requirement, so the sprites
show Nico's natural neck and chest straight from the source art.

    python3 v2/tools/extract_nico.py
"""
import math
import os
from collections import Counter

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "assets", "src")

# Coat ramps, darkest -> lightest (documented in PALETTE.md).
# Close-up art has warm lilac-grey sheen; the sprite sheet is a neutral black.
COAT_WARM = ["void", "space-950", "space-900", "indigo-900", "space-600", "indigo-600", "indigo-300"]
COAT_COOL = ["void", "space-950", "space-900", "space-700", "space-600", "space-500", "indigo-300"]
COAT = COAT_WARM + [k for k in COAT_COOL if k not in COAT_WARM]
BG = None


def lum(rgb):
    r, g, b = rgb
    return 0.299 * r + 0.587 * g + 0.114 * b


# ---------------------------------------------------------------- classify --
def is_bg_closeup(rgb):
    r, g, b = rgb
    return r > 120 and b > 80 and g < 115 and r - g > 55 and b - g > 20


def is_bg_sheet(rgb):
    r, g, b = rgb
    return lum(rgb) > 180 and max(rgb) - min(rgb) < 40


def is_bg_white(rgb):
    """The v3 sprites ship on clean white backgrounds."""
    r, g, b = rgb
    return r > 225 and g > 225 and b > 225


V3_PITCH = 11.0
V3_QUANTS = (0.26, 0.5, 0.71, 0.86, 0.95, 0.99)  # same as the sheet (neutral black coat)


def v3_sprite(name):
    im = Image.open(os.path.join(SRC, "nico-v3-%s.jpg" % name)).convert("RGB")
    P = V3_PITCH
    g = sample_grid(im, 0, 0, int(im.width // P), int(im.height // P), P,
                    is_bg_white, mode="centre", glints=True)
    return trim(clean(to_keys(g, COAT_COOL, V3_QUANTS)))


def circle_bust(grid, cx, cy, r):
    """Keep a stepped pixel circle (the medallion frame); head + chest only."""
    out = []
    for y, row in enumerate(grid):
        nr = []
        for x, v in enumerate(row):
            if v and (x + 0.5 - cx) ** 2 + (y + 0.5 - cy) ** 2 > r ** 2:
                nr.append(None)
            else:
                nr.append(v)
        out.append(nr)
    return trim(clean(out))


def feature(rgb):
    """Non-coat features -> palette key, or None if it is coat."""
    r, g, b = rgb
    L = lum(rgb)
    mx, mn = max(rgb), min(rgb)
    # ball orange
    if r > 170 and 60 < g < 170 and b < 90 and r - b > 110:
        return "sandy-600" if L > 170 else "sandy-700" if L > 115 else "ember" if L > 85 else "sandy-800"
    # ball blue
    if b > 110 and b - r > 45 and b > g:
        return "indigo-500" if L > 130 else "indigo-600" if L > 85 else "indigo-700"
    # teeth / glints
    if L > 175 and mx - mn < 70:
        if L > 215:
            return "ant-50"
        if r - b > 18:
            return "ant-200"      # cream teeth
        return None               # neutral grey sheen -> coat ramp
    # tongue / gums
    if r > 150 and r - g > 35 and b > g - 4 and L > 105:
        return "rasp-200" if L > 150 else "rasp-400" if L > 115 else "rasp-700"
    # mouth interior (red) vs lips / ear leather (warm brown)
    if r - g > 22 and r - b > 6 and L < 150:
        red = r - g > 55 and r > 120
        if red:
            return "burg-800" if L > 45 else "burg-900"
        if L < 55:
            return "burg-900"
        return "mauve" if L < 115 else "ember"
    return None


# ----------------------------------------------------------------- sample --
def sample_grid(im, x0, y0, cols, rows, pitch, bgfn, mode="centre", glints=False):
    """Sample a (cols x rows) grid starting at (x0,y0) with cell size `pitch`.
    Returns grid of RGB or None (background)."""
    px = im.load()
    out = []
    for ty in range(rows):
        row = []
        for tx in range(cols):
            cx0, cy0 = x0 + tx * pitch, y0 + ty * pitch
            pts = []
            if mode == "centre":
                cx, cy = cx0 + pitch / 2, cy0 + pitch / 2
                for dy in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        pts.append((int(cx + dx * pitch * 0.18), int(cy + dy * pitch * 0.18)))
            else:
                step = max(1, int(pitch / 4))
                for sy in range(int(cy0), int(cy0 + pitch), step):
                    for sx in range(int(cx0), int(cx0 + pitch), step):
                        pts.append((sx, sy))
            vals = [px[x, y] for x, y in pts if 0 <= x < im.width and 0 <= y < im.height]
            bgs = sum(1 for v in vals if bgfn(v))
            if not vals or bgs * 2 >= len(vals):
                row.append(None)
                continue
            fg = [v for v in vals if not bgfn(v)]
            fg.sort(key=lum)
            pick = fg[len(fg) // 2]  # median by luminance
            # catch-lights are single source pixels: keep them if the cell has one
            full = [px[x, y] for y in range(int(cy0), int(cy0 + pitch)) for x in range(int(cx0), int(cx0 + pitch))
                    if 0 <= x < im.width and 0 <= y < im.height]
            if full and glints:
                hi = max(full, key=lum)
                if lum(hi) > 150 and max(hi) - min(hi) < 60 and lum(pick) < 75 and not any(bgfn(v) for v in full):
                    pick = hi
            row.append(pick)
        out.append(row)
    return out


def to_keys(rgbgrid, ramp=COAT_WARM, qs=(0.2, 0.46, 0.7, 0.87, 0.955, 0.99)):
    """RGB grid -> palette keys; coat tones by luminance rank within the sprite."""
    coat_l = sorted(lum(v) for row in rgbgrid for v in row if v and not feature(v))
    if not coat_l:
        coat_l = [0]
    cuts = [coat_l[min(len(coat_l) - 1, int(q * len(coat_l)))] for q in qs]
    out = []
    for row in rgbgrid:
        r = []
        for v in row:
            if v is None:
                r.append(None)
                continue
            f = feature(v)
            if f:
                r.append(f)
                continue
            if lum(v) > 150 and max(v) - min(v) < 60:
                r.append("ant-50")    # catch-light kept by sample_grid
                continue
            L = lum(v)
            k = sum(1 for c in cuts if L > c)
            r.append(ramp[k])
        out.append(r)
    return out


def clean(grid, keep_largest=True):
    """Drop tiny islands, fill pinholes."""
    H, W = len(grid), len(grid[0])
    seen = set()
    comps = []
    for y in range(H):
        for x in range(W):
            if grid[y][x] and (x, y) not in seen:
                stack = [(x, y)]
                seen.add((x, y))
                comp = []
                while stack:
                    a, b = stack.pop()
                    comp.append((a, b))
                    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        u, v = a + dx, b + dy
                        if 0 <= u < W and 0 <= v < H and grid[v][u] and (u, v) not in seen:
                            seen.add((u, v))
                            stack.append((u, v))
                comps.append(comp)
    if not comps:
        return grid
    big = max(len(c) for c in comps)
    for comp in comps:
        if len(comp) < max(4, big * 0.02) or (keep_largest and len(comp) != big and len(comp) < big * 0.25):
            for x, y in comp:
                grid[y][x] = None
    # catch-lights only live inside the body, never on the silhouette edge
    for y in range(H):
        for x in range(W):
            if grid[y][x] == "ant-50":
                near = [(x + dx, y + dy) for dx in range(-2, 3) for dy in range(-2, 3)]
                if any(not (0 <= u < W and 0 <= v < H) or grid[v][u] is None for u, v in near):
                    grid[y][x] = "space-900"
    for y in range(1, H - 1):
        for x in range(1, W - 1):
            if grid[y][x] is None:
                n = [grid[y + dy][x + dx] for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))]
                if all(n):
                    grid[y][x] = Counter(n).most_common(1)[0][0]
    return grid


def outline(grid, key="void"):
    H, W = len(grid), len(grid[0])
    add = []
    for y in range(H):
        for x in range(W):
            if grid[y][x] is None:
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    u, v = x + dx, y + dy
                    if 0 <= u < W and 0 <= v < H and grid[v][u] and grid[v][u] != key:
                        add.append((x, y))
                        break
    for x, y in add:
        grid[y][x] = key
    return grid


def pad(grid, n=1):
    W = len(grid[0])
    g = [[None] * (W + 2 * n) for _ in range(n)]
    for row in grid:
        g.append([None] * n + row + [None] * n)
    g += [[None] * (W + 2 * n) for _ in range(n)]
    return g


def trim(grid):
    rows = [i for i, r in enumerate(grid) if any(r)]
    cols = [j for j in range(len(grid[0])) if any(r[j] for r in grid)]
    return [r[cols[0]:cols[-1] + 1] for r in grid[rows[0]:rows[-1] + 1]]


def flip(grid):
    return [list(reversed(r)) for r in grid]


# --------------------------------------------------------------- bandana --
def plaid(x, y):
    bx = x % 6 in (0, 1)
    by = y % 6 in (0, 1)
    if (x % 6 == 4 or y % 6 == 4) and not (bx or by):
        return "sandy-800"
    if bx and by:
        return "burg-800"
    if bx or by:
        return "burg-700"
    return "rasp-700"


def _poly_cells(pts):
    cells = set()
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
                cells.add((x, y))
    return cells


def bandana(grid, *polys, scale=1):
    """Paint red tartan inside the given polygons, only over coat pixels, so
    the silhouette never grows and the tongue/ball stay in front."""
    cells = set()
    for pts in polys:
        cells |= _poly_cells(pts)
    H, W = len(grid), len(grid[0])
    coat = set(COAT)
    for x, y in cells:
        if 0 <= x < W and 0 <= y < H and grid[y][x] in coat:
            grid[y][x] = plaid(x // scale, y // scale)
    for x, y in cells:
        if not (0 <= x < W and 0 <= y < H) or grid[y][x] in coat or grid[y][x] is None:
            continue
        if grid[y][x] not in ("rasp-700", "burg-700", "burg-800", "sandy-800"):
            continue
        if (x, y - 1) not in cells:
            grid[y][x] = "rasp-600"            # lit top hem
        elif (x, y + 1) not in cells or (x + 1, y) not in cells:
            grid[y][x] = "burg-900"            # shadow hem
    return grid


# ------------------------------------------------------------- downscale --
PRIORITY = ["ant-50", "rasp-200", "rasp-600", "rasp-700", "rasp-400", "sandy-600", "sandy-700",
            "indigo-500", "indigo-600", "burg-700", "burg-800", "sandy-800", "ember"]


def downscale(grid, f):
    H, W = len(grid), len(grid[0])
    out = []
    for ty in range(int(math.ceil(H / f))):
        row = []
        for tx in range(int(math.ceil(W / f))):
            cell = [grid[y][x] for y in range(int(ty * f), min(H, int((ty + 1) * f)))
                    for x in range(int(tx * f), min(W, int((tx + 1) * f)))]
            fg = [k for k in cell if k and k != "void"]
            if len(fg) * 2 < len(cell):
                row.append(None)
                continue
            c = Counter(fg)
            pick = None
            for k in PRIORITY:
                if c[k] * 3 >= len(fg):
                    pick = k
                    break
            row.append(pick or c.most_common(1)[0][0])
        out.append(row)
    return out


# ------------------------------------------------------------------ poses --
SHEET = [  # name: (x0, y0, x1, y1) in sheet pixels, flip
    ("run-a", (15, 55, 300, 290), False),       # gallop (ball below dropped)
    ("run-b", (320, 55, 640, 260), False),      # gallop, ball in mouth
    ("run-c", (650, 55, 940, 275), False),      # gallop
    ("leap", (950, 60, 1275, 260), False),      # full stretch
    ("sit-ball", (120, 315, 445, 670), False),  # sitting, ball in mouth
    ("sit-front-ball", (555, 315, 745, 680), False),
    ("sit-front", (895, 315, 1150, 670), False),
    ("bow-right", (170, 680, 625, 990), False),
    ("bow-left", (680, 680, 1135, 990), False),
]


SHEET_PITCH = 3.3  # one pitch for every pose keeps their relative sizes true to the sheet


def sheet_pose(im, box):
    x0, y0, x1, y1 = box
    pitch = SHEET_PITCH
    width = int(math.ceil((x1 - x0) / pitch))
    rows = int(math.ceil((y1 - y0) / pitch))
    g = sample_grid(im, x0, y0, width, rows, pitch, is_bg_sheet, mode="centre", glints=True)
    g = clean(to_keys(g, COAT_COOL, (0.26, 0.5, 0.71, 0.86, 0.95, 0.99)))
    return trim(g)


def main():
    sheet = Image.open(os.path.join(SRC, "nico-sprite-sheet.jpg")).convert("RGB")
    out = {}

    for name, box, fl in SHEET:
        pg = sheet_pose(sheet, box)
        out[name] = flip(pg) if fl else pg

    v3 = {name: v3_sprite(name) for name in ("sit", "front", "leap", "trot", "bark")}

    final = compose(out, v3)
    with open(os.path.join(HERE, "nico_data.py"), "w") as f:
        f.write("# generated by extract_nico.py from v2/assets/src/*.jpg - do not hand-edit.\n")
        f.write("# Palette-keyed pixel grids (None = transparent) for every Nico asset.\n")
        f.write("SPRITES = {\n")
        for k, g in final.items():
            f.write("    %r: %r,\n" % (k, g))
        f.write("}\n")
    print({k: (len(v[0]), len(v)) for k, v in final.items()})


import copy

# Bandana polygons per source grid (cell coords), placed at each neck by eye.
# Bandana requirement removed by the owner (2026-09-27): the sprites ship
# without it. The bandana() painter below stays for reference only.
BANDANAS = {}


def compose(raw, v3):
    g = {k: copy.deepcopy(v) for k, v in raw.items()}
    for k, polys in BANDANAS.items():
        bandana(g[k], *polys)
    final = {}
    # Hero: the front head, circle-framed like the medallion (head rows only,
    # no full body). Front grid is 60 wide; chin sits near row 52.
    head = circle_bust(v3["front"][:56], 30, 27, 28.5)
    final["nico-hero"] = pad(outline(pad(copy.deepcopy(head))))
    # Icon family from the sitting sprite.
    sit = v3["sit"]
    final["nico-badge"] = pad(outline(pad(downscale(sit, 2.5))))
    final["nico-banner"] = pad(outline(pad(downscale(sit, 2)[:42])))
    final["nico-mini"] = pad(outline(pad(downscale(sit, 5))))
    # Run cycle: lunge -> trot -> full-stretch leap reads as a gallop.
    final["nico-run-a"] = pad(outline(pad(v3["bark"])))
    final["nico-run-b"] = pad(outline(pad(v3["trot"])))
    final["nico-run-c"] = pad(outline(pad(v3["leap"])))
    final["nico-leap"] = pad(outline(pad(v3["leap"])))
    for k in ("sit-ball", "sit-front-ball", "sit-front", "bow-right", "bow-left"):
        final["nico-" + k] = pad(outline(pad(g[k])))
    # hidden eggs: the tiny smiling face from the front sprite (scene scale)
    final["nico-egg"] = pad(outline(pad(trim(downscale(head, 6)))))
    return final


if __name__ == "__main__":
    main()
