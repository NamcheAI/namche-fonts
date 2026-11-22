"""Round-trip and target-safety tests for the Glyphs package writer."""

from pathlib import Path
import copy
import math
import tempfile
import unittest

import glyphsLib
from glyphsLib import GSFont

from scripts.write_glyphspackage import save_package


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "sources/NamcheShadowSans.glyphspackage"


class WriteGlyphsPackageTests(unittest.TestCase):
    def test_v3_round_trip_preserves_font_and_layout_data(self):
        font = GSFont(str(TEMPLATE))
        self.assertEqual(font.format_version, 3)
        glyphs = {glyph.name: glyph for glyph in font.glyphs}
        self.assertGreaterEqual(len(font.masters), 2)
        self.assertEqual(int(glyphs["Aacute"].unicode, 16), 0xC1)
        self.assertTrue(any(layer.components for layer in glyphs["Aacute"].layers))
        self.assertTrue(any(font.kerning.values()))

        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "RoundTrip.glyphspackage"
            save_package(font, target, TEMPLATE)
            reloaded = GSFont(str(target))

        self.assertEqual(glyphsLib.dumps(font), glyphsLib.dumps(reloaded))

    def test_filename_inventory_failure_leaves_existing_target_untouched(self):
        font = GSFont(str(TEMPLATE))
        font.glyphs = list(font.glyphs)[:-1]
        marker = b"existing target must survive"
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "owned-output.glyphspackage"
            target.write_bytes(marker)
            with self.assertRaisesRegex(ValueError, "filename inventory"):
                save_package(font, target, TEMPLATE)
            self.assertEqual(target.read_bytes(), marker)

    def test_package_matches_monolithic_normalization_for_zero_values(self):
        font = GSFont(str(TEMPLATE))
        glyphs = {glyph.name: glyph for glyph in font.glyphs}
        component = next(iter(glyphs["Aacute"].layers)).components[0]
        component.position = (1e-6, -1e-6)

        master_id = next(iter(font.kerningLTR))
        left = next(iter(font.kerningLTR[master_id]))
        right = next(iter(font.kerningLTR[master_id][left]))
        font.kerningLTR[master_id][left][right] = -0.0

        expected = glyphsLib.loads(glyphsLib.dumps(copy.deepcopy(font)))
        expected_serialization = glyphsLib.dumps(expected)
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "Normalized.glyphspackage"
            save_package(font, target, TEMPLATE)
            reloaded = GSFont(str(target))

        self.assertEqual(component.position.x, 1e-6)
        self.assertEqual(component.position.y, -1e-6)
        self.assertLess(math.copysign(1, font.kerningLTR[master_id][left][right]), 0)
        self.assertEqual(glyphsLib.dumps(reloaded), expected_serialization)


if __name__ == "__main__":
    unittest.main()
