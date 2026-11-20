import skia, pathops, uharfbuzz as hb
from fontTools.ttLib import TTFont
from fontTools.pens.basePen import BasePen
from fontTools.pens.transformPen import TransformPen

class SkPen(BasePen):
    def __init__(self, gs=None):
        super().__init__(gs); self.path = skia.Path()
    def _moveTo(self, p): self.path.moveTo(*p)
    def _lineTo(self, p): self.path.lineTo(*p)
    def _curveToOne(self, a, b, c): self.path.cubicTo(*a, *b, *c)
    def _qCurveToOne(self, a, b): self.path.quadTo(*a, *b)
    def _closePath(self): self.path.close()

class Face:
    def __init__(self, path, outlines=None):
        self.path = path
        self.tt = TTFont(path)
        self.gs = self.tt.getGlyphSet()
        self.order = self.tt.getGlyphOrder()
        blob = hb.Blob.from_file_path(path)
        self.hbfont = hb.Font(hb.Face(blob))
        self.upm = self.tt["head"].unitsPerEm
        self.outlines = outlines or {}   # gname -> pathops.Path override

    def glyph_pathops(self, gname):
        if gname in self.outlines: return self.outlines[gname]
        p = pathops.Path(); self.gs[gname].draw(p.getPen(glyphSet=self.gs)); p.simplify(fix_winding=True)
        return p

    def line(self, text, features=None):
        buf = hb.Buffer(); buf.add_str(text); buf.guess_segment_properties()
        hb.shape(self.hbfont, buf, features or {"kern": True})
        x = 0; out = []
        for info, pos in zip(buf.glyph_infos, buf.glyph_positions):
            out.append((self.order[info.codepoint], x + pos.x_offset, pos.y_offset))
            x += pos.x_advance
        return out, x

def to_sk(pp, scale, ox, oy):
    pen = SkPen()
    pp.draw(TransformPen(pen, (scale, 0, 0, -scale, ox, oy)))
    return pen.path

def draw_text(canvas, face, text, size, x, y, color=0xFF000000, glyph_map=None):
    """glyph_map: optional fn(gname) -> pathops.Path to draw instead."""
    s = size / face.upm
    glyphs, adv = face.line(text)
    paint = skia.Paint(AntiAlias=True, Color=color)
    for g, gx, gy in glyphs:
        pp = glyph_map(g) if glyph_map else face.glyph_pathops(g)
        if pp is None: continue
        canvas.drawPath(to_sk(pp, s, x + gx * s, y - gy * s), paint)
    return adv * s

def label(canvas, text, x, y, size=22, color=0xFF666666):
    font = skia.Font(skia.Typeface("DejaVu Sans"), size)
    canvas.drawString(text, x, y, font, skia.Paint(AntiAlias=True, Color=color))
