"""Preserve reviewed smooth contacts when cubic contours are quantized for release."""

from bisect import bisect_left, bisect_right
from math import dist

from fontTools.pens.recordingPen import RecordingPen
from fontTools.pens.t2CharStringPen import T2CharStringPen


Y_FORMS = ('y', 'yacute', 'ycircumflex', 'ydieresis', 'ygrave', 'ydieresis.ss08')


def imply_glyf_oncurves(font, name, indices):
    """Use the implicit midpoints of the adjoining quadratic controls.

    Keep the deltas for all surviving points, including metric phantom points.
    IUP must be evaluated on the old contour before its point numbers change.
    """
    glyf = font['glyf']
    glyph = glyf[name]
    indices = sorted(set(indices))
    if not indices:
        return
    ends = glyph.endPtsOfContours
    if indices[0] < 0 or indices[-1] > ends[-1]:
        raise ValueError(f'{name} point number outside its contours')
    for index in indices:
        contour = bisect_left(ends, index)
        start = ends[contour - 1] + 1 if contour else 0
        end = ends[contour]
        prev = index - 1 if index > start else end
        following = index + 1 if index < end else start
        if not glyph.flags[index] & 1 or glyph.flags[prev] & 1 or glyph.flags[following] & 1:
            raise ValueError(f'{name} point {index} is not a join between quadratic controls')
        if index == start and glyph.flags[index] & 64:
            glyph.flags[following] |= 64  # TrueType's OVERLAP_SIMPLE flag
    if 'gvar' in font:
        coordinates, controls = glyf._getCoordinatesAndControls(
            name, font['hmtx'].metrics, getattr(font.get('vmtx'), 'metrics', None))
        for variation in font['gvar'].variations.get(name, []):
            variation.calcInferredDeltas(coordinates, controls.endPts)
            if len(variation.coordinates) != len(coordinates):
                raise ValueError(f'{name} variation has a different point count')
            for index in reversed(indices):
                del variation.coordinates[index]
    for index in reversed(indices):
        del glyph.coordinates[index]
        del glyph.flags[index]
    glyph.endPtsOfContours = [end - bisect_right(indices, end) for end in ends]


def _y_quadratic_contacts(glyph):
    """Find the inner horizontal terminal, then follow it up to the long arm."""
    start = 0
    for end in glyph.endPtsOfContours:
        indices = list(range(start, end + 1))
        start = end + 1
        points = glyph.coordinates
        bottom = min(points[i][1] for i in indices)
        for position, first in enumerate(indices):
            # Rotate the contour to its short, rightward flat above the baseline
            # of the descender. The outside of the tail has its flat at bottom.
            cycle = indices[position:] + indices[:position]
            last = cycle[1]
            x, y = points[first]
            if not (glyph.flags[first] & 1 and glyph.flags[last] & 1
                    and bottom < y < 0 and points[last][1] == y and points[last][0] > x):
                continue
            joins = []
            for offset, i in enumerate(cycle[2:], 2):
                if glyph.flags[i] & 1:
                    if glyph.flags[cycle[(offset + 1) % len(cycle)]] & 1:
                        break
                    joins.append(i)
            if len(joins) == 3:
                return joins
    raise ValueError('expected three cubic-to-quadratic contacts on the inner y tail')


def _smooth_cff_y(font, name):
    """Project the cubic contacts onto their handle chords on CFF's 16.16 grid."""
    cff = font['CFF '].cff
    strings = cff.topDictIndex[0].CharStrings
    charstring = strings[name]
    recording = RecordingPen()
    charstring.draw(recording)
    commands = recording.value
    # CFF's winding follows the arm down to the leftward terminal flat.
    terminals = [i for i, (op, args) in enumerate(commands) if i >= 4 and op == 'lineTo'
                 and all(cmd == 'curveTo' for cmd, _ in commands[i-4:i])
                 and commands[i-1][1][-1][1] == args[0][1] < 0
                 and commands[i-1][1][-1][0] > args[0][0]]
    if len(terminals) != 1:
        raise ValueError(f'{name}: expected four cubics before the inner terminal')
    terminal = terminals[0]
    for i in range(terminal - 4, terminal - 1):
        c1, incoming, point = commands[i][1]
        outgoing = commands[i + 1][1][0]
        dx, dy = outgoing[0] - incoming[0], outgoing[1] - incoming[1]
        t = ((point[0] - incoming[0])*dx + (point[1] - incoming[1])*dy) / (dx*dx + dy*dy)
        # A common binary fraction keeps both coordinates on the same straight
        # line even after Type 2 charstring serialization.
        t = round(t * 65536) / 65536
        projected = incoming[0] + t*dx, incoming[1] + t*dy
        if not 0 < t < 1 or dist(point, projected) > 1:
            raise ValueError(f'{name}: cubic handle projection exceeds the rounding error')
        commands[i] = 'curveTo', (c1, incoming, projected)
    pen = T2CharStringPen(font['hmtx'][name][0] - charstring.private.nominalWidthX,
                          font.getGlyphSet(), roundTolerance=0)
    recording.replay(pen)
    strings[name] = pen.getCharString(private=charstring.private, globalSubrs=cff.GlobalSubrs)


def smooth_italic_y(font):
    """Share tangents before the italic y terminal, including flattened accents."""
    if not font['post'].italicAngle or ('fvar' not in font and font['OS/2'].usWeightClass not in (400, 500)):
        return []
    changed = []
    for name in Y_FORMS:
        if 'glyf' in font:
            glyph = font['glyf'][name]
            if glyph.isComposite():
                if not any(c.glyphName == 'y' for c in glyph.components):
                    raise ValueError(f'{name} does not inherit its base outline from y')
                continue
            imply_glyf_oncurves(font, name, _y_quadratic_contacts(glyph))
        else:
            _smooth_cff_y(font, name)
        changed.append(name)
    return changed
