import sys; sys.path.insert(0, "/home/claude/work")
import numpy as np
from scipy import ndimage
from fontTools.ttLib import TTFont
import analysis as an
I = "inst/"
def holes(font, g, minsz=6):
    a, _, _ = an.raster(font, g); lab, k = ndimage.label(~a)
    border = set(np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]])))
    sizes = ndimage.sum(np.ones_like(lab), lab, index=range(1, k + 1))
    return sorted([int(sz) for i, sz in enumerate(sizes, 1) if i not in border and sz > minsz], reverse=True)
GW = {"up": (100, 200, 300, 400, 500, 700, 900), "it": (100, 200, 300, 400, 700, 900)}
for st, gk, nk in (("up", "geist", "new4"), ("it", "geist_it", "new4_it")):
    nf0 = TTFont(f"{I}{nk}-400.ttf"); cm = set(nf0.getBestCmap().values())
    gf0 = TTFont(f"{I}{gk}-400.ttf"); gnames = set(gf0.getGlyphOrder())
    alts = [g for g in nf0.getGlyphOrder() if g not in cm and g != ".notdef"]
    missing = [g for g in alts if g not in gnames]
    print(st, "alternates:", len(alts), "not in Geist by name:", missing)
    gfs = {w: TTFont(f"{I}{gk}-{w}.ttf") for w in GW[st]}
    for w in (100, 150, 200, 300, 400, 500, 600, 700, 800, 900):
        nf = TTFont(f"{I}{nk}-{w}.ttf"); gw = min(GW[st], key=lambda x: abs(x - w)); gf = gfs[gw]; fl = []
        for g in alts:
            if g not in gnames: continue
            hg = holes(gf, g); hn = holes(nf, g)
            if len(hg) != len(hn): fl.append(f"{g}(count {len(hg)}→{len(hn)})")
            elif gw == w and hg:
                r = min(b / a for a, b in zip(hg, hn))
                if r < 0.80: fl.append(f"{g}({r:.2f})")
        print(f"  {st} {w}:", " ".join(fl) or "ok")
