import sys, math; sys.path.insert(0, "/home/claude/work")
import numpy as np, skia
from fontTools.ttLib import TTFont
from render import SkPen
from analysis import holes
src = open("/home/claude/work/textcheck.py").read().split("rows = []")[0]; ns = {}; exec(src, ns); render = ns["render"]
I = "inst/"
def raw(gname, f):
    gs = f.getGlyphSet(); pen = SkPen(gs); gs[gname].draw(pen); p = pen.path; p.setFillType(skia.PathFillType.kWinding); return p
def ras(p):
    s = skia.Surface(1600, 1600); c = s.getCanvas(); c.clear(skia.ColorBLACK); q = skia.Path(p); m = skia.Matrix(); m.setAll(1, 0, 300, 0, -1, 1200, 0, 0, 1); q.transform(m)
    c.drawPath(q, skia.Paint(AntiAlias=True, Color=skia.ColorWHITE)); return s.makeImageSnapshot().toarray()[:, :, 0].astype(float) / 255
def breaks(f, gname):
    """tangent breaks 2-40 deg at explicit on-curve points (glyf, after instancing)"""
    g = f["glyf"][gname]
    if g.isComposite() or g.numberOfContours <= 0: return []
    coords, ends, flags = g.getCoordinates(f["glyf"]); out = []; st = 0
    for e in ends:
        pts = [(coords[i], flags[i] & 1) for i in range(st, e + 1)]; n = len(pts); st = e + 1
        for i, (p, on) in enumerate(pts):
            if not on: continue
            a = pts[i - 1][0]; b = pts[(i + 1) % n][0]
            v1 = (p[0] - a[0], p[1] - a[1]); v2 = (b[0] - p[0], b[1] - p[1])
            if math.hypot(*v1) < 0.5 or math.hypot(*v2) < 0.5: continue
            ang = abs(math.degrees(math.atan2(v1[0] * v2[1] - v1[1] * v2[0], v1[0] * v2[0] + v1[1] * v2[1])))
            if 2 <= ang <= 40: out.append((round(p[0]), round(p[1]), round(ang, 1)))
    return out
print("A) grey 11-16 px VF vs static, VF vs 66120c2")
for st, a, b, stat in (("up", "new3-400", "new4-400", "new4/NamcheShadowSans-Regular.ttf"), ("it", "new3_it-400", "new4_it-400", "new4/NamcheShadowSans-Italic.ttf")):
    print(" ", st, "  ".join(f"{px}px {100*(g[1]/g[2]-1):+.2f}%/{100*(g[1]/g[0]-1):+.2f}%" for px in (11, 12, 14, 16) for g in [[render(p, px, False).mean() for p in (I + a + ".ttf", I + b + ".ttf", stat)]]))
print("B) changed glyphs vs 66120c2 (raster diff > 30)")
for st, a, b in (("up", "new3", "new4"), ("it", "new3_it", "new4_it")):
    for w in (100, 200, 300, 400, 500, 700, 900):
        fa = TTFont(f"{I}{a}-{w}.ttf"); fb = TTFont(f"{I}{b}-{w}.ttf"); ca = fa.getBestCmap(); cb = fb.getBestCmap(); ch = []
        for cp in sorted(ca):
            if cp < 33 or cp not in cb: continue
            d = np.abs(ras(raw(ca[cp], fa)) - ras(raw(cb[cp], fb))).sum()
            if d > 30: ch.append((chr(cp), int(d)))
        print(f"  {st} {w}: {len(ch)}:", " ".join(f"{c}{d}" for c, d in sorted(ch, key=lambda x: -x[1])[:50]))
print("C) tangent breaks 2-40 deg, lowercase a-z + y accents, count per build")
LC = "abcdefghijklmnopqrstuvwxyzýÿ"
for st, a, b in (("up", "new3", "new4"), ("it", "new3_it", "new4_it")):
    for w in (150, 200, 250, 300, 400, 450, 500):
        fa = TTFont(f"{I}{a}-{w}.ttf"); fb = TTFont(f"{I}{b}-{w}.ttf"); ca = fa.getBestCmap(); cb = fb.getBestCmap()
        ra = {ch: breaks(fa, ca[ord(ch)]) for ch in LC}; rb = {ch: breaks(fb, cb[ord(ch)]) for ch in LC}
        na = sum(len(v) for v in ra.values()); nb = sum(len(v) for v in rb.values())
        new = {ch: v for ch, v in rb.items() if len(v) > len(ra[ch])}
        print(f"  {st} {w}: 66120c2 {na}  6ab84d8 {nb}  per glyph now:", " ".join(f"{ch}{len(v)}" for ch, v in rb.items() if v), " | more than before:", {ch: v for ch, v in new.items()})
print("D) counters vs 66120c2: lost or < 95 %")
for st, a, b in (("up", "new3", "new4"), ("it", "new3_it", "new4_it")):
    for w in (100, 400, 900):
        fa = TTFont(f"{I}{a}-{w}.ttf"); fb = TTFont(f"{I}{b}-{w}.ttf"); ca = fa.getBestCmap(); cb = fb.getBestCmap(); fl = []
        for cp in sorted(ca):
            ch = chr(cp)
            if cp < 33 or not ch.isprintable() or cp not in cb: continue
            ho = holes(fa, ca[cp]); hn = holes(fb, cb[cp])
            if not ho: continue
            if len(ho) != len(hn): fl.append((ch, "count")); continue
            r = min(y / x for x, y in zip(ho, hn))
            if r < 0.95: fl.append((ch, round(r, 2)))
        print(f"  {st} {w}:", fl)
