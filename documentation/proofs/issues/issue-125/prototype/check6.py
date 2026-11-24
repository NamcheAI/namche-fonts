import sys, math; sys.path.insert(0, "/home/claude/work")
import numpy as np
from scipy import ndimage
from fontTools.ttLib import TTFont
import analysis as an
import unicodedata as ud
I = "inst/"
def holes(font, g, minsz=6):
    a, _, _ = an.raster(font, g); lab, k = ndimage.label(~a)
    border = set(np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]])))
    sizes = ndimage.sum(np.ones_like(lab), lab, index=range(1, k + 1))
    return sorted([int(sz) for i, sz in enumerate(sizes, 1) if i not in border and sz > minsz], reverse=True)
def corner_ink(gf, gg, nf, ng, s):
    g, ox, oy = an.raster(gf, gg); n, _, _ = an.raster(nf, ng)
    add = n & ~g; lab, k = ndimage.label(add); cs = an.geist_corners(gf, gg); acc = {}
    if not cs or k == 0: return [], int((g & ~n).sum())
    idx = ndimage.find_objects(lab)
    for i in range(1, k + 1):
        sl = idx[i - 1]; sub = lab[sl] == i; A = int(sub.sum())
        if A < 3: continue
        ys, xs = np.nonzero(sub); cx = xs.mean() + sl[1].start - ox; cy = oy - (ys.mean() + sl[0].start)
        j = min(range(len(cs)), key=lambda q: math.dist(cs[q][0], (cx, cy)))
        if math.dist(cs[j][0], (cx, cy)) > 6 * s + 150: continue
        acc[j] = acc.get(j, 0) + A
    return [(cs[j][0], cs[j][1], A) for j, A in acc.items()], int((g & ~n).sum())
gf0 = TTFont("inst/new4-400.ttf"); CPS = [cp for cp in sorted(gf0.getBestCmap()) if cp > 32 and cp != 0xA0 and ud.category(chr(cp))[0] != "M"]
print("chars checked:", len(CPS))
# A) metrics vs submitted
for st, a, b in (("up", "namche_main-400", "new4-400"), ("it", None, "new4_it-400")):
    if not a: continue
    fa = TTFont(I + a + ".ttf"); fb = TTFont(I + b + ".ttf"); ca = fa.getBestCmap(); cb = fb.getBestCmap()
    diff = [chr(cp) for cp in CPS if cp in ca and fa["hmtx"][ca[cp]][0] != fb["hmtx"][cb[cp]][0]]
    print(f"A) advance widths differing from submitted ({st} 400):", "".join(diff) or "none", "| missing in submitted:", "".join(chr(cp) for cp in CPS if cp not in ca)[:80])
# B) topology across all weights vs Geist
print("B) counter count differs from Geist (all weights), or counter < 80 % of Geist")
GW = {"up": (100, 200, 300, 400, 500, 700, 900), "it": (100, 200, 300, 400, 700, 900)}
for st, gk, nk in (("up", "geist", "new4"), ("it", "geist_it", "new4_it")):
    gfs = {w: TTFont(f"{I}{gk}-{w}.ttf") for w in GW[st]}
    for w in (100, 150, 200, 250, 300, 350, 400, 450, 500, 600, 700, 800, 900):
        nf = TTFont(f"{I}{nk}-{w}.ttf"); ncm = nf.getBestCmap(); gw = min(GW[st], key=lambda x: abs(x - w)); gf = gfs[gw]; gcm = gf.getBestCmap(); fl = []
        for cp in CPS:
            if cp not in gcm: continue
            hg = holes(gf, gcm[cp]); hn = holes(nf, ncm[cp])
            if len(hg) != len(hn): fl.append(f"{chr(cp)}(count {len(hg)}→{len(hn)})")
            elif gw == w and hg:
                r = min(b / a for a, b in zip(hg, hn))
                if r < 0.80: fl.append(f"{chr(cp)}({r:.2f})")
        print(f"  {st} {w} (Geist {gw}):", " ".join(fl) or "ok")
# C) corner ink outliers + removed ink
print("C) corner ink / target (A/A*), top outliers; removed ink vs Geist")
for st, gk, nk in (("up", "geist", "new4"), ("it", "geist_it", "new4_it")):
    for w in (100, 400, 900):
        gf = TTFont(f"{I}{gk}-{w}.ttf"); nf = TTFont(f"{I}{nk}-{w}.ttf"); gcm = gf.getBestCmap(); ncm = nf.getBestCmap(); s = an.stem_of(gf)
        rows = []; removed = []
        for cp in CPS:
            if cp not in gcm: continue
            ch = chr(cp); rmax = 70 if (ch.isupper() or ch.isdigit()) else 53; r90 = min(1.6 * s, rmax); At = (1 - math.pi / 4) * r90 ** 2
            cs, rem = corner_ink(gf, gcm[cp], nf, ncm[cp], s)
            if rem > 60: removed.append(f"{ch}{rem}")
            for (pos, th, A) in cs: rows.append((A / At, ch, round(th), tuple(round(v) for v in pos), A))
        rows.sort(reverse=True); med = np.median([r[0] for r in rows])
        nonlet = [r for r in rows if not r[1].isalnum()]
        print(f"  {st} {w}: median {med:.2f}  top:", " ".join(f"{r[1]}{r[2]}°:{r[0]:.1f}" for r in rows[:14]))
        print(f"        symbols top:", " ".join(f"{r[1]}{r[2]}°:{r[0]:.1f}" for r in nonlet[:14]))
        print(f"        removed ink > 60:", " ".join(removed) or "none")
