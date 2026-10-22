#!/usr/bin/env python3
"""Explicit, one-time recovery of an approved VF as editable production sources.

Not a build dependency. Review changes to sources and approved output hashes
before use. Design masters are maintained separately from this exact snapshot.
"""
import argparse
from hashlib import sha256
import json
from pathlib import Path
from fontTools.ttLib import TTFont
from ufoLib2 import Font


def recover(ttf: Path, woff: Path, output: Path, commit: str, italic: bool) -> None:
    font = TTFont(ttf, recalcTimestamp=False)
    ufo = Font()
    style = 'Italic' if italic else 'Upright'
    ufo.info.familyName = font['name'].getBestFamilyName()
    ufo.info.styleName = 'Italic' if italic else 'Regular'
    ufo.info.unitsPerEm = font['head'].unitsPerEm
    ufo.glyphOrder = font.getGlyphOrder()
    glyphset = font.getGlyphSet()
    cmap = font.getBestCmap()
    order = {}
    for name in ufo.glyphOrder:
        original = font['glyf'][name]
        if original.isComposite() or (getattr(original, 'program', None) and original.program.getBytecode()):
            raise ValueError(f'{name}: recovery requires flat unhinted quadratic glyphs')
        glyph = ufo.newGlyph(name)
        glyph.width = font['hmtx'][name][0]
        glyph.unicodes = [cp for cp, mapped in cmap.items() if mapped == name]
        glyphset[name].drawPoints(glyph.getPointPen())
        glyph.lib['org.namche.originalFlags'] = list(original.flags) if original.numberOfContours else []
        index = 0
        for contour in glyph.contours:
            for point in contour.points:
                point.identifier = f'p{index}'
                index += 1
        order[name] = [[point.identifier for point in contour.points] for contour in glyph.contours]
    output.mkdir(parents=True, exist_ok=False)
    ufo.save(output / f'{style}.ufo')
    font.saveXML(output / 'variation-and-layout.ttx', skipTables=['glyf', 'loca', 'gvar'])
    font.saveXML(output / 'variations.ttx', tables=['gvar'])
    (output / 'point-order.json').write_text(json.dumps(order, indent=2) + '\n')
    manifest = dict(recovered_from=str(ttf), sha256=sha256(ttf.read_bytes()).hexdigest(),
                    repository_commit=commit, ufo=f'{style}.ufo', harfbuzz_repacker=not italic,
                    method='Recovered quadratic UFO and indexed variation/layout TTX production snapshot; not a replacement for the separate cubic design masters.',
                    table_order=list(font.reader.keys()), outputs={
                        f'variable/{ttf.name}': sha256(ttf.read_bytes()).hexdigest(),
                        f'webfonts/{woff.name}': sha256(woff.read_bytes()).hexdigest()})
    (output / 'provenance.json').write_text(json.dumps(manifest, indent=2) + '\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ttf', type=Path, required=True)
    parser.add_argument('--woff2', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--commit', required=True)
    parser.add_argument('--italic', action='store_true')
    args = parser.parse_args()
    recover(args.ttf, args.woff2, args.output, args.commit, args.italic)
