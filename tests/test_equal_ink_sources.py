"""Guard the italic source migration against stale upright backgrounds."""
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

import openstep_plist
from glyphsLib import GSFont

from scripts import build_sans_equal_ink as build
from scripts.check_equal_ink import _filled_geos, _geos_counters, _polygon_parts

ROOT = Path(__file__).resolve().parents[1]



def clean_model(suffix):
    """Exercise the real UFO interpolation model with pinned unrounded inputs."""
    records = json.loads(build.BASE.read_text())['styles'][suffix or 'Upright']
    font = GSFont(build.package(suffix))
    ids = set(records['I']['masters'])
    font.masters = [master for master in font.masters if master.id in ids]
    for glyph in font.glyphs:
        inputs = records[glyph.name]['masters']
        glyph.layers = [layer for layer in glyph.layers if layer.layerId in inputs]
        for layer_id, paths in inputs.items():
            build.set_paths(glyph.layers[layer_id], paths)
            glyph.layers[layer_id]._background = None
    build.add_intermediate_masters(font)
    return font


class EqualInkSourceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.clean = json.loads(build.BASE.read_text())['styles']['-Italic']
        cls.upstream = GSFont(ROOT/'originals/geist/sources/Geist-Italic.glyphspackage')

    def test_italic_H_stems_slope_right_in_every_master(self):
        # H's stale background is upright despite compatible topology.
        # Check the actual independent geometric property, not node identity.
        for master in self.upstream.masters:
            with self.subTest(weight=master.axes[0]):
                points = [point for contour in self.clean['H']['masters'][master.id]
                          for point in contour]
                bottom = min(x for x, y, _ in points if y == 0)
                top = min(x for x, y, _ in points if y == 710)
                self.assertGreater(top-bottom, 100)
                self.assertLess(top-bottom, 200)

    def test_clean_interpolation_keeps_percent_and_quote_parts_separate(self):
        # A shared bad clean baseline can pass candidate-minus-baseline gates.
        # Inspect topology/positions independently with GEOS, not PathOps.
        for suffix in ('', '-Italic'):
            font = clean_model(suffix)
            self.assertEqual([m.axes[0] for m in font.masters], list(range(100, 901, 50)))
            for master in font.masters:
                glyphs = {g.name: g.layers[master.id] for g in font.glyphs}
                with self.subTest(style=suffix or 'Upright', weight=master.axes[0], glyph='percent'):
                    ink, _ = _filled_geos(glyphs, 'percent', .01)
                    holes = sorted(_geos_counters(ink), key=lambda h: h.centroid.y)
                    self.assertEqual(len(holes), 2)
                    # Two holes alone can survive when both rings collapse at
                    # the center. Keep the lower-right and upper-left rings.
                    self.assertGreater(holes[1].centroid.y-holes[0].centroid.y, 200)
                    self.assertGreater(holes[0].centroid.x-holes[1].centroid.x, 100)
                with self.subTest(style=suffix or 'Upright', weight=master.axes[0], glyph='quotedbl'):
                    ink, _ = _filled_geos(glyphs, 'quotedbl', .01)
                    strokes = _polygon_parts(ink)
                    self.assertEqual(len(strokes), 2)
                    self.assertGreater(min(stroke.area for stroke in strokes), 10)
                    self.assertGreater(abs(strokes[0].centroid.x-strokes[1].centroid.x), 20)

    def test_initialize_refuses_to_overwrite_pinned_design_inputs(self):
        with tempfile.TemporaryDirectory() as folder:
            fixture = Path(folder)/'clean.json'
            fixture.write_text('pinned design inputs\n')
            with patch.object(build, 'BASE', fixture):
                with self.assertRaisesRegex(ValueError, 'refusing to replace'):
                    build.initialize()
            self.assertEqual(fixture.read_text(), 'pinned design inputs\n')

    def test_prepare_component_interpolation_matches_saved_package_precision(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root/'source'
            source.mkdir()
            for suffix in ('', '-Italic'):
                shutil.copytree(build.package(suffix), source/f'NamcheShadowSans{suffix}.glyphspackage')

            # Recreate the original source precision that exposed the issue:
            # 1.7494 and 1.5899 interpolate to values whose rounded package
            # forms differ from a later interpolation of the saved endpoints.
            bullet = source/'NamcheShadowSans.glyphspackage/glyphs/bullet.glyph'
            data = openstep_plist.loads(bullet.read_text(), use_numbers=True)
            endpoint_scales = {
                'EE2FFE84-06F1-4AFB-BBEC-60D09A436D14': 1.7494,
                '6C190511-B94A-4F5A-B519-D6E9DB0E7B93': 1.7494,
                '3507EE3D-0D92-4546-A145-3A991F0A2B71': 1.5899,
            }
            for layer in data['layers']:
                scale = endpoint_scales.get(layer['layerId'])
                if scale is not None:
                    layer['shapes'][0]['scale'] = [scale, scale]
            bullet.write_text(openstep_plist.dumps(data, sort_keys=False) + '\n')

            output1, output2 = root/'first', root/'second'
            output1.mkdir()
            output2.mkdir()
            with patch.object(build, 'package', side_effect=lambda suffix: source/f'NamcheShadowSans{suffix}.glyphspackage'):
                build.prepare(output1, only={'bullet'})

            first_package = output1/'NamcheShadowSans.glyphspackage'
            first_font = GSFont(str(first_package))
            first_by_weight = {master.axes[0]: master.id for master in first_font.masters}
            first_scales = {
                weight: tuple(first_font.glyphs['bullet'].layers[first_by_weight[weight]].components[0].scale)
                for weight in (500, 550, 600)
            }
            self.assertEqual(first_scales, {500: (1.717, 1.717), 550: (1.701, 1.701), 600: (1.685, 1.685)})

            with patch.object(build, 'package', side_effect=lambda suffix: first_package if not suffix else output1/'NamcheShadowSans-Italic.glyphspackage'):
                build.prepare(output2, only={'bullet'})

            second_font = GSFont(str(output2/'NamcheShadowSans.glyphspackage'))
            second_by_weight = {master.axes[0]: master.id for master in second_font.masters}
            second_scales = {
                weight: tuple(second_font.glyphs['bullet'].layers[second_by_weight[weight]].components[0].scale)
                for weight in (500, 550, 600)
            }
            self.assertEqual(second_scales, first_scales)


if __name__ == '__main__':
    unittest.main()
