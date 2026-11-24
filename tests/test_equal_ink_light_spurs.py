"""Regressions for Michael's round-3 Thin lowercase join adjustment."""

import json
from pathlib import Path
import unittest

from scripts import equal_ink_corners as corners


class LightSpurTest(unittest.TestCase):
    def test_radius_fraction_tapers_to_the_existing_regular_rule(self):
        for weight, expected in ((100, .4), (150, 13/30), (200, 7/15), (250, .5),
                                 (300, 8/15), (350, 17/30), (400, .6), (900, .6)):
            with self.subTest(weight=weight):
                self.assertAlmostEqual(corners.spur_floor_at(weight), expected)

    def test_real_lowercase_thin_shoulders_lighten_and_heavier_outlines_remain_exact(self):
        fixture = Path(__file__).resolve().parents[1] / 'sources/equal-ink/clean-outlines.json'
        styles = json.loads(fixture.read_text())['styles']
        for style in ('Upright', '-Italic'):
            with self.subTest(slope=style):
                masters = list(styles[style]['h']['masters'].values())
                radii = [51.2, 53., 53.]
                before, _ = corners.round_compatible_contours(masters, radii, soft_spurs=True)
                after, _ = corners.round_compatible_contours(
                    masters, radii, spur_floors=[corners.spur_floor_at(w) for w in (100, 400, 900)])
                # The already approved Regular and Black remain identical down to the nodes.
                self.assertEqual(after[1:], before[1:])
                base_area = corners._path(masters[0]).area
                prior_ink = corners._path(before[0]).area - base_area
                next_ink = corners._path(after[0]).area - base_area
                self.assertGreater(next_ink, 0)
                self.assertLess(next_ink, .85 * prior_ink)
                self.assertEqual(corners._counter_count(corners._path(after[0])),
                                 corners._counter_count(corners._path(masters[0])))

    def test_curved_n_short_spur_uses_the_prototype_tangent_reach_and_releases_it(self):
        fixture = Path(__file__).resolve().parents[1] / 'sources/equal-ink/clean-outlines.json'
        styles = json.loads(fixture.read_text())['styles']
        floors = [corners.spur_floor_at(w) for w in (100, 200, 300, 400)]
        for slope, thin_limit in (('Upright', 13.4), ('-Italic', 12.0)):
            with self.subTest(slope=slope):
                thin = next(iter(styles[slope]['n']['masters'].values()))
                # Use the same real curved shoulder at each weight to isolate
                # the taper from the simultaneous interpolation of the glyph.
                source = [thin] * len(floors)
                _, report = corners.round_compatible_contours(source, [51.2] * len(floors), spur_floors=floors)
                shoulder, = [j['masters'] for j in report if j['status'] == 'rounded']
                accepted_radius = shoulder[-1]['radius']
                self.assertNotIn('tangent_run_limit', shoulder[-1])
                self.assertGreater(accepted_radius, thin_limit + 3)
                for index, master in enumerate(shoulder[:-1]):
                    limit = master['tangent_run_limit']
                    self.assertAlmostEqual(limit, thin_limit, delta=.15)
                    fraction = index / 3
                    self.assertAlmostEqual(master['radius'], limit + fraction * (accepted_radius - limit), places=4)
                    self.assertGreater(master['area'], 0)


if __name__ == '__main__':
    unittest.main()
