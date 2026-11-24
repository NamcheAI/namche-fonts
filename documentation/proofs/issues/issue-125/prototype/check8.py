import sys; sys.path.insert(0, "/home/claude/work")
import numpy as np, skia
from fontTools.ttLib import TTFont
from render import SkPen
exec(open("check7.py").read().split("GW = ")[0])
def raw(f, g):
    gs = f.getGlyphSet(); pen = SkPen(gs); gs[g].draw(pen); p = pen.path; p.setFillType(skia.PathFillType.kWinding); return p
def ras(p):
    s = skia.Surface(1600, 1600); c = s.getCanvas(); c.clear(skia.ColorBLACK); q = skia.Path(p); m = skia.Matrix(); m.setAll(1, 0, 300, 0, -1, 1200, 0, 0, 1); q.transform(m)
    c.drawPath(q, skia.Paint(AntiAlias=True, Color=skia.ColorWHITE)); return s.makeImageSnapshot().toarray()[:, :, 0].astype(float) / 255
SMALL = lambda g: any(t in g for t in (".numr", ".dnom", "superior", "uni207", "uni208", "uni00B9", "uni00B2", "uni00B3"))
print("A) glyphs changed vs 6ab84d8 (raster diff > 30), all glyphs incl. alternates")
for st, a, b in (("up", "new4", "new5"), ("it", "new4_it", "new5_it")):
    for w in (100, 400, 700, 900):
        fa = TTFont(f"inst/{a}-{w}.ttf"); fb = TTFont(f"inst/{b}-{w}.ttf"); ch = []
        for g in fb.getGlyphOrder():
            if g == ".notdef" or g not in fa.getGlyphOrder(): continue
            d = np.abs(ras(raw(fa, g)) - ras(raw(fb, g))).sum()
            if d > 30: ch.append(g)
        other = [g for g in ch if not SMALL(g)]
        print(f"  {st} {w}: {len(ch)} changed, small figures {len(ch) - len(other)}, other: {other}")
print("B) small-figure counters vs Geist (min ratio per glyph), and count")
GW = {"up": (100, 200, 300, 400, 500, 700, 900), "it": (100, 200, 300, 400, 700, 900)}
for st, gk, nk in (("up", "geist", "new5"), ("it", "geist_it", "new5_it")):
    gfs = {w: TTFont(f"inst/{gk}-{w}.ttf") for w in GW[st]}
    for w in (100, 150, 200, 300, 400, 500, 600, 700, 800, 900):
        nf = TTFont(f"inst/{nk}-{w}.ttf"); gw = min(GW[st], key=lambda x: abs(x - w)); gf = gfs[gw]; res = []; bad = []
        for g in nf.getGlyphOrder():
            if not SMALL(g): continue
            hg = holes(gf, g); hn = holes(nf, g)
            if len(hg) != len(hn): bad.append(f"{g} count {len(hg)}->{len(hn)}"); continue
            if hg and gw == w: res.append((round(min(y / x for x, y in zip(hg, hn)), 2), g))
        res.sort()
        print(f"  {st} {w}: lowest {res[:3] if res else '-'}  four: {[r for r in res if 'four' in r[1] or r[1] in ('uni2074','uni2084')][:1]}  problems: {bad or 'none'}")
