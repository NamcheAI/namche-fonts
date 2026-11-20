import sys; sys.path.insert(0, "/home/claude/work")
import math, json, statistics as st, pathops
from measure import glyph_path, corners, contour_area, f_theta, stem
from fontTools.ttLib import TTFont
from fontTools.pens.recordingPen import RecordingPen
from fontTools.pens.statisticsPen import StatisticsPen
from proto import fill_corners

TEXT = "ABDEFGHKLMNPRTVWXYZabdefghkmnpqrtuvwxyz2467#$&"
def per_corner(gpth, npth, s):
    diff = pathops.op(npth, gpth, pathops.PathOp.DIFFERENCE)
    cs, _ = corners(gpth)
    rec = RecordingPen(); diff.draw(rec); comps, cur = [], []
    for op, a in rec.value:
        cur.append((op, a))
        if op in ("closePath", "endPath"): comps.append(cur); cur = []
    acc = {}
    for comp in comps:
        A = abs(contour_area(comp))
        if A < 2 or not cs or A > 8*s*s + 4000: continue
        sp = StatisticsPen()
        for op, a in comp: getattr(sp, op)(*a)
        j = min(range(len(cs)), key=lambda k: math.dist(cs[k][0], (sp.meanX, sp.meanY)))
        if math.dist(cs[j][0], (sp.meanX, sp.meanY)) > 6*s + 150: continue
        acc[j] = acc.get(j, 0) + A
    return [(cs[j][1], A) for j, A in acc.items()]

if __name__ != '__main__': raise SystemExit
res = {}
for w in (100, 200, 300, 400, 700, 900):
    gf = TTFont(f"inst/geist-{w}.ttf"); nf = TTFont(f"inst/namche-{w}.ttf")
    s = stem(gf); gc = gf.getBestCmap(); nc = nf.getBestCmap()
    cur, pro = [], []
    for ch in TEXT:
        g = glyph_path(gf, gc[ord(ch)])
        cur += [(th, A, ch) for th, A in per_corner(g, glyph_path(nf, nc[ord(ch)]), s)]
        rmax = 70 if (ch.isupper() or ch.isdigit()) else 53
        pro += [(th, A, ch) for th, A in per_corner(g, fill_corners(g, s, c=1.2, rmax=rmax, as_skia=False), s)]
    def summ(rows):
        rows = [r for r in rows if r[0] <= 100]
        xs = sorted(A / s**2 for _, A, _c in rows)
        acute = [A / s**2 for th, A, ch in rows if th < 60 and ch.islower()]; right = [A / s**2 for th, A, ch in rows if 80 <= th <= 100 and ch.islower()]
        return dict(n=len(xs), median=round(st.median(xs), 3), p10=round(xs[len(xs)//10], 3), p90=round(xs[9*len(xs)//10], 3),
                    p95=round(xs[95*len(xs)//100], 3),
                    acute_vs_right=round(st.median(acute) / st.median(right), 2) if acute and right else None,
                    max=round(xs[-1], 2))
    res[w] = dict(stem=s, jetzt=summ(cur), vorschlag=summ(pro))
    print(w, s, "jetzt", res[w]["jetzt"], "\n          vorschlag", res[w]["vorschlag"], flush=True)
json.dump(res, open("evaluate.json", "w"), indent=1)
