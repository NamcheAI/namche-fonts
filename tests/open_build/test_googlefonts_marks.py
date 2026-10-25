"""Check candidate mark attachment and preservation of existing text."""
from io import BytesIO
from pathlib import Path
import sys
import unittest

import uharfbuzz as hb
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from build_sans_open import RELEASE
from googlefonts_marks import add_macron_below, GLYPH


def shape(data, text, weight):
    font = hb.Font(hb.Face(data))
    font.set_variations({'wght': weight})
    buffer = hb.Buffer()
    buffer.add_str(text)
    buffer.guess_segment_properties()
    hb.shape(font, buffer)
    return [(info.codepoint, position.x_advance, position.y_advance,
             position.x_offset, position.y_offset)
            for info, position in zip(buffer.glyph_infos, buffer.glyph_positions)]


class MacronBelowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fonts = []
        for style in ('', '-Italic'):
            path = RELEASE / f'variable/NamcheShadowSans{style}[wght].ttf'
            font = TTFont(path, recalcTimestamp=False)
            add_macron_below(font)
            stream = BytesIO()
            font.save(stream)
            cls.fonts.append((path.read_bytes(), stream.getvalue()))

    def test_original_text_keeps_glyphs_advances_and_positions(self):
        for original, candidate in self.fonts:
            repertoire = ' '.join(chr(codepoint) for codepoint in TTFont(BytesIO(original)).getBestCmap())
            for weight in (100, 250, 400, 450, 700, 900):
                for text in ('H E a M 0123456789', 'a\u0323 a\u0323\u0323 i\u0302',
                             'į́ ị̂ і́ А́', 'fi ffi fl AV To', '◌\u0304 ◌\u0323', repertoire):
                    with self.subTest(weight=weight, text=text):
                        self.assertEqual(shape(original, text, weight), shape(candidate, text, weight))

    def test_mark_is_zero_width_attaches_and_stacks_below(self):
        for original, candidate in self.fonts:
            font = TTFont(BytesIO(candidate))
            mark_id = font.getGlyphID(GLYPH)
            for weight in (100, 200, 400, 450, 700, 900):
                instance = instantiateVariableFont(font, {'wght': weight}, inplace=False)
                glyph = instance['glyf'][GLYPH]
                self.assertEqual(instance['hmtx'][GLYPH][0], 0)
                self.assertGreater(glyph.numberOfContours, 0)
                self.assertLess(glyph.yMax, 0)
                for base in 'AaEeIiOoUuNn◌':
                    marked = shape(candidate, base + '\u0331', weight)
                    self.assertIn(mark_id, [item[0] for item in marked])
                    self.assertNotIn(0, [item[0] for item in marked])
                    self.assertEqual(sum(item[1] for item in marked),
                                     sum(item[1] for item in shape(candidate, base, weight)))
                stacked = shape(candidate, 'a\u0331\u0331', weight)
                marks = [item for item in stacked if item[0] == mark_id]
                self.assertEqual(len(marks), 2)
                self.assertLess(marks[1][4] + glyph.yMax, marks[0][4] + glyph.yMin)


if __name__ == '__main__':
    unittest.main()
