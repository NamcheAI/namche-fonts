import sys; sys.path.insert(0, "/home/claude/work")
import skia, numpy as np
from fontTools.ttLib import TTFont
from render import SkPen, label
I = "inst/"
LINES = ['!"#%&\'()*,-./:;?@[\\]_{}¡§«¶·»¿', "–—‘’‚“”„•…‹›$+<=>^`|~¢£¥¨©®¯°´¸×÷", "˘˙˚˛˜˝€™−ªº0123456789 ˆˇ",
         "ÆæŒœØøßẞÞþÐðĐđĦħŁłȷı", "ĄąĘęĮįŲųÇçŞşȘșȚțĢģĶķĻļŅņŖŗ", "ŠšŽžČčĎďĽľŤťŘřĚěŇň ŐőŰű"]
def gpath(f, ch):
    cm = f.getBestCmap()
    if ord(ch) not in cm: return None, 0
    gs = f.getGlyphSet(); g = cm[ord(ch)]; pen = SkPen(gs); gs[g].draw(pen); p = pen.path; p.setFillType(skia.PathFillType.kWinding); return p, gs[g].width
def mask(p, m, W, H):
    s = skia.Surface(W, H); c = s.getCanvas(); c.clear(skia.ColorBLACK); q = skia.Path(p); q.transform(m)
    c.drawPath(q, skia.Paint(AntiAlias=True, Color=skia.ColorWHITE)); return s.makeImageSnapshot().toarray()[:, :, 0].astype(float) / 255
def sheet(fname, gk, nk, title, size=74, ws=(100, 400, 900)):
    lh = int(size * 1.55); W = 1900; H = 70 + len(ws) * (len(LINES) * lh + 30)
    img = np.full((H, W, 4), 255, np.uint8)
    y = 70; s = size / 1000; labels = []
    for w in ws:
        gf = TTFont(f"{I}{gk}-{w}.ttf"); nf = TTFont(f"{I}{nk}-{w}.ttf"); labels.append((str(w), y + 30))
        for line in LINES:
            x = 90; base = y + lh * 0.75
            for ch in line:
                if ch == " ": x += 300 * s; continue
                pn, adv = gpath(nf, ch); pg, _ = gpath(gf, ch)
                if pn is None: continue
                m = skia.Matrix(); m.setAll(s, 0, x, 0, -s, base, 0, 0, 1)
                n = mask(pn, m, W, H); g = mask(pg, m, W, H) if pg is not None else n
                ink = n > 0.02
                col = np.zeros((H, W, 3)); col[:] = (17, 17, 17)
                red = (n - g) > 0.35; blue = (g - n) > 0.35
                a = n[..., None]
                img[..., :3] = np.where(ink[..., None], (img[..., :3] * (1 - a) + np.array([17, 17, 17]) * a).astype(np.uint8), img[..., :3])
                img[red] = (224, 64, 42, 255); img[blue] = (40, 110, 230, 255)
                x += adv * s + 6
            y += lh
        y += 30; img[y - 18:y - 16, 20:W - 20, :3] = 221
    sk = skia.Image.fromarray(img, colorType=skia.ColorType.kRGBA_8888_ColorType)
    surf = skia.Surface(W, H); c = surf.getCanvas(); c.drawImage(sk, 0, 0)
    label(c, title, 20, 34, 20, 0xFF111111)
    for t, yy in labels: label(c, t, 20, yy, 18, 0xFF666666)
    surf.makeImageSnapshot().save(fname); print(fname)
OUT = "/home/claude/review/img/"
sheet(OUT + "r6_sonder_up.png", "geist", "new4", "Sonderzeichen aufrecht, 6ab84d8 · rot = Tinte zu Geist dazu · blau = Tinte gegenüber Geist weg")
sheet(OUT + "r6_sonder_it.png", "geist_it", "new4_it", "Sonderzeichen kursiv, 6ab84d8 · rot = Tinte zu Geist dazu · blau = Tinte gegenüber Geist weg")
