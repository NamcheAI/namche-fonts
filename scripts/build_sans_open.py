#!/usr/bin/env python3
"""Rebuild the approved Sans VFs from open quadratic UFO/TTX sources.

--check builds twice in isolation and requires byte equality with the pinned
release hashes and committed TTF/WOFF2. No release binaries are build inputs.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import tempfile

from fontTools.pens.ttGlyphPen import TTGlyphPointPen
from fontTools.ttLib import TTFont, newTable
from fontTools.ttLib.ttFont import reorderFontTables
from ufoLib2 import Font

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / 'sources/NamcheShadowSans-Upright'
ITALIC_SOURCE = ROOT / 'sources/NamcheShadowSans-Italic'
RELEASE = ROOT / 'fonts/NamcheShadowSans'
FILES = ('variable/NamcheShadowSans[wght].ttf', 'webfonts/NamcheShadowSans[wght].woff2')


def build(source: Path, output: Path) -> None:
    manifest = json.loads((source / 'provenance.json').read_text())
    ufo = Font.open(source / manifest.get('ufo', 'Upright.ufo'))
    point_order = json.loads((source / 'point-order.json').read_text())
    font = TTFont(recalcTimestamp=False)
    # Require the production layout serializer; never silently switch backends.
    font.cfg['fontTools.ttLib.tables.otBase:USE_HARFBUZZ_REPACKER'] = manifest.get('harfbuzz_repacker', True)
    font.importXML(source / 'variation-and-layout.ttx')
    if font.getGlyphOrder() != ufo.glyphOrder:
        raise ValueError('UFO glyph order must match the indexed variation/layout sources')
    font['glyf'] = newTable('glyf')
    font['glyf'].glyphs = {}
    font['glyf'].glyphOrder = ufo.glyphOrder
    font['loca'] = newTable('loca')
    for name in ufo.glyphOrder:
        actual_order = [[point.identifier for point in contour.points]
                        for contour in ufo[name].contours]
        if actual_order != point_order[name]:
            raise ValueError(f'{name}: point order or contour boundaries changed; migrate variation deltas before rebuilding')
        pen = TTGlyphPointPen(ufo)
        ufo[name].drawPoints(pen)
        glyph = pen.glyph()
        flags = ufo[name].lib['org.namche.originalFlags']
        if glyph.numberOfContours:
            if len(glyph.flags) != len(flags) or [v & 1 for v in glyph.flags] != [v & 1 for v in flags]:
                raise ValueError(f'{name}: point topology changed; migrate variation deltas before rebuilding')
            glyph.flags[:] = type(glyph.flags)('B', flags)
        elif flags:
            raise ValueError(f'{name}: empty glyph has nonempty point flags')
        font['glyf'].glyphs[name] = glyph
        font['hmtx'][name] = (int(ufo[name].width), font['hmtx'][name][1])
    # gvar XML needs the completed glyf table to resolve indexed deltas.
    font.importXML(source / 'variations.ttx')
    font.recalcTimestamp = False
    ttf_path, woff_path = (output / p for p in manifest['outputs'])
    ttf_path.parent.mkdir(parents=True, exist_ok=True)
    woff_path.parent.mkdir(parents=True, exist_ok=True)
    raw, ordered = BytesIO(), BytesIO()
    font.save(raw, reorderTables=False)
    raw.seek(0)
    reorderFontTables(raw, ordered, tableOrder=manifest['table_order'])
    ttf_path.write_bytes(ordered.getvalue())
    webfont = TTFont(ttf_path, recalcTimestamp=False)
    webfont.flavor = 'woff2'
    webfont.save(woff_path, reorderTables=False)


def check(source: Path, release: Path) -> None:
    expected = json.loads((source / 'provenance.json').read_text())['outputs']
    with tempfile.TemporaryDirectory(prefix='namche-open-check-') as tmp:
        first, second = Path(tmp) / 'first', Path(tmp) / 'second'
        build(source, first)
        build(source, second)
        for relative in expected:
            data = (first / relative).read_bytes()
            digest = sha256(data).hexdigest()
            if digest != expected[relative]:
                raise ValueError(f'{relative}: rebuilt SHA-256 {digest} differs from approved {expected[relative]}')
            if data != (second / relative).read_bytes():
                raise ValueError(f'{relative}: repeated builds differ')
            if data != (release / relative).read_bytes():
                raise ValueError(f'{relative}: committed release differs from open build')
            print(f'PASS {relative}: two builds = pinned hash = committed release ({digest})')


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, help='Build only the specified production source; default: both styles')
    parser.add_argument('--output', type=Path, default=RELEASE)
    parser.add_argument('--release', type=Path, default=RELEASE, help='committed reference directory for --check')
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    for source in ([args.source] if args.source else [SOURCE, ITALIC_SOURCE]):
        if args.check:
            check(source, args.release)
        else:
            build(source, args.output)


if __name__ == '__main__':
    main()
