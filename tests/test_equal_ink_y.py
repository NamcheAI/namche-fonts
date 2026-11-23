"""The default y stays round as the contact passes from a curve onto the flat."""
import json
import unittest
from pathlib import Path

from shapely.geometry import LineString

from scripts import equal_ink_corners as eq
from scripts.check_equal_ink import _filled_geos
from scripts.round_inner_corners import MASTER_IDS


class YJunctionTest(unittest.TestCase):
    def test_contact_topology_and_reviewed_edge_across_weights(self):
        root = Path(__file__).resolve().parents[1]
        styles = json.loads((root/'sources/equal-ink/clean-outlines.json').read_text())['styles']
        # Independent scanline measurements in Michael's pinned r3_y_vorschau:
        # font-space (y, x) of the left ink edge. Black used to miss by 13–17 units.
        sample = {
            ('Upright', 100): (-11.1, 237.6), ('Upright', 400): (-23.7, 225.0),
            ('Upright', 700): (-26.8, 202.6), ('Upright', 900): (-1.1, 198.2),
            ('-Italic', 400): (-23.7, 161.6), ('-Italic', 700): (-26.8, 133.9),
            ('-Italic', 900): (-1.1, 127.4),
        }
        weights = list(range(100, 901, 50))
        for style, records in styles.items():
            source = [records['y']['masters'][mid][0] for mid in MASTER_IDS.values()]
            originals = []
            for weight in weights:
                i = int(weight > 400)
                lo, hi = ((100, 400), (400, 900))[i]
                t = (weight-lo)/(hi-lo)
                originals.append([[(x+(u-x)*t, y+(v-y)*t, kind)
                                   for (x,y,kind),(u,v,_) in zip(source[i], source[i+1], strict=True)]])
            radii = [51.2] + [53.] * (len(weights)-1)
            rounded, report = eq.round_y_junction(originals, radii, weights, style == '-Italic')
            topology = eq._topology(rounded[0])
            for weight, r90, member, metric in zip(weights, radii, rounded, report['masters'], strict=True):
                with self.subTest(style=style, weight=weight):
                    self.assertEqual(eq._topology(member), topology)
                    self.assertTrue(.60*r90 <= metric['radius'] <= r90)
                    if weight <= 400:
                        self.assertEqual(metric['radius'], r90)
                    if weight >= 700:
                        self.assertEqual(metric['flank'], 2)  # horizontal terminal
                    chain = eq.nodes_to_segments(member[0])[6:12]
                    # Smooth tangent contacts at both ends and at the central
                    # arc knot; the remaining authored tail may have a slight
                    # inflection further downstream.
                    for left,right in zip(chain[:3], chain[1:4]):
                        self.assertGreater(eq.dot(eq.seg_tangent_in(left), eq.seg_tangent_out(right)), .99999)
                    self.assertTrue(all(eq.seg_length(s) > .01 for s in chain))
                    if (style, weight) in sample:
                        y, expected_x = sample[style, weight]
                        outline, _ = _filled_geos({'y':eq._NodeGlyph(member)}, 'y', .005)
                        edge = outline.intersection(LineString([(-1000, y), (3000, y)])).bounds[0]
                        self.assertAlmostEqual(edge, expected_x, delta=1.7)
