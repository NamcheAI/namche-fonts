import sys; sys.path.insert(0, "/home/claude/work")
import skia, pathops
from fontTools.ttLib import TTFont
from render import SkPen, label
src = open("/home/claude/work/r3_sheets.py").read().split("CH = ")[0]; ns = {}; exec(src, ns)
raw, proto, ink, compact, classify = ns["raw"], ns["proto"], ns["ink"], ns["compact"], ns["classify"]
ysrc = open("/home/claude/work/r3_y_cmp.py").read().split("WN = ")[0]; ys = {}; exec(ysrc, ys); preview = ys["preview"]
I = "inst/"; OUT = "/home/claude/review/img/"
CH = "abdhmnpqru"
for style, gk, ok, nk in (("Upright", "geist", "namche", "new3"), ("Italic", "geist_it", "namche_it", "new3_it")):
    pk = "new2" if style == "Upright" else "new2_it"
    w = 100; inv = []
    for ch in CH: inv += classify(f"inst/{gk}-{w}.ttf", ch, 530)
    seen, items = set(), []
    for r in inv:
        if not (r["where"] == "aussen" and r["theta"] < 50): continue
        k = (r["ch"], round(r["x"] / 40), round(r["y"] / 40))
        if k not in seen: seen.add(k); items.append(r)
    items.sort(key=lambda r: (r["y"] > 265, r["ch"]))
    V = [("bisher", lambda w, ch: raw(f"{I}{ok}-{w}.ttf", ch)), ("7b47095", lambda w, ch: raw(f"{I}{pk}-{w}.ttf", ch)),
         ("66120c2", lambda w, ch: raw(f"{I}{nk}-{w}.ttf", ch)), ("Prototyp 0,4", lambda w, ch: proto(gk, w, ch, 0.4))]
    compact(OUT + f"r4_thin_{style.lower()}.png", items, w, V, f"Thin {style}: Anschlüsse · bisher / 7b47095 / 66120c2 / Prototyp 0,4", per_row=2)
    tot = {"bisher": 0, "7b47095": 0, "66120c2": 0, "p04": 0}
    for ch in CH:
        g = ink(raw(f"{I}{gk}-{w}.ttf", ch))
        tot["bisher"] += ink(raw(f"{I}{ok}-{w}.ttf", ch)) - g; tot["7b47095"] += ink(raw(f"{I}{pk}-{w}.ttf", ch)) - g
        tot["66120c2"] += ink(raw(f"{I}{nk}-{w}.ttf", ch)) - g; tot["p04"] += ink(proto(gk, w, ch, 0.4)) - g
    print(style, {k: round(v) for k, v in tot.items()})
    # intermediate weights, new build only
    ws = (100, 150, 200, 250, 300, 350, 400)
    surf = skia.Surface(110 + 7 * 150, 70 + 6 * 160); c = surf.getCanvas(); c.clear(skia.ColorWHITE)
    label(c, f"66120c2 {style}: Übergang Thin bis Regular (Zwischenschnitte)", 10, 24, 16, 0xFF111111)
    for j, wv in enumerate(ws): label(c, str(wv), 110 + j * 150, 52, 13, 0xFF444444)
    for i, (ch, cx, cy) in enumerate((("d", 470, 30), ("b", 160, 470), ("n", 150, 470), ("u", 440, 30), ("a", 420, 40), ("p", 160, 470))):
        label(c, ch, 20, 70 + i * 160 + 75, 18, 0xFF111111)
        for j, wv in enumerate(ws):
            p = raw(f"{I}{nk}-{wv}.ttf", ch); x0 = 110 + j * 150; y0 = 62 + i * 160; size = 145; sc = 0.9
            ccx = cx - (60 if style == "Italic" and cy > 200 else 0)
            c.save(); c.clipRect(skia.Rect.MakeXYWH(x0, y0, size, size)); c.drawRect(skia.Rect.MakeXYWH(x0, y0, size, size), skia.Paint(Color=0xFFF4F4F0))
            m = skia.Matrix(); m.setAll(sc, 0, x0 + size / 2 - ccx * sc, 0, -sc, y0 + size / 2 + cy * sc, 0, 0, 1); q = skia.Path(p); q.transform(m)
            c.drawPath(q, skia.Paint(AntiAlias=True, Color=0xFF111111)); c.restore()
    surf.makeImageSnapshot().save(OUT + f"r4_thin_steps_{style.lower()}.png")
# y comparison
WN = {300: "Light", 400: "Regular", 500: "Medium", 600: "SemiBold", 700: "Bold", 800: "ExtraBold", 900: "Black"}
rows = [("geist", "namche", "new2", "new3", w, "Upright") for w in (400, 700, 900)] + [("geist_it", "namche_it", "new2_it", "new3_it", w, "Italic") for w in (400, 700, 900)]
size = 230; cw = size + 12; heads = ["bisher", "7b47095", "66120c2 (neu)", "Vorschau B"]
surf = skia.Surface(130 + cw * 4, 64 + (size + 14) * len(rows)); c = surf.getCanvas(); c.clear(skia.ColorWHITE)
label(c, "y: Übergang Arm in Unterlänge", 10, 24, 17, 0xFF111111)
for j, t in enumerate(heads): label(c, t, 130 + j * cw, 52, 14, 0xFF444444)
for i, (gk, ok_, pk, nk, w, st) in enumerate(rows):
    pv, _ = preview(gk, w)
    paths = [raw(f"{I}{ok_}-{w}.ttf", "y"), raw(f"{I}{pk}-{w}.ttf", "y"), raw(f"{I}{nk}-{w}.ttf", "y"), pv]
    y0 = 60 + i * (size + 14); label(c, f"{st} {WN[w]}", 10, y0 + size / 2, 15, 0xFF111111)
    cx = {400: 205, 700: 210, 900: 215}[w] - (55 if st == "Italic" else 0); cy = {400: -20, 700: -20, 900: -10}[w]; sc = 0.95
    for j, p in enumerate(paths):
        q = skia.Path(p); x0 = 130 + j * cw
        c.save(); c.clipRect(skia.Rect.MakeXYWH(x0, y0, size, size)); c.drawRect(skia.Rect.MakeXYWH(x0, y0, size, size), skia.Paint(Color=0xFFF4F4F0))
        m = skia.Matrix(); m.setAll(sc, 0, x0 + size / 2 - cx * sc, 0, -sc, y0 + size / 2 + cy * sc, 0, 0, 1); q.transform(m); c.drawPath(q, skia.Paint(AntiAlias=True, Color=0xFF111111)); c.restore()
surf.makeImageSnapshot().save(OUT + "r4_y.png")
# y all intermediate weights, new build, zoomed
surf = skia.Surface(120 + 7 * 170, 60 + 2 * 180); c = surf.getCanvas(); c.clear(skia.ColorWHITE)
for j, w in enumerate((300, 400, 500, 600, 700, 800, 900)): label(c, WN[w], 120 + j * 170, 30, 13, 0xFF444444)
for i, (pre, st) in enumerate((("new3", "Upright"), ("new3_it", "Italic"))):
    label(c, st, 10, 40 + i * 180 + 85, 15, 0xFF111111)
    for j, w in enumerate((300, 400, 500, 600, 700, 800, 900)):
        p = raw(f"{I}{pre}-{w}.ttf", "y"); x0 = 120 + j * 170; y0 = 40 + i * 180; size = 165; sc = 1.6
        cx = 205 + (w - 400) * 0.02 - (55 if st == "Italic" else 0); cy = -15
        c.save(); c.clipRect(skia.Rect.MakeXYWH(x0, y0, size, size)); c.drawRect(skia.Rect.MakeXYWH(x0, y0, size, size), skia.Paint(Color=0xFFF4F4F0))
        m = skia.Matrix(); m.setAll(sc, 0, x0 + size / 2 - cx * sc, 0, -sc, y0 + size / 2 + cy * sc, 0, 0, 1); q = skia.Path(p); q.transform(m); c.drawPath(q, skia.Paint(AntiAlias=True, Color=0xFF111111)); c.restore()
surf.makeImageSnapshot().save(OUT + "r4_y_steps.png"); print("ok")
