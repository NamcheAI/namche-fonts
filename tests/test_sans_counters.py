from pathlib import Path
import tempfile
import unittest

from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont

from scripts.check_sans_counters import (
    EXPECTED_CONTOURS,
    EXPECTED_RELEASE_FILES,
    release_fonts,
    validate_font,
)
from scripts.refresh_sans_italic_outlines import (
    cff_bytecode,
    changed_outlines,
    check_hinting_environment,
    check_untouched_charstrings,
    open_font,
)


ROOT = Path(__file__).resolve().parent.parent
SANS = ROOT / "fonts" / "NamcheShadowSans"


class SansCounterTest(unittest.TestCase):
    def testEveryTrackedGlyphKeepsItsCounterInUprightAndItalic(self) -> None:
        for style in ("Regular", "Italic", "Thin", "ThinItalic", "BlackItalic"):
            for directory, suffix in (("otf", ".otf"), ("ttf", ".ttf")):
                path = SANS / directory / f"NamcheShadowSans-{style}{suffix}"
                with self.subTest(font=path.name):
                    self.assertEqual(validate_font(path), [])

    def testTheReleaseFileCountMatchesTheDeclaredExpectation(self) -> None:
        self.assertEqual(len(release_fonts(ROOT)), EXPECTED_RELEASE_FILES)

    def testACollapsedCounterIsReported(self) -> None:
        # The italic A shipped as one contour, its counter welded into the
        # silhouette (issue #78). Rebuild that topology by keeping only the
        # outer contour and confirm the guard rejects it.
        source = SANS / "ttf" / "NamcheShadowSans-MediumItalic.ttf"
        font = TTFont(source, recalcTimestamp=False)
        glyf = font["glyf"]
        outer = glyf["A"].endPtsOfContours[0] + 1
        pen = TTGlyphPen(glyf)
        coordinates, _ends, _flags = glyf["A"].getCoordinates(glyf)
        pen.moveTo(coordinates[0])
        for point in coordinates[1:outer]:
            pen.lineTo(point)
        pen.closePath()
        glyf["A"] = pen.glyph()
        with tempfile.TemporaryDirectory() as scratch:
            welded = Path(scratch) / "welded-a.ttf"
            font.save(welded)
            font.close()
            errors = validate_font(welded)
        self.assertTrue(
            any("A has 1 contour(s), expected 2" in error for error in errors), errors
        )

    def testTrackedGlyphsCoverTheLetterThatRegressed(self) -> None:
        self.assertEqual(EXPECTED_CONTOURS["A"], 2)


class ItalicOutlineMergeGuardTest(unittest.TestCase):
    """The merge tool's safety net has to survive a refactor of its call order.

    Drawing a glyph clears the CFF charstring's ``bytecode``, so capturing it
    after ``changed_outlines`` silently turns the untouched-glyph comparison
    into ``None != None`` and the guard passes on anything.
    """

    OTF = SANS / "otf" / "NamcheShadowSans-MediumItalic.otf"

    def testBytecodeIsCapturedBeforeAnythingDecompilesIt(self) -> None:
        font = open_font(self.OTF)
        try:
            glyphs, global_subrs, local_subrs = cff_bytecode(font)
        finally:
            font.close()
        self.assertIn("A", glyphs)
        self.assertTrue(all(isinstance(code, bytes) for code in glyphs.values()))
        self.assertTrue(global_subrs and local_subrs)

    def testCapturingAfterDrawingIsRefused(self) -> None:
        font = open_font(self.OTF)
        try:
            changed_outlines(font, open_font(self.OTF))
            with self.assertRaises(SystemExit):
                cff_bytecode(font)
        finally:
            font.close()

    def testAReEncodedUntouchedGlyphBlocksTheMerge(self) -> None:
        font = open_font(self.OTF)
        try:
            release = cff_bytecode(font)
        finally:
            font.close()
        glyphs = dict(release[0])
        glyphs["B"] = glyphs["B"] + b"\x00"
        with self.assertRaises(SystemExit):
            check_untouched_charstrings(release, (glyphs, release[1], release[2]), ["A"])

    def testChangedSubrsBlockTheMerge(self) -> None:
        font = open_font(self.OTF)
        try:
            release = cff_bytecode(font)
        finally:
            font.close()
        global_subrs = list(release[1])
        global_subrs[0] = global_subrs[0] + b"\x00"
        with self.assertRaises(SystemExit):
            check_untouched_charstrings(
                release, (release[0], global_subrs, release[2]), ["A"]
            )

    def testADifferentHintingEnvironmentBlocksTheMerge(self) -> None:
        # A transplanted ttfautohint program indexes the font's own cvt and
        # fpgm, so the build has to share them with the release.
        ttf = SANS / "ttf" / "NamcheShadowSans-MediumItalic.ttf"
        with tempfile.TemporaryDirectory() as scratch:
            tampered = Path(scratch) / "other-cvt.ttf"
            font = TTFont(ttf, recalcTimestamp=False)
            font["cvt "].values[0] += 7
            font.save(tampered)
            font.close()
            release, compiled = open_font(ttf), open_font(tampered)
            try:
                with self.assertRaises(SystemExit):
                    check_hinting_environment(release, compiled)
            finally:
                release.close()
                compiled.close()

    def testAnUnchangedBuildPassesTheGuard(self) -> None:
        release, compiled = open_font(self.OTF), open_font(self.OTF)
        try:
            check_untouched_charstrings(
                cff_bytecode(release), cff_bytecode(compiled), ["A"]
            )
        finally:
            release.close()
            compiled.close()


if __name__ == "__main__":
    unittest.main()
