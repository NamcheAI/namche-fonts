"""Round-four regression: the quantized italic y and its accents share tangents."""

from copy import deepcopy
from pathlib import Path
import unittest

from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import newTable
from fontTools.ttLib.tables.TupleVariation import TupleVariation

from scripts.equal_ink_tangents import Y_FORMS, imply_glyf_oncurves
from scripts.measure_y_terminal import fixed_font, inward_dent, maximum_tangent_break, terminal_segments


RELEASE = Path(__file__).resolve().parents[1] / 'fonts' / 'NamcheShadowSans'


class YTerminalTest(unittest.TestCase):
    def test_compiled_terminal_tangents_and_accented_forms(self):
        for fmt, weights in (('variable', (100, 375, 400, 425, 450, 475, 500, 525, 700, 900)),
                             ('ttf', (400, 500)), ('otf', (400, 500))):
            for weight in weights:
                with self.subTest(fmt=fmt, weight=weight), fixed_font(RELEASE, fmt, weight) as font:
                    base = terminal_segments(font)
                    self.assertGreater(len(base), 1)
                    self.assertLess(maximum_tangent_break(base), 1e-5)
                    if 375 <= weight <= 525:
                        self.assertLess(inward_dent(base), .05)
                        self.assertEqual(base[0][0][1], base[0][1][1], 'the terminal must start flat')
                    for name in Y_FORMS[1:]:
                        self.assertEqual(terminal_segments(font, name), base, name)

    def test_implied_contact_keeps_sparse_deltas_and_all_metric_phantoms(self):
        pen = TTGlyphPen(None)
        pen.moveTo((0, 0))
        pen.qCurveTo((5, 0), (10, 2))
        pen.qCurveTo((16, 5), (20, 10))
        pen.lineTo((0, 10))
        pen.closePath()
        pen.moveTo((0, 30))
        pen.lineTo((10, 30))
        pen.lineTo((0, 40))
        pen.closePath()
        builder = FontBuilder(1000, isTTF=True)
        builder.setupGlyphOrder(['y'])
        builder.setupGlyf({'y': pen.glyph()})
        builder.setupHorizontalMetrics({'y': (725, 45)})
        font = builder.font
        glyf = font['glyf']
        original, controls = glyf._getCoordinatesAndControls('y', font['hmtx'].metrics)
        deltas = [None] * len(original)
        deltas[0], deltas[2], deltas[4] = (4, 1), (8, 2), (12, 5)
        deltas[-4:] = [(5, 0), (8, 0), (0, 2), (0, -3)]
        variation = TupleVariation({'wght': (0, 1, 1)}, deltas)
        font['gvar'] = newTable('gvar')
        font['gvar'].variations = {'y': [variation]}
        expanded = deepcopy(variation)
        expanded.calcInferredDeltas(original, controls.endPts)
        imply_glyf_oncurves(font, 'y', [2])
        revised, new_controls = glyf._getCoordinatesAndControls('y', font['hmtx'].metrics)
        self.assertEqual(list(revised), list(original[:2]) + list(original[3:]))
        self.assertEqual(variation.coordinates, expanded.coordinates[:2] + expanded.coordinates[3:])
        self.assertEqual(new_controls.endPts, [end - 1 for end in controls.endPts])
