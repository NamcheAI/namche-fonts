from pathlib import Path
import sys
import tempfile
import unittest
from fontTools.ttLib import TTFont
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from latin_core import ROOT, CODEPOINTS, check_file
from latin_core import normalize_info

class CoreScopeTest(unittest.TestCase):
    def test_extra_unicode_is_rejected(self):
        source=ROOT/'fonts/NamcheShadowSans/ttf/NamcheShadowSans-Regular.ttf'
        with TTFont(source) as font, tempfile.TemporaryDirectory() as directory:
            for table in font['cmap'].tables:
                if table.isUnicode():table.cmap[0x410]=font.getBestCmap()[0x41]
            output=Path(directory)/'extra.ttf';font.save(output)
            with self.assertRaisesRegex(ValueError, 'extra='):check_file(output)

    def test_missing_core_mark_is_rejected(self):
        source=ROOT/'fonts/NamcheShadowSans/ttf/NamcheShadowSans-Regular.ttf'
        with TTFont(source) as font, tempfile.TemporaryDirectory() as directory:
            for table in font['cmap'].tables:
                if table.isUnicode():table.cmap.pop(0x302,None)
            output=Path(directory)/'missing.ttf';font.save(output)
            with self.assertRaisesRegex(ValueError, 'missing='):check_file(output)

    def test_filter_scope_never_turns_empty_include_into_global_filter(self):
        info={'customParameters':[{'name':'Filter','value':'RoundCorner;-60;exclude:A,A-cy'},
             {'name':'Filter','value':'RoundCorner;-40;include:A,A-cy'},
             {'name':'Filter','value':'RoundCorner;-10;include:A-cy'}]}
        normalize_info(info, {'A'})
        self.assertEqual([p['value'] for p in info['customParameters']],
            ['RoundCorner;-60;exclude:A','RoundCorner;-40;include:A'])

if __name__=='__main__':unittest.main()
