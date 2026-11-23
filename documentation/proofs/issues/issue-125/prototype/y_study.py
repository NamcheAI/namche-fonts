import sys; sys.path.insert(0, "/home/claude/work")
import math, pathops, skia
from fontTools.ttLib import TTFont
from fontTools.pens.recordingPen import RecordingPen
from render import SkPen, label
from proto import fill_corners, pp_to_sk
from measure import stem
I = "inst/"
def raw(path):
    f = TTFont(path); gs = f.getGlyphSet(); g = f.getBestCmap()[ord("y")]; pen = SkPen(gs); gs[g].draw(pen); p = pen.path; p.setFillType(skia.PathFillType.kWinding); return p
def geist_y(w):
    f = TTFont(f"{I}geist-{w}.ttf"); gs = f.getGlyphSet(); g = f.getBestCmap()[ord("y")]
    p = pathops.Path(); gs[g].draw(p.getPen(glyphSet=gs)); p.simplify(fix_winding=True); return f, p
def remove_step(p):
    rec = RecordingPen(); p.draw(rec); ops = rec.value
    # find lineTo A (arm end), lineTo B (ledge end, same y), lineTo C (tail)
    for i in range(1, len(ops) - 2):
        if ops[i][0] == ops[i+1][0] == ops[i+2][0] == "lineTo":
            A, B, Cc = ops[i][1][0], ops[i+1][1][0], ops[i+2][1][0]
            P0 = ops[i-1][1][-1]
            if abs(A[1] - B[1]) < 1 and 10 < B[0] - A[0] < 80 and Cc[1] < B[1]:
                # intersect line P0->A with B->Cc
                d1 = (A[0]-P0[0], A[1]-P0[1]); d2 = (Cc[0]-B[0], Cc[1]-B[1])
                den = d1[0]*d2[1] - d1[1]*d2[0]
                t = ((B[0]-P0[0])*d2[1] - (B[1]-P0[1])*d2[0]) / den
                X = (P0[0] + t*d1[0], P0[1] + t*d1[1])
                new = ops[:i] + [("lineTo", (X,))] + ops[i+3:]
                q = pathops.Path(); pen = q.getPen()
                for op, args in new: getattr(pen, op)(*args)
                q.simplify(fix_winding=True); return q
    return p
rows = []
for w, c in ((100, 1.6), (400, 1.2), (900, 1.2)):
    f, p = geist_y(w); s = stem(f)
    exc = fill_corners(p, s, c=c, rmax=53, floor=0.6, space=0.9, override=lambda cn: (1.0, 2.5) if cn["theta"] > 60 and cn["v"][1] < 60 else None)
    nostep = fill_corners(remove_step(p), s, c=c, rmax=53, floor=0.6, space=0.9)
    rows.append((w, [pp_to_sk(p), raw(f"{I}namche-{w}.ttf"), raw(f"{I}new-{w}.ttf"), exc, nostep]))
heads = ["Geist", "bisher", "PR #126", "A: Ecke ausrunden", "B: Stufe entfernen"]
size, cw = 230, 240
surf = skia.Surface(110 + cw * len(heads), 70 + 2 * (size + 30) * 3); cv = surf.getCanvas(); cv.clear(skia.ColorWHITE)
label(cv, "y unten: Stufe zwischen linkem Arm und Unterlänge", 10, 24, 17, 0xFF111111)
for j, t in enumerate(heads): label(cv, t, 110 + j * cw, 52, 13, 0xFF444444)
WN = {100: "Thin c1,6", 400: "Regular", 900: "Black"}
y0 = 64
for w, paths in rows:
    for mode in ("crop", "full"):
        label(cv, WN[w] + (" Detail" if mode == "crop" else ""), 10, y0 + size / 2, 14, 0xFF111111)
        for j, path in enumerate(paths):
            q = skia.Path(path); x0 = 110 + j * cw
            cv.save(); cv.clipRect(skia.Rect.MakeXYWH(x0, y0, size, size)); cv.drawRect(skia.Rect.MakeXYWH(x0, y0, size, size), skia.Paint(Color=0xFFF4F4F0))
            if mode == "crop": sc, cx, cy = 0.9, 240, 0
            else: sc, cx, cy = 0.27, 300, 190
            m = skia.Matrix(); m.setAll(sc, 0, x0 + size / 2 - cx * sc, 0, -sc, y0 + size / 2 + cy * sc, 0, 0, 1)
            q.transform(m); cv.drawPath(q, skia.Paint(AntiAlias=True, Color=0xFF111111)); cv.restore()
        y0 += size + 30
surf.makeImageSnapshot().save("/home/claude/review/img/r2_y.png"); print("ok")
