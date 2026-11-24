#!/usr/bin/env python3
"""Measure the ten reviewed lowercase glyphs against bundled Geist at matching VF weights.

Each glyph contributes once to the total. Match Michael's r3_sheets.py proof
by summing grayscale coverage at one pixel per font unit for each compiled
nonzero-filled outline. This compares the silhouette independently of hinting.
"""

import argparse
import csv
from contextlib import ExitStack
from pathlib import Path

import skia
from fontTools.pens.basePen import BasePen
from fontTools.ttLib import TTFont

try:
    from .check_equal_ink import VF_FILENAMES
except ImportError:
    from check_equal_ink import VF_FILENAMES


GLYPHS = 'abdhmnpqru'
WEIGHTS = (100, 150, 200, 250, 300, 350, 400, 500, 600, 700, 800, 900)
GEIST_VF = {'upright': 'Geist-Variable.woff2', 'italic': 'Geist-Italic[wght].woff2'}


class CoveragePen(BasePen):
    def __init__(self, glyphs):
        super().__init__(glyphs)
        self.path = skia.Path()

    def _moveTo(self, p):
        self.path.moveTo(*p)

    def _lineTo(self, p):
        self.path.lineTo(*p)

    def _qCurveToOne(self, a, b):
        self.path.quadTo(*a, *b)

    def _curveToOne(self, a, b, c):
        self.path.cubicTo(*a, *b, *c)

    def _closePath(self):
        self.path.close()


def filled_areas(font, weight):
    if font['head'].unitsPerEm != 1000:
        raise ValueError('Expected the Geist 1000-unit design grid')
    glyphs = font.getGlyphSet(location={'wght': weight})
    cmap = font.getBestCmap()
    surface = skia.Surface(1400, 1400)
    canvas = surface.getCanvas()
    canvas.translate(200, 1100)
    canvas.scale(1, -1)
    ink = skia.Paint(Color=skia.ColorWHITE, AntiAlias=True)
    areas = {}
    for char in GLYPHS:
        pen = CoveragePen(glyphs)
        glyphs[cmap[ord(char)]].draw(pen)
        canvas.clear(skia.ColorBLACK)
        canvas.drawPath(pen.path, ink)
        areas[char] = float(surface.makeImageSnapshot().toarray()[:, :, 0].sum()) / 255
    areas['total'] = sum(areas.values())
    return areas


def measure(geist_webfonts, historical, round2, round3, output):
    fields = ['slope', 'weight', 'glyph', 'geist_area', 'historical_added_ink',
              'round2_added_ink', 'round3_added_ink']
    with output.open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator='\n')
        writer.writeheader()
        for slope, filename in VF_FILENAMES.items():
            with ExitStack() as stack:
                geist = stack.enter_context(TTFont(geist_webfonts / GEIST_VF[slope]))
                snapshots = {name: stack.enter_context(TTFont(root / 'variable' / filename))
                             for name, root in (('historical', historical), ('round2', round2),
                                                ('round3', round3))}
                for weight in WEIGHTS:
                    baseline = filled_areas(geist, weight)
                    snapshots_at_weight = {name: filled_areas(font, weight)
                                           for name, font in snapshots.items()}
                    for glyph, area in baseline.items():
                        row = {'slope': slope, 'weight': weight, 'glyph': glyph, 'geist_area': round(area, 2)}
                        row.update({f'{name}_added_ink': round(values[glyph] - area, 2)
                                    for name, values in snapshots_at_weight.items()})
                        writer.writerow(row)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--geist-webfonts', type=Path, default=Path('fonts/Geist/webfonts'))
    parser.add_argument('--historical', type=Path, required=True, help='Pre-PR Latin Core Sans family root')
    parser.add_argument('--round2', type=Path, required=True, help='PR 7b47095 Sans family root')
    parser.add_argument('--round3', type=Path, required=True, help='Revised Sans family root')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    measure(args.geist_webfonts, args.historical, args.round2, args.round3, args.output)
