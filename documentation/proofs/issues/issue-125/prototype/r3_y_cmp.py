import sys; sys.path.insert(0, "/home/claude/work")
import skia, pathops
from fontTools.ttLib import TTFont
from render import SkPen, label
from proto import fill_corners, pp_to_sk
from measure import stem
src = open("y_study2.py").read().split("rows = []")[0]; ns = {}; exec(src, ns); remove_step = ns["remove_step"]
I = "inst/"
def raw(path):
    f = TTFont(path); gs = f.getGlyphSet(); g = f.getBestCmap()[ord("y")]; pen = SkPen(gs); gs[g].draw(pen); p = pen.path; p.setFillType(skia.PathFillType.kWinding); return p
def preview(gk, w):
    f = TTFont(f"{I}{gk}-{w}.ttf"); gs = f.getGlyphSet(); g = f.getBestCmap()[ord("y")]
    p = pathops.Path(); gs[g].draw(p.getPen(glyphSet=gs)); p.simplify(fix_winding=True)
    q = remove_step(p); ok = q is not p
    return fill_corners(q, stem(TTFont(f"{I}geist-{w}.ttf")), c=1.6, rmax=53, floor=0.6, space=0.9), ok
WN = {100: "Thin", 400: "Regular", 700: "Bold", 900: "Black"}
rows = [("geist", "namche", "new2", w, "Upright") for w in (100, 400, 700, 900)] + [("geist_it", "namche_it", "new2_it", w, "Italic") for w in (400, 700, 900)]
size = 250; cw = size + 12; heads = ["bisher", "neu (7b47095)", "Vorschau B (Runde 2)"]
surf = skia.Surface(130 + cw * 3, 64 + (size + 14) * len(rows)); c = surf.getCanvas(); c.clear(skia.ColorWHITE)
label(c, "y: Übergang Arm in Unterlänge", 10, 24, 17, 0xFF111111)
for j, t in enumerate(heads): label(c, t, 130 + j * cw, 52, 14, 0xFF444444)
for i, (gk, ok_, nk, w, st) in enumerate(rows):
    pv, okk = preview(gk, w); print(st, w, "step removed" if okk else "NO STEP FOUND")
    paths = [raw(f"{I}{ok_}-{w}.ttf"), raw(f"{I}{nk}-{w}.ttf"), pv]
    nb = paths[1].computeTightBounds()
    y0 = 60 + i * (size + 14); label(c, f"{st} {WN[w]}", 10, y0 + size / 2, 15, 0xFF111111)
    # centre on the junction: left arm bottom, around x of arm end, y ~ -10
    f = TTFont(f"{I}{nk}-{w}.ttf"); 
    cx = {100: 205, 400: 205, 700: 210, 900: 215}[w] - (55 if st == "Italic" else 0); cy = {100: 0, 400: -20, 700: -20, 900: -10}[w]
    sc = 0.95
    for j, p in enumerate(paths):
        q = skia.Path(p); x0 = 130 + j * cw
        c.save(); c.clipRect(skia.Rect.MakeXYWH(x0, y0, size, size)); c.drawRect(skia.Rect.MakeXYWH(x0, y0, size, size), skia.Paint(Color=0xFFF4F4F0))
        m = skia.Matrix(); m.setAll(sc, 0, x0 + size / 2 - cx * sc, 0, -sc, y0 + size / 2 + cy * sc, 0, 0, 1); q.transform(m); c.drawPath(q, skia.Paint(AntiAlias=True, Color=0xFF111111)); c.restore()
surf.makeImageSnapshot().save("/home/claude/review/img/r3_y_vorschau.png"); print("ok")
