"""Measure the cubic and quadratic tangents on the compiled italic y terminal.

Compare two release directories. For each variable row, instantiate wght, save
the result as a static TTF, then reopen it to include integer point rounding.
"""

import argparse
from contextlib import contextmanager
import csv
from io import BytesIO
from itertools import takewhile
from math import atan2, degrees
from pathlib import Path

from fontTools.misc.bezierTools import cubicPointAtT, quadraticPointAtT
from fontTools.pens.basePen import BasePen
from fontTools.pens.reverseContourPen import ReverseContourPen
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont
from shapely.geometry import LineString, Point

try:
    from .check_equal_ink import VF_FILENAMES, _filled_geos, _static_path
except ImportError:
    from check_equal_ink import VF_FILENAMES, _filled_geos, _static_path


class SegmentPen(BasePen):
    """Keep individual Beziers, including implicit quadratic on-curves."""

    def __init__(self, glyphs):
        super().__init__(glyphs)
        self.contours = []

    def _moveTo(self, p):
        self.contours.append([])

    def _lineTo(self, p):
        self.contours[-1].append((self._getCurrentPoint(), p))

    def _qCurveToOne(self, c, p):
        self.contours[-1].append((self._getCurrentPoint(), c, p))

    def _curveToOne(self, c1, c2, p):
        self.contours[-1].append((self._getCurrentPoint(), c1, c2, p))


def terminal_segments(font, name='y'):
    glyphs = font.getGlyphSet()
    pen = SegmentPen(glyphs)
    glyphs[name].draw(ReverseContourPen(pen) if 'CFF ' in font else pen)
    for contour in pen.contours:
        bottom = min(s[0][1] for s in contour)
        for i, segment in enumerate(contour):
            p, q = segment[0], segment[-1]
            if len(segment) == 2 and bottom < q[1] == p[1] < 0 and q[0] > p[0]:
                curves = list(takewhile(lambda s: len(s) > 2, contour[i+1:] + contour[:i]))
                if curves:
                    return curves
    raise ValueError(f'{name}: missing terminal curve')


def maximum_tangent_break(segments):
    maximum = 0.
    for before, after in zip(segments, segments[1:]):
        c, p = before[-2:]
        q = after[1]
        x, y = p[0] - c[0], p[1] - c[1]
        u, v = q[0] - p[0], q[1] - p[1]
        maximum = max(maximum, abs(degrees(atan2(x*v - y*u, x*u + y*v))))
    return maximum


def inward_dent(segments):
    """Maximum departure from the convex hull, sampled in 32 steps per Bezier."""
    samples = []
    for segment in segments:
        evaluate = quadraticPointAtT if len(segment) == 3 else cubicPointAtT
        samples.extend(evaluate(*segment, i / 32) for i in range(32))
    samples.append(segments[-1][-1])
    hull = LineString(samples).convex_hull.boundary
    return max(hull.distance(Point(p)) for p in samples)


@contextmanager
def fixed_font(root, fmt, weight, slope='italic'):
    if fmt != 'variable':
        with TTFont(_static_path(root, slope, weight, fmt)) as font:
            yield font
        return
    with TTFont(root / 'variable' / VF_FILENAMES[slope]) as font:
        instance = instantiateVariableFont(font, {'wght': weight}, inplace=True)
        buf = BytesIO()
        instance.save(buf)
    buf.seek(0)
    with TTFont(buf) as frozen:
        yield frozen


def measure(before, after, output):
    with output.open('w', newline='') as out:
        writer = csv.writer(out, lineterminator='\n')
        writer.writerow(('weight', 'format', 'before_max_join_degrees', 'after_max_join_degrees',
                         'before_inward_dent_fu', 'after_inward_dent_fu',
                         'outline_hausdorff_fu'))
        for fmt in ('variable', 'ttf', 'otf'):
            for weight in (range(100, 901, 25) if fmt == 'variable' else (400, 500)):
                with fixed_font(before, fmt, weight) as old, fixed_font(after, fmt, weight) as new:
                    segments = [terminal_segments(f) for f in (old, new)]
                    values = [func(s) for func in (maximum_tangent_break, inward_dent) for s in segments]
                    a, b = [_filled_geos(f.getGlyphSet(), 'y', .003)[0].boundary for f in (old, new)]
                writer.writerow((weight, fmt, *(f'{x:.3f}' for x in values), f'{a.hausdorff_distance(b):.3f}'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--before', type=Path, required=True)
    parser.add_argument('--after', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    measure(args.before, args.after, args.output)


if __name__ == '__main__':
    main()
