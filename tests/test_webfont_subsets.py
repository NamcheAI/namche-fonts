from pathlib import Path
import tempfile
import unittest

from fontTools.ttLib import TTFont

from scripts.subset_webfonts import (
    DEFAULT_UNICODE_FILE,
    read_unicode_ranges,
    subset_webfont,
    unicode_codepoints,
)


ROOT = Path(__file__).resolve().parents[1]
SOURCE = (
    ROOT
    / "fonts"
    / "NamcheShadowSans"
    / "webfonts"
    / "NamcheShadowSans[wght].woff2"
)


def names(font: TTFont) -> set[tuple[int, int, int, int, bytes]]:
    return {
        (
            record.nameID,
            record.platformID,
            record.platEncID,
            record.langID,
            record.toBytes(),
        )
        for record in font["name"].names
        # IDs 256+ are labels for optional OpenType feature parameters. The
        # subsetter correctly removes labels whose alternate glyphs are not in
        # the Latin subset; the standard family, attribution, license, and
        # version records must remain byte-identical.
        if record.nameID < 256
    }


class WebfontSubsetTests(unittest.TestCase):
    def test_latin_subset_is_deterministic_and_preserves_font_contracts(self) -> None:
        codepoints, css_range = read_unicode_ranges(DEFAULT_UNICODE_FILE)
        self.assertIn(0x00E3, codepoints)  # Portuguese a with tilde
        self.assertIn(0x20AC, codepoints)  # euro
        self.assertNotIn(0x0410, codepoints)  # Cyrillic A
        self.assertIn("U+0020-007E", css_range)

        with tempfile.TemporaryDirectory() as temporary_directory:
            first = Path(temporary_directory) / "first.woff2"
            second = Path(temporary_directory) / "second.woff2"
            subset_webfont(SOURCE, first, codepoints)
            subset_webfont(SOURCE, second, codepoints)
            self.assertEqual(first.read_bytes(), second.read_bytes())
            self.assertLess(first.stat().st_size, SOURCE.stat().st_size / 2)

            original = TTFont(SOURCE)
            subset = TTFont(first)
            self.assertEqual(
                unicode_codepoints(subset),
                unicode_codepoints(original) & codepoints,
            )
            self.assertNotIn(0x0410, unicode_codepoints(subset))
            self.assertEqual(names(subset), names(original))
            self.assertEqual(subset["meta"].data["dlng"], "Latn")
            self.assertEqual(subset["meta"].data["slng"], "Latn")
            self.assertEqual(
                [
                    (axis.axisTag, axis.minValue, axis.defaultValue, axis.maxValue)
                    for axis in subset["fvar"].axes
                ],
                [
                    (axis.axisTag, axis.minValue, axis.defaultValue, axis.maxValue)
                    for axis in original["fvar"].axes
                ],
            )
            for table in ("GDEF", "GPOS", "GSUB", "HVAR", "gvar"):
                self.assertIn(table, subset)


if __name__ == "__main__":
    unittest.main()
