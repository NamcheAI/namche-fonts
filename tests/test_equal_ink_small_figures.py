"""The four small-figure sets share the source-sized radius and open counters."""
import json
import unittest

from glyphsLib import GSFont

from scripts.build_sans_equal_ink import BASE, contours, package, signature
from scripts.equal_ink_corners import SMALL_FIGURES, SMALL_FIGURE_SCALE, r90_for_stem
from scripts.round_inner_corners import MASTER_IDS, nodes_to_pathops


DIGITS = 'zero one two three four five six seven eight nine'.split()


class SmallFiguresTest(unittest.TestCase):
    def test_radius_uses_the_clean_design_height(self):
        sources = json.loads(BASE.read_text())['styles']
        for style in sources.values():
            for mid in MASTER_IDS.values():
                def height(name):
                    ys = [y for path in style[name]['masters'][mid] for _, y, _ in path]
                    return max(ys) - min(ys)
                self.assertEqual(SMALL_FIGURE_SCALE, height('foursuperior') / height('four'))
        # A numerator with a decimal base name shares the radius of its
        # unencoded superior.
        for upper in (True, False):
            self.assertEqual(r90_for_stem(10, upper, small_figure=True), 16)
            for stem in (32, 86, 196):
                self.assertAlmostEqual(r90_for_stem(stem, upper, small_figure=True), 28.8887324)
        self.assertEqual(r90_for_stem(86, True), 70)
        self.assertEqual(r90_for_stem(86), 53)
        for name in ('four', 'four.tf', 'one.ss09', 'fraction', 'ordfeminine'):
            self.assertNotIn(name, SMALL_FIGURES)

    def test_baked_small_figures_and_counter_through_all_seventeen_masters(self):
        sources = json.loads(BASE.read_text())['styles']
        for suffix in ('', '-Italic'):
            font = GSFont(package(suffix))
            refs = sources[suffix or 'Upright']['foursuperior']['masters']
            self.assertEqual([m.axes[0] for m in font.masters], list(range(100, 901, 50)))
            for digit in DIGITS:
                superior = digit + 'superior'
                previous = None
                for master in font.masters:
                    with self.subTest(slope=suffix, digit=digit, weight=master.axes[0]):
                        base = font.glyphs[superior].layers[master.id]
                        topology = signature(contours(base))
                        self.assertTrue(topology)
                        if previous is not None:
                            self.assertEqual(topology, previous)
                        previous = topology
                        for alias in (digit + '.numr', digit + '.dnom', digit + 'inferior'):
                            self.assertEqual(SMALL_FIGURES[alias], digit)
                            layer = font.glyphs[alias].layers[master.id]
                            self.assertFalse(layer.paths)
                            component, = layer.components
                            # The nine aliases are a half-turn of the small six.
                            self.assertEqual(component.componentName, 'sixsuperior' if digit == 'nine' else superior)
                            self.assertEqual(tuple(component.scale), (1, 1))
                        if digit == 'four':
                            w = master.axes[0]
                            a, b = ('Thin', 'Regular') if w <= 400 else ('Regular', 'Black')
                            fraction = (w - 100) / 300 if w <= 400 else (w - 400) / 500
                            first, last = refs[MASTER_IDS[a]][1], refs[MASTER_IDS[b]][1]
                            triangle = [(x + fraction*(u-x), y + fraction*(v-y), kind)
                                        for (x,y,kind), (u,v,_) in zip(first, last, strict=True)]
                            ratio = abs(nodes_to_pathops(contours(base)[1]).area / nodes_to_pathops(triangle).area)
                            self.assertGreater(ratio, .92)
                            self.assertLess(ratio, 1)
