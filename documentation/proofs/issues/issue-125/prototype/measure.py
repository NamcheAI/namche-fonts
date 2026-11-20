"""Measure added ink at inner corners: Namche Shadow Sans minus Geist, per weight."""
import math, json, sys
import pathops
from fontTools.ttLib import TTFont
from fontTools.pens.recordingPen import RecordingPen
from fontTools.pens.areaPen import AreaPen
from fontTools.pens.statisticsPen import StatisticsPen

def glyph_path(font, gname):
    gs = font.getGlyphSet()
    p = pathops.Path()
    gs[gname].draw(p.getPen(glyphSet=gs))
    p.simplify(fix_winding=True)
    return p

def contours_of(path):
    rec = RecordingPen(); path.draw(rec)
    cs, cur = [], []
    for op, args in rec.value:
        if op == "moveTo": cur = [("M", args[0])]
        elif op in ("lineTo",): cur.append(("L", args[0]))
        elif op in ("qCurveTo", "curveTo"): cur.append(("C", list(args)))
        elif op in ("closePath", "endPath"):
            cs.append(cur); cur = []
    return cs

def contour_area(path_contour_rec):
    pen = AreaPen()
    for op, args in path_contour_rec: getattr(pen, op)(*args)
    return pen.value

def corners(path):
    """Concave corners of the ink shape: (vertex, interior white angle in deg)."""
    out = []
    rec = RecordingPen(); path.draw(rec)
    # split recording into contours
    conts, cur = [], []
    for op, args in rec.value:
        cur.append((op, args))
        if op in ("closePath", "endPath"):
            conts.append(cur); cur = []
    total = sum(contour_area(c) for c in conts)
    ink_left = total > 0  # AreaPen: positive for counter-clockwise? sign handled below
    for c in conts:
        # build list of segments as (start, controls..., end)
        pts = []  # sequence of (oncurve, prev_ctrl, next_ctrl)
        segs = []
        start = None; last = None
        for op, args in c:
            if op == "moveTo": start = last = args[0]
            elif op == "lineTo": segs.append([last, args[0]]); last = args[0]
            elif op in ("qCurveTo", "curveTo"): segs.append([last] + list(args)); last = args[-1]
        if last != start: segs.append([last, start])
        n = len(segs)
        for i in range(n):
            a, b = segs[i], segs[(i + 1) % n]
            v = a[-1]
            # incoming tangent
            pin = None
            for q in reversed(a[:-1]):
                if math.dist(q, v) > 1e-6: pin = q; break
            pout = None
            for q in b[1:]:
                if math.dist(q, v) > 1e-6: pout = q; break
            if pin is None or pout is None: continue
            t1 = (v[0]-pin[0], v[1]-pin[1]); t2 = (pout[0]-v[0], pout[1]-v[1])
            l1, l2 = math.hypot(*t1), math.hypot(*t2)
            cr = (t1[0]*t2[1]-t1[1]*t2[0])/(l1*l2); dt = (t1[0]*t2[0]+t1[1]*t2[1])/(l1*l2)
            turn = math.degrees(math.atan2(cr, dt))
            if abs(turn) < 12: continue
            concave = (turn < 0) if ink_left else (turn > 0)
            if concave:
                out.append((v, 180 - abs(turn)))
    return out, ink_left

def f_theta(theta_deg):
    t = math.radians(theta_deg)
    return 1/math.tan(t/2) - (math.pi - t)/2

def stem(font):
    gs = font.getGlyphSet(); from fontTools.pens.boundsPen import BoundsPen
    bp = BoundsPen(gs); gs[font.getBestCmap()[ord("I")]].draw(bp); b = bp.bounds
    return b[2]-b[0]

def measure(weight, glyphs, nkey="namche"):
    nf = TTFont(f"inst/{nkey}-{weight}.ttf"); gf = TTFont(f"inst/geist-{weight}.ttf")
    s = stem(gf)
    rows = []
    gcmap = gf.getBestCmap(); ncmap = nf.getBestCmap()
    for ch in glyphs:
        cp = ord(ch)
        if cp not in ncmap or cp not in gcmap: continue
        npth = glyph_path(nf, ncmap[cp]); gpth = glyph_path(gf, gcmap[cp])
        diff = pathops.op(npth, gpth, pathops.PathOp.DIFFERENCE)
        lost = pathops.op(gpth, npth, pathops.PathOp.DIFFERENCE)
        cs, _ = corners(gpth)
        # diff components
        rec = RecordingPen(); diff.draw(rec)
        comps, cur = [], []
        for op, args in rec.value:
            cur.append((op, args))
            if op in ("closePath", "endPath"): comps.append(cur); cur = []
        assigned = {}
        for comp in comps:
            A = abs(contour_area(comp))
            if A < 2: continue
            sp = StatisticsPen()
            for op, args in comp: getattr(sp, op)(*args)
            c = (sp.meanX, sp.meanY)
            if not cs: continue
            j = min(range(len(cs)), key=lambda k: math.dist(cs[k][0], c))
            if math.dist(cs[j][0], c) > 6*s + 150: continue
            assigned[j] = assigned.get(j, 0) + A
        for j, (v, th) in enumerate(cs):
            A = assigned.get(j, 0.0)
            req = math.sqrt(A / f_theta(th)) if A > 0 and th < 179 else 0.0
            rows.append(dict(ch=ch, x=round(v[0]), y=round(v[1]), theta=round(th, 1), area=round(A, 1),
                             a_rel=round(A / s**2, 3), r_eq=round(req, 1), r_rel=round(req / s, 2)))
        lostA = abs(sum(abs(contour_area(c)) for c in [lost] if False))
    return s, rows

if __name__ == "__main__":
    text = sys.argv[1] if len(sys.argv) > 1 else "AKRVWXYkvwxyMNaebdghmnpqr#$&4"
    res = {}
    for w in (100, 200, 300, 400, 700, 900):
        s, rows = measure(w, text)
        res[w] = dict(stem=s, rows=rows)
    json.dump(res, open("measure.json", "w"), indent=1)
    for w, d in res.items():
        rs = [r for r in d["rows"] if r["area"] > 0]
        print(f"\nwght {w}: stem(l)={d['stem']:.0f}  corners={len(d['rows'])}  rounded={len(rs)}")
