#!/usr/bin/env python3
"""Compare compiled y edges with Michael's round-three approval image.

Use the unscaled r3_y_vorschau.png from commit 5ef6ee4c998e542f7a38c1656dd9d51aa598bdef,
documentation/proofs/issues/issue-125/runde-3. Coordinate transforms and row order
come from prototype/r3_y_cmp.py in the same revision. All errors are font units.
"""
import argparse
import csv
from hashlib import sha256
from math import sqrt
from pathlib import Path

from fontTools.ttLib import TTFont
from PIL import Image
from shapely.geometry import LineString

try:
    from .check_equal_ink import VF_FILENAMES, _filled_geos, _static_path
except ImportError:
    from check_equal_ink import VF_FILENAMES, _filled_geos, _static_path


REFERENCE_SHA256 = 'b6febe188af08403bea4d96e87ab5ab0e12c85291a799c15d37fe7d66a7cf2a0'
ROWS = [('upright', w) for w in (100, 400, 700, 900)] + [('italic', w) for w in (400, 700, 900)]


def reference_edge(image, row, style, weight):
    """Use pixel-center scanlines; the first dark pixel's left boundary estimates the edge."""
    cx = {100: 205, 400: 205, 700: 210, 900: 215}[weight] - (55 if style == 'italic' else 0)
    cy = {100: 0, 400: -20, 700: -20, 900: -10}[weight]
    top, left, scale = 60 + 264*row, 654, .95
    # Keep the arm junction and exclude the horizontal edge at the bottom
    # of its white opening, where the scanline starts following the terminal.
    bottom_y, top_y = {100: (-40, 40), 400: (-40, 40), 700: (-30, 50), 900: (-11, 50)}[weight]
    points = []
    for py in range(250):
        y = cy + (124.5 - py)/scale
        if bottom_y <= y <= top_y:
            x = next(x for x in range(250) if image.getpixel((left+x, top+py)) < 128)
            if x == 0:
                raise ValueError('reference edge touches the left crop boundary')
            points.append((cx + (x-125)/scale, y))
    return points


def edge_errors(path, weight, reference):
    with TTFont(path) as font:
        glyphs = font.getGlyphSet(location={'wght': weight} if 'fvar' in font else None)
        shape, _ = _filled_geos(glyphs, font.getBestCmap()[ord('y')], .005)
    errors = []
    for ref_x, ref_y in reference:
        cut = shape.intersection(LineString([(-1000, ref_y), (3000, ref_y)]))
        if cut.is_empty:
            raise ValueError(f'{path.name}: y does not cross scanline {ref_y}')
        errors.append(cut.bounds[0] - ref_x)
    return sqrt(sum(e*e for e in errors)/len(errors)), max(map(abs, errors))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference', type=Path, required=True)
    parser.add_argument('--previous', type=Path, required=True, help='7b47095 Sans directory with ttf/ and variable/')
    parser.add_argument('--candidate', type=Path, required=True, help='rebuilt Sans directory with ttf/ and variable/')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if sha256(args.reference.read_bytes()).hexdigest() != REFERENCE_SHA256:
        parser.error('reference PNG must match the approved 5ef6ee4c image')
    with Image.open(args.reference) as image:
        reference = image.convert('L')
    with args.output.open('w', newline='') as output:
        writer = csv.writer(output, lineterminator='\n')
        writer.writerow(('style','weight','format','scanlines','previous_rms_fu','candidate_rms_fu',
                         'previous_max_fu','candidate_max_fu'))
        for row, (style, weight) in enumerate(ROWS):
            points = reference_edge(reference, row, style, weight)
            for fmt in ('variable', 'static'):
                paths = [root/'variable'/VF_FILENAMES[style] if fmt == 'variable' else
                         _static_path(root, style, weight) for root in (args.previous, args.candidate)]
                (old, old_max), (new, new_max) = [edge_errors(p, weight, points) for p in paths]
                writer.writerow((style, weight, fmt, len(points), f'{old:.3f}', f'{new:.3f}',
                                 f'{old_max:.3f}', f'{new_max:.3f}'))


if __name__ == '__main__':
    main()
