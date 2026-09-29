from pathlib import Path
import unittest

from fontTools.ttLib import TTFont

from scripts.rename_font_metadata import (
    SHAPE_FAMILY,
    WWS_BIT,
    check,
    family_for,
    font_files,
    rewrite_opentype_metadata,
)


ROOT = Path(__file__).resolve().parent.parent


class FontMetadataTest(unittest.TestCase):
    def testReleaseFontsUseReviewedWwsRepresentation(self) -> None:
        paths = font_files(ROOT / "fonts")
        self.assertTrue(paths)
        errors = [error for path in paths for error in check(path)]
        self.assertEqual(errors, [])

    def testRepresentativeFamilyAndStyleNamesRemainPublic(self) -> None:
        expected = {
            ROOT / "fonts" / "NamcheShadowSans" / "ttf" / "NamcheShadowSans-BoldItalic.ttf": (
                "Namche Shadow Sans",
                "Bold Italic",
            ),
            ROOT / "fonts" / "NamcheShadowMono" / "ttf" / "NamcheShadowMono-Regular.ttf": (
                "Namche Shadow Mono",
                "Regular",
            ),
            ROOT / "fonts" / "NamcheShape" / "ttf" / "NamcheShape-Metaball.ttf": (
                "Namche Shape",
                "Metaball",
            ),
        }
        for path, names in expected.items():
            font = TTFont(path, lazy=True)
            try:
                family = font["name"].getDebugName(16) or font["name"].getDebugName(1)
                style = font["name"].getDebugName(17) or font["name"].getDebugName(2)
                self.assertEqual((family, style), names)
                has_wws_bit = bool(font["OS/2"].fsSelection & WWS_BIT)
                wws_names = {
                    record.nameID: record.toUnicode()
                    for record in font["name"].names
                    if record.nameID in {21, 22} and record.platformID == 3
                }
                if family == SHAPE_FAMILY:
                    self.assertFalse(has_wws_bit)
                    self.assertEqual(
                        wws_names,
                        {21: "Namche Shape Metaball", 22: "Regular"},
                    )
                else:
                    self.assertTrue(has_wws_bit)
                    self.assertEqual(wws_names, {})
            finally:
                font.close()

    def testNpmFamilyDirectoryIsRecognized(self) -> None:
        path = (
            ROOT
            / "packages"
            / "next"
            / "dist"
            / "fonts"
            / "namche-shadow-sans"
            / "font.ttf"
        )
        self.assertEqual(family_for(path), ("Namche Shadow Sans", "NamcheShadowSans"))

    def testWwsBitRequiresOs2VersionFour(self) -> None:
        path = (
            ROOT
            / "fonts"
            / "NamcheShadowSans"
            / "ttf"
            / "NamcheShadowSans-Regular.ttf"
        )
        font = TTFont(path)
        try:
            font["OS/2"].version = 3
            with self.assertRaisesRegex(ValueError, "OS/2 version 4 or later"):
                rewrite_opentype_metadata(font, "Namche Shadow Sans")
        finally:
            font.close()
