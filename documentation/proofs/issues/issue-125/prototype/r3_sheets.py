import sys; sys.path.insert(0, "/home/claude/work")
import skia, pathops, numpy as np
from fontTools.ttLib import TTFont
from render import SkPen, label
from proto import fill_corners
from lc_corners import classify
from measure import stem as stem_I
src = open("/home/claude/work/compact.py").read().split("OUT = ")[0]; ns = {}; exec(src, ns); compact = ns["compact"]
I = "inst/"
def raw(path, ch):
    f = TTFont(path); gs = f.getGlyphSet(); g = f.getBestCmap()[ord(ch)]; pen = SkPen(gs); gs[g].draw(pen); p = pen.path; p.setFillType(skia.PathFillType.kWinding); return p
CACHE = {}
def proto(gk, w, ch, floor):
    k = (gk, w, ch, floor)
    if k not in CACHE:
        f = TTFont(f"inst/{gk}-{w}.ttf"); gs = f.getGlyphSet(); g = f.getBestCmap()[ord(ch)]
        p = pathops.Path(); gs[g].draw(p.getPen(glyphSet=gs)); p.simplify(fix_winding=True)
        CACHE[k] = fill_corners(p, stem_I(TTFont(f"inst/{gk}-{w}.ttf")) if gk == "geist" else stem_I(TTFont(f"inst/geist-{w}.ttf")), c=1.6, rmax=53, floor=floor, space=0.9)
    return CACHE[k]
def ink(p):
    s = skia.Surface(1400, 1400); c = s.getCanvas(); c.clear(skia.ColorBLACK); q = skia.Path(p); m = skia.Matrix(); m.setAll(1, 0, 200, 0, -1, 1100, 0, 0, 1); q.transform(m)
    c.drawPath(q, skia.Paint(AntiAlias=True, Color=skia.ColorWHITE)); return s.makeImageSnapshot().toarray()[:, :, 0].astype(float).sum() / 255
CH = "abdhmnpqru"
for style, gk, ok, nk in (("Upright", "geist", "namche", "new2"), ("Italic", "geist_it", "namche_it", "new2_it")):
    w = 100
    inv = []
    for ch in CH: inv += classify(f"inst/{gk}-{w}.ttf", ch, 530)
    seen, items = set(), []
    for r in inv:
        if not (r["where"] == "aussen" and r["theta"] < 50): continue
        k = (r["ch"], round(r["x"] / 40), round(r["y"] / 40))
        if k not in seen: seen.add(k); items.append(r)
    items.sort(key=lambda r: (r["y"] > 265, r["ch"]))
    V = [("bisher", lambda w, ch: raw(f"{I}{ok}-{w}.ttf", ch)), ("neu (0,6)", lambda w, ch: raw(f"{I}{nk}-{w}.ttf", ch)),
         ("Prototyp 0,6", lambda w, ch: proto(gk, w, ch, 0.6)), ("Prototyp 0,4", lambda w, ch: proto(gk, w, ch, 0.4))]
    compact(f"/home/claude/review/img/r3_thin_{style.lower()}.png", items, w, V, f"Thin {style}: Anschlüsse der Kleinbuchstaben", per_row=2)
    # added ink per glyph vs Geist, summed
    tot = {k: 0 for k in ("bisher", "neu", "p06", "p04")}
    for ch in CH:
        g = ink(raw(f"{I}{gk}-{w}.ttf", ch))
        tot["bisher"] += ink(raw(f"{I}{ok}-{w}.ttf", ch)) - g; tot["neu"] += ink(raw(f"{I}{nk}-{w}.ttf", ch)) - g
        tot["p06"] += ink(proto(gk, w, ch, 0.6)) - g; tot["p04"] += ink(proto(gk, w, ch, 0.4)) - g
    print(style, {k: round(v) for k, v in tot.items()}, "glyph ink geist", round(sum(ink(raw(f"{I}{gk}-{w}.ttf", ch)) for ch in CH)))
# hash italic, fixed scale
surf = skia.Surface(1420, 300); c = surf.getCanvas(); c.clear(skia.ColorWHITE)
for j, w in enumerate((400, 700, 900)):
    for k, (t, pre) in enumerate((("bisher", "namche_it"), ("neu", "new2_it"))):
        x0 = 10 + (j * 2 + k) * 235; y0 = 44; size = 225; label(c, f"# Italic {t} · {({400:'Regular',700:'Bold',900:'Black'})[w]}", x0, 30, 14)
        q = raw(f"{I}{pre}-{w}.ttf", "#"); b = q.computeTightBounds(); sc = 0.3; cx = (b.left() + b.right()) / 2; cy = (b.top() + b.bottom()) / 2
        c.save(); c.clipRect(skia.Rect.MakeXYWH(x0, y0, size, size)); c.drawRect(skia.Rect.MakeXYWH(x0, y0, size, size), skia.Paint(Color=0xFFF4F4F0))
        m = skia.Matrix(); m.setAll(sc, 0, x0 + size / 2 - cx * sc, 0, -sc, y0 + size / 2 + cy * sc, 0, 0, 1); q.transform(m); c.drawPath(q, skia.Paint(AntiAlias=True, Color=0xFF111111)); c.restore()
surf.makeImageSnapshot().save("/home/claude/review/img/r3_hash.png")
