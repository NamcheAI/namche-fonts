"""Keep the baked exterior fillets tangent on the exported quadratic and CFF grids."""
from functools import lru_cache
from itertools import product
from math import dist
from pathlib import Path

import numpy as np
from fontTools.misc.transform import Transform
from fontTools.pens.recordingPen import RecordingPointPen
from fontTools.pens.pointPen import PointToSegmentPen
from fontTools.pens.t2CharStringPen import T2CharStringPen
from glyphsLib import GSFont
from glyphsLib.glyphdata import get_glyph

from scripts.equal_ink_corners import LIGHTER_SPURS
from scripts.round_inner_corners import nodes_to_segments, seg_tangent_in, seg_tangent_out, dot, cross

# _arc draws two equal-angle cubic pieces with four equal-length handles.
# Glyphs packages serialize their controls to five decimal places.
HANDLE_PRECISION = .001
GRID_STEPS = np.array(sorted(product((-1, 0, 1), repeat=4),
                             key=lambda v: sum(d*d for d in v))).reshape(-1, 2, 2)


def _arc_handle(segment):
    if segment[0] != 'curve':
        return None
    a, b, c, d = segment[1:]
    size = dist(a, b)
    if abs(size - dist(c, d)) > HANDLE_PRECISION:
        return None
    return size if cross(seg_tangent_out(segment), seg_tangent_in(segment)) < 0 else None


def _source_contacts(layer, base):
    from scripts.build_sans_equal_ink import contours

    # The rounded exterior is the first contour in the clean design sources.
    outline = nodes_to_segments(contours(layer)[0])
    out = []
    pairs = 0
    for i, left in enumerate(outline):
        right = outline[(i + 1) % len(outline)]
        size, other = _arc_handle(left), _arc_handle(right)
        if size is None or other is None or abs(size - other) > HANDLE_PRECISION:
            continue
        if dot(seg_tangent_in(left), seg_tangent_out(right)) < .999999:
            continue
        pairs += 1
        for j in (i, i + 1, i + 2):
            previous, following = outline[(j-1) % len(outline)], outline[j % len(outline)]
            t = seg_tangent_out(following)
            if dot(seg_tangent_in(previous), t) < .999999:
                raise ValueError(f'{layer.parent.name}: baked fillet lost tangency')
            out.append((following[1], t, previous[0] == following[0] == 'curve'))
    expected = 2 if base in 'abdmpq' else 1
    if pairs != expected:
        raise ValueError(f'{layer.parent.name}: expected {expected} exterior fillets, found {pairs}')
    return out


@lru_cache(maxsize=2)
def source_contacts(package: Path):
    """Carry each reviewed contact through the source component tree and production names."""
    glyphs = GSFont(package)
    result = {}
    for master in glyphs.masters:
        weight = int(master.axes[0])
        if weight % 100:
            continue
        @lru_cache(maxsize=None)
        def contacts(name):
            layer = glyphs.glyphs[name].layers[master.id]
            base = name.split('.')[0]
            out = _source_contacts(layer, base) if base in LIGHTER_SPURS and layer.paths else []
            for component in layer.components:
                transform = Transform(*component.transform)
                for p, t, curved in contacts(component.name):
                    out.append((transform.transformPoint(p), transform.transformVector(t), curved))
            return out
        by_name = {}
        for glyph in glyphs.glyphs:
            anchors = contacts(glyph.name)
            if anchors:
                name = glyph.production or get_glyph(glyph.name).production_name or glyph.name
                by_name[name] = anchors
        result[weight] = by_name
        contacts.cache_clear()
    return result


def _match(points, location, name):
    # All release masters use a 1000-unit em. An independently quantized
    # export may round its x and y by half a grid unit each; CFF overlap
    # removal can round twice. More than a diagonal grid step is ambiguous.
    found = [idx for idx, point in points if dist(point, location) <= 1.5]
    if len(found) != 1:
        raise ValueError(f'{name}: expected one compiled fillet contact near {location}, found {found}')
    return found[0]


def _fit_scores(points, on, at):
    """Fit the implied join to the original two quadratic arcs in their normal direction."""
    p2, p, q, r, r2 = (np.asarray(points[(at+i) % len(points)]) for i in (-2, -1, 0, 1, 2))
    left, right = p + GRID_STEPS[:, 0], r + GRID_STEPS[:, 1]
    middle = (left + right) * .5
    first_explicit = on[(at-2) % len(points)] & 1
    last_explicit = on[(at+2) % len(points)] & 1
    a = p2 if first_explicit else (p2+p)*.5
    b = r2 if last_explicit else (r2+r)*.5
    new_a = p2 if first_explicit else (p2+left)*.5
    new_b = r2 if last_explicit else (r2+right)*.5
    loss = np.zeros(len(GRID_STEPS))
    for start, control, end, x, y, z in ((a, p, q, new_a, left, middle),
                                         (q, r, b, middle, right, new_b)):
        for t in (.05, .15, .25, .35, .45, .55, .65, .75, .85, .95):
            tangent = (1-t)*(control-start) + t*(end-control)
            speed = np.linalg.norm(tangent)
            if speed == 0:
                raise ValueError('degenerate quadratic at a reviewed fillet')
            delta = (1-t)**2*(x-start) + 2*(1-t)*t*(y-control) + t*t*(z-end)
            # Squared normal displacement integrated in arc length. A knot can
            # move along a curve when its parameterization changes.
            loss += (delta[:, 0]*tangent[1] - delta[:, 1]*tangent[0])**2 / speed
    return loss


def _smooth_quadratic(font, name, contacts):
    from scripts.equal_ink_tangents import imply_glyf_oncurves

    glyf = font['glyf']
    glyph = glyf[name]
    if glyph.isComposite():
        return 0  # Its base outline carries the correction.
    coords, ends, flags = glyph.getCoordinates(glyf)
    explicit = [(i, p) for i, p in enumerate(coords) if flags[i] & 1]
    knots = sorted({_match(explicit, p, name) for p, _, curved in contacts if curved})
    variable = 'gvar' in font
    # A shared correction applies to all locations. Give the approved Thin
    # silhouette equal importance to the four other design samples together.
    samples = [font.getGlyphSet(location={'wght': w})[name]._getGlyphAndOffset()[0]
               .getCoordinates(glyf)[0] for w in (100, 200, 300, 400, 900)] if variable else [coords]
    offsets = {}
    for k in knots:
        ci = next(i for i, end in enumerate(ends) if k <= end)
        start = ends[ci-1]+1 if ci else 0
        stop = ends[ci]+1
        n, at = stop-start, k-start
        if any(flags[start+(at+d) % n] & 1 for d in (-1, 1)):
            raise ValueError(f'{name}: source curve-to-curve contact {k} has no quadratic handles')
        scores = [_fit_scores(row[start:stop], flags[start:stop], at) for row in samples]
        score = np.average(scores, axis=0, weights=(4, 1, 1, 1, 1) if variable else None)
        # Resolve machine-precision ties by the stable, smallest-move order.
        fit = GRID_STEPS[np.round(score, 8).argmin()]
        for d, step in zip((-1, 1), fit):
            i = start+(at+d) % n
            if i in offsets:
                # A single-control span shares a handle between both contacts.
                # Both adjustments are bounded and the shared implied curve is
                # smooth regardless of which of the two normal fits is used.
                continue
            offsets[i] = step
    # Expand any inferred variation coordinates against the original base
    # inside the helper before moving the surviving controls.
    imply_glyf_oncurves(font, name, knots)
    for old, step in offsets.items():
        i = old - sum(k < old for k in knots)
        x, y = glyph.coordinates[i]
        glyph.coordinates[i] = (x + int(step[0]), y + int(step[1]))
    return len(knots)


def _smooth_cff(font, name, contacts):
    glyphs = font.getGlyphSet()
    recording = RecordingPointPen()
    glyphs[name].drawPoints(recording)
    contours, contour = [], []
    for op, args, _ in recording.value:
        if op == 'beginPath':
            contour = []
        elif op == 'addPoint':
            contour.append([args[0], args[1]])
        elif op == 'endPath':
            contours.append(contour)
    explicit = [((ci, i), p) for ci, c in enumerate(contours) for i, (p, kind) in enumerate(c) if kind]
    for p, tangent, _ in contacts:
        ci, i = _match(explicit, p, name)
        c = contours[ci]
        q = np.asarray(c[i][0])
        prev, after = c[i-1], c[(i+1) % len(c)]
        direction = np.asarray(tangent)
        if prev[1]:
            direction = q-prev[0]
        elif after[1]:
            direction = np.asarray(after[0])-q
        direction = direction / np.linalg.norm(direction)
        for handle in (prev, after):
            if handle[1] is None:
                projected = q + direction*np.dot(np.asarray(handle[0])-q, direction)
                # Type 2 stores relative deltas. Snap the absolute coordinate
                # first so fractional deltas telescope exactly at contour closure.
                handle[0] = tuple(np.round(projected * 65536) / 65536)
    top = font['CFF '].cff.topDictIndex[0]
    old = top.CharStrings[name]
    pen = T2CharStringPen(font['hmtx'][name][0]-old.private.nominalWidthX, glyphs, roundTolerance=0)
    point_pen = PointToSegmentPen(pen)
    for c in contours:
        point_pen.beginPath()
        for p, kind in c:
            point_pen.addPoint(p, segmentType=kind)
        point_pen.endPath()
    top.CharStrings[name] = pen.getCharString(private=old.private, globalSubrs=old.globalSubrs)
    return len(contacts)


def smooth_lowercase_fillets(font, sources):
    """Apply source tangent directions at the actual exported fillet contacts."""
    weight = int(font['OS/2'].usWeightClass)
    if 'fvar' not in font and weight >= 400:
        return {}
    contacts = sources[weight]
    if missing := contacts.keys() - set(font.getGlyphOrder()):
        raise ValueError(f'reviewed lowercase glyphs missing from compiled font: {sorted(missing)}')
    smooth = _smooth_quadratic if 'glyf' in font else _smooth_cff
    return {name: smooth(font, name, nodes) for name, nodes in contacts.items()}
