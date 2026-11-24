import sys; sys.path.insert(0, "/home/claude/work")
import skia, numpy as np
from fontTools.ttLib import TTFont
from render import SkPen, label
src = open("r6_sheets.py").read().split("def sheet(")[0]; ns = {}; exec(src, ns); mask = ns["mask"]
I = "inst/"
LINES = [["R.ss04", "I.ss05", "G.ss06", "a.ss01", "a.ss02", "l.ss03", "lslash.ss03", "zero.ss09", "one.ss09", "i.ss08", "j.ss08", "question.ss08", "exclam.ss08", "questiondown.ss08", "Odieresis.ss08", "adieresis.ss08"],
         ["fi", "fl", "f_f.liga", "t_t.liga", "A_I.dlig", "U_I.dlig", "uni2116", "hyphen_greater.liga", "less_hyphen.liga", "less_hyphen_greater.liga", "parenleft.alt", "braceleft.alt", "bracketleft.alt.white", "guillemotleft.alt", "less.alt"],
         ["zero.tf", "one.tf", "four.tf", "seven.tf", "uni00B9", "uni00B2", "uni00B3", "uni2074", "uni2078", "uni2080", "uni2084", "one.numr", "fraction", "four.dnom", "uni0122.ss06", "Gdotaccent.ss06.ss08"]]
def gp(f, g):
    gs = f.getGlyphSet()
    if g not in gs: return None, 0
    pen = SkPen(gs); gs[g].draw(pen); p = pen.path; p.setFillType(skia.PathFillType.kWinding); return p, gs[g].width
def sheet(fname, gk, nk, title, size=80, ws=(100, 400, 900)):
    lh = int(size * 1.6); W = 1900; H = 70 + len(ws) * (len(LINES) * lh + 30)
    img = np.full((H, W, 4), 255, np.uint8); y = 70; s = size / 1000; labels = []
    for w in ws:
        gf = TTFont(f"{I}{gk}-{w}.ttf"); nf = TTFont(f"{I}{nk}-{w}.ttf"); labels.append((str(w), y + 30))
        for line in LINES:
            x = 90; base = y + lh * 0.72
            for g in line:
                pn, adv = gp(nf, g); pg, _ = gp(gf, g)
                if pn is None: continue
                m = skia.Matrix(); m.setAll(s, 0, x, 0, -s, base, 0, 0, 1)
                n = mask(pn, m, W, H); gg = mask(pg, m, W, H) if pg is not None else n; a = n[..., None]
                img[..., :3] = np.where((n > 0.02)[..., None], (img[..., :3] * (1 - a) + np.array([17, 17, 17]) * a).astype(np.uint8), img[..., :3])
                img[(n - gg) > 0.35] = (224, 64, 42, 255); img[(gg - n) > 0.35] = (40, 110, 230, 255)
                x += adv * s + 14
            y += lh
        y += 30; img[y - 18:y - 16, 20:W - 20, :3] = 221
    surf = skia.Surface(W, H); c = surf.getCanvas(); c.drawImage(skia.Image.fromarray(img, colorType=skia.ColorType.kRGBA_8888_ColorType), 0, 0)
    label(c, title, 20, 34, 20, 0xFF111111)
    for t, yy in labels: label(c, t, 20, yy, 18, 0xFF666666)
    surf.makeImageSnapshot().save(fname); print(fname)
OUT = "/home/claude/review/img/"
sheet(OUT + "r6_alt_up.png", "geist", "new4", "Alternativen, Ligaturen, Ziffernformen aufrecht · rot = dazu · blau = weg")
sheet(OUT + "r6_alt_it.png", "geist_it", "new4_it", "Alternativen, Ligaturen, Ziffernformen kursiv · rot = dazu · blau = weg")
# small 4 close-up
surf = skia.Surface(1500, 640); c = surf.getCanvas(); c.clear(skia.ColorWHITE)
label(c, "Kleine 4 (hochgestellt ⁴, Bruch-Zähler): Punze im Vergleich, Geist / eingereicht / jetzt", 20, 30, 18, 0xFF111111)
for i, w in enumerate((400, 700, 900)):
    for j, (t, k) in enumerate((("Geist", "geist"), ("eingereicht", "namche_main"), ("jetzt", "new4"))):
        f = TTFont(f"{I}{k}-{w}.ttf"); p, _ = gp(f, "uni2074"); b = p.computeTightBounds(); sc = 0.55
        x0 = 20 + (i * 3 + j) * 162; y0 = 70; size = 155
        label(c, f"{t} {w}", x0, 62, 13, 0xFF444444)
        c.save(); c.clipRect(skia.Rect.MakeXYWH(x0, y0, size, 540)); c.drawRect(skia.Rect.MakeXYWH(x0, y0, size, 540), skia.Paint(Color=0xFFF4F4F0))
        m = skia.Matrix(); m.setAll(sc, 0, x0 + size / 2 - (b.left() + b.right()) / 2 * sc, 0, -sc, y0 + 270 + (b.top() + b.bottom()) / 2 * sc, 0, 0, 1); q = skia.Path(p); q.transform(m)
        c.drawPath(q, skia.Paint(AntiAlias=True, Color=0xFF111111)); c.restore()
surf.makeImageSnapshot().save(OUT + "r6_four_small.png"); print("ok")
