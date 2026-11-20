import sys; sys.path.insert(0, "/home/claude/work")
import skia, pathops
from render import Face, label, SkPen
from proto import fill_corners, pp_to_sk
from fontTools.ttLib import TTFont
from fontTools.pens.boundsPen import BoundsPen

RED = 0xFFE0301E
import os
LANG = os.environ.get("PROOF_LANG", "de")
PFX = "en_" if LANG == "en" else ""
LBL = dict(de=dict(cur_sub="jetzt (eingereicht)", prop_long="Vorschlag (c = 1.2): gleiche Tinte je Ecke, Radius folgt dem Stamm", hero_head="Simons Beispiel, gleiche Gewichte",
  cur_ink="jetzt — rot = zugefügte Tinte", prop_ink="Vorschlag (c = 1.2) — rot = zugefügte Tinte", ink_head="Zugefügte Tinte je Innenecke", cur="jetzt", prop="Vorschlag (c = 1.2)",
  latin_head="Wortbilder, alle Gewichte (GF Latin Core)", geist="Geist (ohne)", knob_head="wght {w}: Radius = c × Stammstärke, spitze Ecken mit gleicher Tintenmenge"),
 en=dict(cur_sub="current (submitted)", prop_long="proposal (c = 1.2): equal ink per corner, radius follows stem", hero_head="Simon's example, same weights",
  cur_ink="current — red = added ink", prop_ink="proposal (c = 1.2) — red = added ink", ink_head="Added ink per inner corner", cur="current", prop="proposal (c = 1.2)",
  latin_head="Words, all weights (GF Latin Core)", geist="Geist (no rounding)", knob_head="wght {w}: radius = c × stem, acute corners get equal ink"))[LANG]
def stem_of(face):
    bp = BoundsPen(face.gs); face.gs[face.tt.getBestCmap()[ord("I")]].draw(bp); return bp.bounds[2]-bp.bounds[0]

class Variant:
    def __init__(self, w, kind, branch="namche", c=1.2):
        self.c = c
        self.geist = Face(f"inst/geist-{w}.ttf"); self.kind = kind; self.cache = {}
        self.stem = stem_of(self.geist)
        self.nam = Face(f"inst/{branch}-{w}.ttf") if kind == "current" else None
    def shaper(self): return self.nam if self.kind == "current" else self.geist
    def glyph(self, g):
        if g in self.cache: return self.cache[g]
        if self.kind == "current": p = pp_to_sk(self.nam.glyph_pathops(g))
        elif self.kind == "geist": p = pp_to_sk(self.geist.glyph_pathops(g))
        else:
            cp = {v: k for k, v in self.geist.tt.getBestCmap().items()}.get(g)
            ch = chr(cp) if cp else "a"
            rmax = 70 if (ch.isupper() or ch.isdigit()) else 53
            p = fill_corners(self.geist.glyph_pathops(g), self.stem, c=self.c, rmax=rmax)
        self.cache[g] = p; return p
    def base(self, g):
        # Geist outline for the same character (overlay reference)
        f = self.shaper(); cp = {v: k for k, v in f.tt.getBestCmap().items()}.get(g)
        gname = self.geist.tt.getBestCmap().get(cp, g) if cp else g
        return pp_to_sk(self.geist.glyph_pathops(gname)) if gname in self.geist.gs else None

def draw_line(c, var, text, size, x, y, overlay=False):
    f = var.shaper(); s = size / f.upm
    glyphs, adv = f.line(text)
    black = skia.Paint(AntiAlias=True, Color=0xFF111111); red = skia.Paint(AntiAlias=True, Color=RED)
    for g, gx, gy in glyphs:
        m = skia.Matrix(); m.setAll(s, 0, x + gx*s, 0, -s, y - gy*s, 0, 0, 1)
        p = var.glyph(g)
        if overlay:
            b = var.base(g)
            if b is not None:
                add = skia.Op(p, b, skia.PathOp.kDifference_PathOp)
                b2 = skia.Path(b); b2.transform(m); c.drawPath(b2, black)
                add.transform(m); c.drawPath(add, red); continue
        p2 = skia.Path(p); p2.transform(m); c.drawPath(p2, black)
    return adv * s

def sheet(fname, rows, cols, text, size, rowh, colw, overlay=False, branch="namche", head=None, W=None):
    W = W or 120 + colw*len(cols); H = 110 + rowh*len(rows)
    surf = skia.Surface(W, H); c = surf.getCanvas(); c.clear(skia.ColorWHITE)
    if head: label(c, head, 40, 50, 24, 0xFF111111)
    for j, col in enumerate(cols): label(c, col[1], 120 + j*colw, 95, 22)
    for i, w in enumerate(rows):
        y = 110 + rowh*i + rowh*0.72
        label(c, str(w), 40, y - size*0.35, 22)
        for j, col in enumerate(cols):
            kind = col[0]; cc = col[2] if len(col) > 2 else 1.2
            draw_line(c, Variant(w, kind, branch, cc), text, size, 120 + j*colw, y, overlay)
    surf.makeImageSnapshot().save(fname)

if __name__ == "__main__":
    which = sys.argv[1]
    if which == "hero":
        sheet(PFX+"hero_cyr.png", [100, 200, 300], [("current", LBL["cur_sub"]), ("proposal", LBL["prop_long"])],
              "Абуалӣ", 190, 270, 1050, branch="namche_main", head=LBL["hero_head"])
    if which == "ink":
        sheet("ink_map.png", [100, 300, 400, 700, 900], [("current", LBL["cur_ink"]), ("proposal", "Vorschlag — rot = zugefügte Tinte")],
              "AKVWYkwxy#&", 150, 205, 1150, overlay=True, head="Wie viel Tinte jede Innenecke bekommt")
    if which == "knob":
        sheet("regler_c.png", [100, 200, 300, 400], [("current", "jetzt"), ("proposal", "c = 0.6", 0.6), ("proposal", "c = 0.9", 0.9), ("proposal", "c = 1.2", 1.2)],
              "Абуалӣ Kayak", 110, 150, 900, branch="namche_main", head="Regler: Radius = c × Stammstärke (höchstens 55), spitze Ecken mit gleicher Tintenmenge")
    if which == "inkzoom":
        sheet(PFX+"ink_zoom.png", [100, 400, 900], [("current", LBL["cur_ink"]), ("proposal", LBL["prop_ink"], 1.2)],
              "AKYy&", 260, 330, 1250, overlay=True, head=LBL["ink_head"])
    if which == "latin":
        sheet(PFX+"latin_words.png", [100, 200, 300, 400, 500, 700, 900], [("current", LBL["cur"]), ("proposal", LBL["prop"])],
              "Kayak Wavy Rekx 47", 120, 165, 1250, head=LBL["latin_head"])

def variant_rows(fname, w, variants, text, size, head, branch="namche_main", overlay=False):
    rowh = int(size * 1.45); W = 2000; H = 110 + rowh * len(variants)
    surf = skia.Surface(W, H); c = surf.getCanvas(); c.clear(skia.ColorWHITE)
    label(c, head, 40, 50, 24, 0xFF111111)
    for i, (kind, title, cc) in enumerate(variants):
        y = 110 + rowh*i + size*1.0
        label(c, title, 40, y - size*0.85, 22)
        draw_line(c, Variant(w, kind, branch, cc), text, size, 300, y, overlay)
    surf.makeImageSnapshot().save(fname)

if __name__ == "__main__" and sys.argv[1] == "thin":
    for w in (100, 200):
        variant_rows(f"{PFX}regler_{w}.png", w, [("current", LBL["cur"], 0), ("geist", LBL["geist"], 0), ("proposal", "c = 0.6", 0.6), ("proposal", "c = 0.9", 0.9), ("proposal", "c = 1.2", 1.2)],
                     "Абуалӣ Kayak", 190, LBL["knob_head"].format(w=w))
