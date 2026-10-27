"""Require exact GF Latin Core in every maintained Namche source and artifact."""
import json
from pathlib import Path
import glyphsLib
from ufoLib2 import Font
from latin_core import CODEPOINTS, ROOT, check_file
from subset_webfonts import read_unicode_ranges


def main():
    count = 0
    for source in (ROOT/'sources').glob('Namche*.glyphspackage'):
        font = glyphsLib.GSFont(str(source))
        actual = {int(value,16) for glyph in font.glyphs for value in glyph.unicodes}
        if actual != CODEPOINTS:
            raise ValueError(f'{source}: incorrect source character scope')
    for source in (ROOT/'sources').glob('NamcheShadowSans-*'):
        if not source.is_dir() or not (source/'provenance.json').exists():
            continue
        manifest = json.loads((source/'provenance.json').read_text())
        font = Font.open(source/manifest['ufo'])
        if {cp for glyph in font for cp in glyph.unicodes} != CODEPOINTS:
            raise ValueError(f'{source}: incorrect production-source character scope')
    for parent, pattern in [(ROOT/'fonts','Namche*'), (ROOT/'packages/next/dist/fonts','namche-*')]:
        for family in parent.glob(pattern):
            for path in family.rglob('*'):
                if path.suffix in ('.ttf','.otf','.woff2'):
                    check_file(path)
                    count += 1
    if read_unicode_ranges(ROOT/'sources/subsets/latin-core.txt')[0] != CODEPOINTS:
        raise ValueError('CSS Core ranges differ from canonical charset')
    if not count:
        raise ValueError('No release binaries checked')
    print(f'PASS: all Namche design/production sources and {count} release/npm fonts have exactly {len(CODEPOINTS)} characters')


if __name__ == '__main__':
    main()
