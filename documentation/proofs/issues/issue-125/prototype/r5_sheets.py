import sys; sys.path.insert(0, "/home/claude/work")
import numpy as np, skia
from scipy import ndimage
from fontTools.ttLib import TTFont
from render import SkPen, label
I = "inst/"
def raw(path, ch):
    f = TTFont(path); gs = f.getGlyphSet(); g = f.getBestCmap()[ord(ch)]; pen = SkPen(gs); gs[g].draw(pen); p = pen.path; p.setFillType(skia.PathFillType.kWinding); return p
def ras(p):
    s = skia.Surface(1600, 1600); c = s.getCanvas(); c.clear(skia.ColorBLACK); q = skia.Path(p); m = skia.Matrix(); m.setAll(1, 0, 300, 0, -1, 1200, 0, 0, 1); q.transform(m)
    c.drawPath(q, skia.Paint(AntiAlias=True, Color=skia.ColorWHITE)); return s.makeImageSnapshot().toarray()[:, :, 0].astype(float) / 255
def blobs(pa, pb, maxn=2):
    d = np.abs(ras(pa) - ras(pb)) > 0.15; d = ndimage.binary_dilation(d, iterations=12); lab, n = ndimage.label(d); out = []
    for i in range(1, n + 1):
        ys, xs = np.nonzero(lab == i); w = (np.abs(ras(pa) - ras(pb)) * (lab == i)).sum()
        if w < 4: continue
        out.append((w, xs.mean() - 300, 1200 - ys.mean()))
    return sorted(out, reverse=True)[:maxn]
def sheet(fname, title, jobs, size=210, sc=3.0):
    rows = []
    for st, pre_old, pre_new, ch, w in jobs:
        pa = raw(f"{I}{pre_old}-{w}.ttf", ch); pb = raw(f"{I}{pre_new}-{w}.ttf", ch)
        for wt, cx, cy in blobs(pa, pb): rows.append((f"{ch} {st} {w}", pa, pb, cx, cy))
    cw = size + 10; surf = skia.Surface(150 + 3 * cw, 60 + len(rows) * (size + 10)); c = surf.getCanvas(); c.clear(skia.ColorWHITE)
    label(c, title, 10, 24, 16, 0xFF111111)
    for j, t in enumerate(("66120c2 (vorher)", "6ab84d8 (neu)", "neu, rot = vorher")): label(c, t, 150 + j * cw, 50, 13, 0xFF444444)
    for i, (lab, pa, pb, cx, cy) in enumerate(rows):
        y0 = 58 + i * (size + 10); label(c, lab, 10, y0 + size / 2, 14, 0xFF111111)
        for j in range(3):
            x0 = 150 + j * cw; m = skia.Matrix(); m.setAll(sc, 0, x0 + size / 2 - cx * sc, 0, -sc, y0 + size / 2 + cy * sc, 0, 0, 1)
            c.save(); c.clipRect(skia.Rect.MakeXYWH(x0, y0, size, size)); c.drawRect(skia.Rect.MakeXYWH(x0, y0, size, size), skia.Paint(Color=0xFFF4F4F0))
            q = skia.Path(pa if j == 0 else pb); q.transform(m); c.drawPath(q, skia.Paint(AntiAlias=True, Color=0xFF111111))
            if j == 2:
                o = skia.Path(pa); o.transform(m); c.drawPath(o, skia.Paint(AntiAlias=True, Color=0xFFE0402A, Style=skia.Paint.kStroke_Style, StrokeWidth=1.5))
            c.restore()
    surf.makeImageSnapshot().save(fname); print(fname, len(rows))
OUT = "/home/claude/review/img/"
sheet(OUT + "r5_y.png", "y kursiv: Übergang in den flachen Abschluss (3 Pixel pro Einheit)", [("it", "new3_it", "new4_it", "y", w) for w in (400, 450, 500)], sc=3.0)
sheet(OUT + "r5_up.png", "Aufrecht b u: Anschlüsse 150 bis 300 (3 Pixel pro Einheit)", [("up", "new3", "new4", ch, w) for ch in "bu" for w in (150, 200, 250, 300)])
sheet(OUT + "r5_it.png", "Kursiv b n p: Anschlüsse 150 bis 300 (3 Pixel pro Einheit)", [("it", "new3_it", "new4_it", ch, w) for ch in "bnp" for w in (150, 200, 250, 300)])
sheet(OUT + "r5_a.png", "a aufrecht: ebenfalls geändert (nicht angekündigt)", [("up", "new3", "new4", "a", w) for w in (100, 400, 900)])
