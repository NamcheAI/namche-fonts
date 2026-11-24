"""Exercise the reviewed cubic and quadratic contacts in actual release fonts."""
import math
import unittest
from pathlib import Path

from fontTools.pens.recordingPen import RecordingPointPen
from fontTools.ttLib import TTFont
from glyphsLib import GSFont
from shapely.geometry import MultiLineString

from scripts.build_sans_equal_ink import contours
from scripts.check_equal_ink import WEIGHT_STYLES, _FlattenPen
from scripts.equal_ink_corners import _NodeGlyph
from scripts.lowercase_fillet_tangents import _match, source_contacts

ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / 'fonts/NamcheShadowSans'


def adjacent(point, direction, anchor):
    dx, dy = point[0] - anchor[0], point[1] - anchor[1]
    return math.degrees(math.atan2(abs(dx*direction[1]-dy*direction[0]),
                                   (dx*direction[0]+dy*direction[1])))


class LowercaseFilletExports(unittest.TestCase):
    def test_a_static_boundaries_stay_within_two_grid_units_of_the_design(self):
        # Static cu2qu occasionally fits an entire bowl with a single control.
        # Moving the end of such a long span can visibly distort otherwise
        # smooth geometry, particularly at Regular through SemiBold.
        for slope, suffix in enumerate(('', '-Italic')):
            design = GSFont(ROOT / f'sources/NamcheShadowSans{suffix}.glyphspackage')
            for master in design.masters:
                weight = int(master.axes[0])
                if weight not in WEIGHT_STYLES:
                    continue
                pen = _FlattenPen(.01)
                _NodeGlyph(contours(design.glyphs['a'].layers[master.id])).draw(pen)
                original = MultiLineString(pen.contours)
                style = WEIGHT_STYLES[weight][slope]
                with self.subTest(style=style), TTFont(RELEASE / 'ttf' / f'NamcheShadowSans-{style}.ttf') as font:
                    pen = _FlattenPen(.01)
                    font.getGlyphSet()['a'].draw(pen)
                    self.assertLess(original.hausdorff_distance(MultiLineString(pen.contours)), 2.)

    def test_cff_keeps_baked_tangents_through_fixed_point_serialization(self):
        for slope in ('', '-Italic'):
            source = source_contacts(ROOT / f'sources/NamcheShadowSans{slope}.glyphspackage')
            for weight, style in ((200, 'ExtraLight'), (300, 'Light')):
                style += 'Italic' if slope else ''
                with TTFont(RELEASE / 'otf' / f'NamcheShadowSans-{style}.otf') as font:
                    glyphs = font.getGlyphSet()
                    for name, anchors in source[weight].items():
                        with self.subTest(style=style, glyph=name):
                            pen = RecordingPointPen()
                            glyphs[name].drawPoints(pen)
                            contours = []
                            for op, args, _ in pen.value:
                                if op == 'beginPath':
                                    contour = []
                                elif op == 'addPoint':
                                    contour.append(args[:2])
                                elif op == 'endPath':
                                    contours.append(contour)
                            explicit = [((ci, i), p) for ci, c in enumerate(contours)
                                        for i, (p, kind) in enumerate(c) if kind]
                            for point, _, curved in anchors:
                                if not curved:
                                    continue
                                ci, i = _match(explicit, point, name)
                                c = contours[ci]
                                p, _ = c[i-1]
                                q, _ = c[i]
                                r, _ = c[(i+1) % len(c)]
                                self.assertLess(adjacent(r, (q[0]-p[0], q[1]-p[1]), q), .001)

    def test_variable_and_static_curve_contacts_use_implied_knots(self):
        for slope in ('', '-Italic'):
            source = source_contacts(ROOT / f'sources/NamcheShadowSans{slope}.glyphspackage')
            for weight, path in (
                (400, RELEASE / 'variable' / f'NamcheShadowSans{slope}[wght].ttf'),
                (200, RELEASE / 'ttf' / f"NamcheShadowSans-ExtraLight{'Italic' if slope else ''}.ttf"),
                (300, RELEASE / 'ttf' / f"NamcheShadowSans-Light{'Italic' if slope else ''}.ttf"),
            ):
                with TTFont(path) as font:
                    for name, anchors in source[weight].items():
                        with self.subTest(font=path.name, glyph=name):
                            glyph = font['glyf'][name]
                            if glyph.isComposite():
                                # Static accented forms reference the already-checked base.
                                continue
                            coords, ends, flags = glyph.getCoordinates(font['glyf'])
                            oncurves = [p for i, p in enumerate(coords) if flags[i] & 1]
                            implied = []
                            start = 0
                            for end in ends:
                                for j in range(start, end+1):
                                    k = j+1 if j < end else start
                                    if not (flags[j] & 1 or flags[k] & 1):
                                        implied.append(tuple((a+b)*.5 for a, b in zip(coords[j], coords[k])))
                                start = end+1
                            for p, _, curved in anchors:
                                if curved:
                                    self.assertTrue(all(math.dist(p, q) > 1.5 for q in oncurves))
                                    self.assertLess(min(math.dist(p, q) for q in implied), 24.)
