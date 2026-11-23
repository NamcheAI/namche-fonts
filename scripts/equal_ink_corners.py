"""Compatible, additive inner fillets for clean, unrounded cubic masters.

The VFs and statics share the rounded boundaries and local curve guards. Fillets are
solved on the *actual* adjacent Beziers, not their tangent-line extensions.
Acute joins solve the boolean added ink area numerically; obtuse joins retain
r90. Reviewed exterior lowercase spurs have a longer flank allowance.
The historical italic recipe remains in round_inner_corners.py.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

import pathops
from fontTools.misc import bezierTools
from fontTools.pens.recordingPen import RecordingPen
from fontTools.pens.areaPen import AreaPen

try:  # Supports both `python scripts/build_...py` and package imports.
    from .round_inner_corners import (
        Node, Point, Segment, add, sub, mul, dot, cross, norm, dist,
        nodes_to_segments, segments_to_nodes, nodes_to_pathops, path_depth_map, recording_to_node_paths,
        seg_start, seg_end, seg_length, seg_tangent_in, seg_tangent_out,
        _cubic_split_t_for_arclen,
    )
except ImportError:
    from round_inner_corners import (
        Node, Point, Segment, add, sub, mul, dot, cross, norm, dist,
        nodes_to_segments, segments_to_nodes, nodes_to_pathops, path_depth_map, recording_to_node_paths,
        seg_start, seg_end, seg_length, seg_tangent_in, seg_tangent_out,
        _cubic_split_t_for_arclen,
    )

F90 = 1.0 - math.pi / 4.0
FLANK_FRACTION = 0.45
AREA_TOLERANCE = 0.05  # aggregate square font units; pathops uses float32 geometry
LOCAL_LOSS_TOLERANCE = 0.0001
MIN_ADDED_AREA = 1.0  # Subunit changes are not stable on the integer TrueType lattice.
MIN_COMPATIBLE_FILLET_AREA = 1.0  # One square unit: the integer TrueType coordinate lattice.
LIGHTER_SPURS = frozenset("abdhmnpqru")


def spur_floor_at(weight):
    """Michael's minimum radius for the ten reviewed exterior lowercase joins."""
    if weight >= 400:
        return .60
    return .40 + .20 * max(0., weight - 100) / 300


# Short curved flanks in these outlines change shape between solved masters.
# Keep the original curve locally. The eight needs continuous rounded counters:
# disconnected patches at its waist can acquire small white pockets in TrueType.
LOCAL_GUARDS = {
    ('Upright', 'three'): 'fillets', ('Upright', 'threesuperior'): 'fillets',
    ('Upright', 'at'): 'fillets', ('-Italic', 'at'): 'fillets',
    ('Upright', 'eight'): 'flanks', ('-Italic', 'eight'): 'flanks',
}


def r90_for_stem(stem: float, uppercase_or_figure: bool = False) -> float:
    """Issue #125: c=1.6, capped at 70 for capitals/figures, otherwise 53."""
    if not math.isfinite(stem) or stem <= 0:
        raise ValueError("stem must be finite and positive")
    return min(1.6 * stem, 70.0 if uppercase_or_figure else 53.0)


def _path(contours):
    p = pathops.Path()
    for nodes in contours:
        p.addPath(nodes_to_pathops(nodes))
    return p


def _op(a, b, operation):
    return pathops.op(a, b, operation, fix_winding=True)


def _counter_count(path):
    filled = pathops.simplify(path, fix_winding=True, clockwise=False)
    return sum(contour.clockwise for contour in filled.contours)


def _reverse(segs):
    return [tuple([s[0], *reversed(s[1:])]) for s in reversed(segs)]


def _normalize(contours):
    paths = [nodes_to_pathops(c) for c in contours]
    depths = path_depth_map(paths)
    # A black island can cross a white counter while remaining within its
    # outer contour (the slash in zerosuperior). Nesting parity alone calls
    # that island a hole. For such nonzero overlap geometry retain relative
    # source winding, normalized globally by the largest outer contour.
    overlaps = False
    for i, a in enumerate(paths):
        for b in paths[i+1:]:
            shared = _op(a, b, pathops.PathOp.INTERSECTION).area
            if AREA_TOLERANCE < shared < min(a.area, b.area)-AREA_TOLERANCE:
                overlaps = True
    reverse_all = paths[max(range(len(paths)), key=lambda i: paths[i].area)].clockwise if paths else False
    result = []
    for nodes, path, depth in zip(contours, paths, depths):
        segs = nodes_to_segments(nodes)
        want_positive = depth % 2 == 0
        # Path.area is unsigned in skia-pathops, including for clockwise
        # counters. Winding must be read explicitly or every hole is filled.
        reverse = reverse_all if overlaps else (not path.clockwise) != want_positive
        if reverse:
            segs = _reverse(segs)
        result.append(segs)
    return result


def resolve_clean_contours(contours: Sequence[Sequence[Node]]):
    """Resolve the complete nonzero filled region without discarding islands.

    Holes, islands inside holes and further nested counters all participate in
    one compound path. Overlapping additive shapes retain relative winding.
    This replaces the legacy outer-minus-first-level-holes merge, which loses
    the C/R in copyright/registered and crossing bars in .notdef.
    """
    if not contours:
        return []
    compound = _path([segments_to_nodes(c) for c in _normalize(contours)])
    filled = pathops.simplify(compound, fix_winding=True, clockwise=False)
    recording = RecordingPen()
    filled.draw(recording)
    return [_drop_duplicate_closure(nodes) for nodes in recording_to_node_paths(recording)]


def _nodes_preserving_segment_start(segments):
    nodes = segments_to_nodes(segments)
    # segments_to_nodes starts with segment 0's END, whereas the matcher uses
    # its START. Move the final endpoint to the front; closing cubic handles
    # remain at the end and retain their exact cyclic meaning.
    return nodes[-1:]+nodes[:-1] if nodes else nodes


def _drop_duplicate_closure(nodes):
    """Remove the repeated move-to endpoint without losing a closing cubic."""
    nodes = list(nodes)
    if len(nodes) > 1 and nodes[0][2] != 'o' and nodes[-1][2] != 'o' and dist(nodes[0][:2], nodes[-1][:2]) < 1e-8:
        nodes[0] = (nodes[0][0], nodes[0][1], nodes[-1][2])
        nodes.pop()
    return nodes


def _raw_boundaries_are_simple(contours):
    from shapely.geometry import LineString
    try:
        from .check_equal_ink import _FlattenPen
    except ImportError:
        from check_equal_ink import _FlattenPen
    pen = _FlattenPen(.01)
    _NodeGlyph(contours).draw(pen)
    boundaries = [LineString(points) for points in pen.contours]
    return all(line.is_simple for line in boundaries) and not any(
        a.intersects(b) for i, a in enumerate(boundaries) for b in boundaries[i+1:])


def _topology(contours):
    return [[segment[0] for segment in nodes_to_segments(contour)] for contour in contours]


def _alignment_bounds(contour):
    points = [point for segment in nodes_to_segments(contour) for point in segment[1:]]
    return min(p[0] for p in points), min(p[1] for p in points), max(p[0] for p in points), max(p[1] for p in points)


def _best_cyclic_alignment(reference, candidate):
    ref = nodes_to_segments(reference)
    other = nodes_to_segments(candidate)
    if len(ref) != len(other) or nodes_to_pathops(reference).clockwise != nodes_to_pathops(candidate).clockwise:
        return math.inf, None, None
    def normalized(segs):
        points = [p for s in segs for p in s[1:]]
        x0, y0 = min(p[0] for p in points), min(p[1] for p in points)
        w, h = max(p[0] for p in points)-x0, max(p[1] for p in points)-y0
        return [[((p[0]-x0)/max(w, 1), (p[1]-y0)/max(h, 1)) for p in s[1:]] for s in segs]
    normal_ref, normal_other = normalized(ref), normalized(other)
    best = (math.inf, None, None)
    for shift in range(len(other)):
        shifted = other[shift:]+other[:shift]
        if [s[0] for s in shifted] != [s[0] for s in ref]:
            continue
        points = normal_other[shift:]+normal_other[:shift]
        cost = sum((a[0]-b[0])**2+(a[1]-b[1])**2
                   for left, right in zip(normal_ref, points) for a, b in zip(left, right))
        if cost < best[0]:
            best = cost, shifted, shift
    return best


def _align_resolved_masters(masters):
    """Match contour identity and cyclic phase, not just node-type signatures."""
    import itertools
    aligned, changes = [masters[0]], []
    for mi, candidates in enumerate(masters[1:], 1):
        reference = aligned[-1]
        if len(candidates) != len(reference):
            raise ValueError('resolved contour counts differ across masters')
        count = len(reference)
        all_bounds = [_alignment_bounds(c) for c in reference+candidates]
        scale = max(1, max(b[2] for b in all_bounds)-min(b[0] for b in all_bounds),
                    max(b[3] for b in all_bounds)-min(b[1] for b in all_bounds))
        matrix = []
        for ref in reference:
            rb = _alignment_bounds(ref)
            row = []
            for candidate in candidates:
                cb = _alignment_bounds(candidate)
                phase_cost, shifted, shift = _best_cyclic_alignment(ref, candidate)
                center_cost = (((rb[0]+rb[2]-cb[0]-cb[2])/2)**2+
                               ((rb[1]+rb[3]-cb[1]-cb[3])/2)**2)/scale**2
                size_cost = ((rb[2]-rb[0]-(cb[2]-cb[0]))**2+
                             (rb[3]-rb[1]-(cb[3]-cb[1]))**2)/scale**2
                row.append((10*center_cost+.1*size_cost+.01*phase_cost, shifted, shift))
            matrix.append(row)
        order = min(itertools.permutations(range(count)),
                    key=lambda permutation: sum(matrix[i][j][0] for i, j in enumerate(permutation)))
        if not math.isfinite(sum(matrix[i][j][0] for i, j in enumerate(order))):
            raise ValueError('resolved contours have no compatible winding and cyclic topology')
        aligned.append([_nodes_preserving_segment_start(matrix[i][j][1]) for i, j in enumerate(order)])
        changes.append(dict(master=mi, contour_order=list(order),
                            segment_rotations=[matrix[i][j][2] for i, j in enumerate(order)]))
    return aligned, changes


def resolve_compatible_clean_contours(master_contours):
    """Resolve clean master inputs while preserving authored correspondence.

    Boolean simplification independently reorders contours and chooses starts;
    equal node-type signatures do not prevent one percent ring interpolating
    into the other. Preserve already simple/disjoint authored paths. For actual
    overlap geometry, resolve the full nonzero compound and match contour
    identity plus cyclic phase. Return (masters, normalization evidence).
    """
    normalized = [[_nodes_preserving_segment_start(c) for c in _normalize(master)] for master in master_contours]
    if not normalized or not any(normalized):
        return normalized, dict(method='empty')
    raw_compatible = all(_topology(master) == _topology(normalized[0]) for master in normalized)
    if raw_compatible and all(_raw_boundaries_are_simple(master) for master in normalized):
        return normalized, dict(method='authored_simple_correspondence')
    resolved = [resolve_clean_contours(master) for master in normalized]
    try:
        aligned, changes = _align_resolved_masters(resolved)
        return aligned, dict(method='resolved_matched_correspondence', alignment=changes)
    except ValueError as error:
        if not raw_compatible:
            raise ValueError(f'clean inputs require an explicit topology repair: {error}') from error
        return normalized, dict(method='authored_overlap_correspondence', reason=str(error))


def _point(seg, t):
    if seg[0] == "line":
        return add(seg[1], mul(sub(seg[2], seg[1]), t))
    a, b, c, d = seg[1:]
    s = 1 - t
    return (s*s*s*a[0]+3*s*s*t*b[0]+3*s*t*t*c[0]+t*t*t*d[0],
            s*s*s*a[1]+3*s*s*t*b[1]+3*s*t*t*c[1]+t*t*t*d[1])


def _tangent(seg, t):
    if seg[0] == "line":
        return norm(sub(seg[2], seg[1]))
    a, b, c, d = seg[1:]
    s = 1-t
    v = add(add(mul(sub(b, a), 3*s*s), mul(sub(c, b), 6*s*t)),
            mul(sub(d, c), 3*t*t))
    if math.hypot(*v) < 1e-10:
        return seg_tangent_out(seg) if t < 0.5 else seg_tangent_in(seg)
    return norm(v)


def _portion(seg, start=0.0, end=1.0):
    if seg[0] == "line":
        return ("line", _point(seg, start), _point(seg, end))
    points = seg[1:]
    if end < 1:
        points = bezierTools.splitCubicAtT(*points, end)[0]
    if start > 0:
        points = bezierTools.splitCubicAtT(*points, start/end)[1]
    return ("curve", *points)


def _parameter_limit(seg, at_end, fraction=FLANK_FRACTION):
    if seg[0] == "line":
        return fraction
    t = _cubic_split_t_for_arclen(seg, fraction*seg_length(seg), not at_end)
    return 1-t if at_end else t


def _offset(seg, t, radius):
    p, u = _point(seg, t), _tangent(seg, t)
    return add(p, mul((u[1], -u[0]), radius))


def _circle(a, b, radius, phi, limits=(FLANK_FRACTION, FLANK_FRACTION)):
    """Find circle tangent to both real flanks, within their arc-length bounds."""
    ma, mb = _parameter_limit(a, True, limits[0]), _parameter_limit(b, False, limits[1])
    trim = radius * math.tan(phi/2)
    x = min(ma, trim / max(seg_length(a), 1e-10))
    y = min(mb, trim / max(seg_length(b), 1e-10))
    def residual(x, y):
        return sub(_offset(a, 1-x, radius), _offset(b, y, radius))
    for _ in range(35):
        f = residual(x, y)
        error = math.hypot(*f)
        if error < 2e-6:
            p, q = _point(a, 1-x), _point(b, y)
            center = mul(add(_offset(a, 1-x, radius), _offset(b, y, radius)), .5)
            return x, y, _arc(p, q, center, radius)
        eps = 1e-5
        fx = mul(sub(residual(x+eps, y), residual(x-eps, y)), .5/eps)
        fy = mul(sub(residual(x, y+eps), residual(x, y-eps)), .5/eps)
        den = cross(fx, fy)
        if abs(den) < 1e-12:
            return None
        dx, dy = -cross(f, fy)/den, -cross(fx, f)/den
        accepted = False
        for power in range(15):
            step = 0.5**power
            nx, ny = x+step*dx, y+step*dy
            if 0 < nx <= ma+1e-10 and 0 < ny <= mb+1e-10:
                nf = residual(nx, ny)
                if math.hypot(*nf) < error:
                    x, y, accepted = nx, ny, True
                    break
        if not accepted:
            return None
    return None


def _arc(p, q, center, radius):
    """Two clockwise cubic pieces, even for an almost flat join."""
    angle = math.atan2(p[1]-center[1], p[0]-center[0])
    finish = math.atan2(q[1]-center[1], q[0]-center[0])
    sweep = (finish-angle) % (2*math.pi)
    if sweep > 0:
        sweep -= 2*math.pi
    if abs(sweep) > math.pi + 1e-5:
        raise ValueError("fillet offset solution follows the wrong circle branch")
    step = sweep/2
    h = radius*(4/3)*math.tan(abs(step)/4)
    result = []
    start = p
    for part in range(2):
        aa, ab = angle+part*step, angle+(part+1)*step
        end = q if part == 1 else add(center, (radius*math.cos(ab), radius*math.sin(ab)))
        ta, tb = (math.sin(aa), -math.cos(aa)), (math.sin(ab), -math.cos(ab))
        result.append(("curve", start, add(start, mul(ta, h)), sub(end, mul(tb, h)), end))
        start = end
    return result


@dataclass
class Fillet:
    incoming: float
    outgoing: float
    bridges: list
    radius: float
    area: float
    target: float
    capped: bool
    tangent_run_limit: float | None = None


def _changed(contours, ci, j, solution, as_nodes=False):
    """One local replacement, used only to measure its real boolean effect."""
    output = []
    for index, segs in enumerate(contours):
        if index != ci:
            output.append(segments_to_nodes(segs))
            continue
        n = len(segs)
        result = []
        for k, seg in enumerate(segs):
            start = solution[1] if k == (j+1) % n else 0
            end = 1-solution[0] if k == j else 1
            result.append(_portion(seg, start, end))
            if k == j:
                result.extend(solution[2])
        output.append(segments_to_nodes(result))
    return output if as_nodes else _path(output)


def _free_run(segments, join, direction):
    """Prototype chord lengths up to the next change in tangent of at least 12°."""
    k = join + 1 if direction == 1 else join
    total = 0.
    for _ in segments:
        segment = segments[k % len(segments)]
        total += dist(seg_start(segment), seg_end(segment))
        end = k if direction == 1 else k - 1
        left = seg_tangent_in(segments[end % len(segments)])
        right = seg_tangent_out(segments[(end + 1) % len(segments)])
        if abs(math.atan2(cross(left, right), dot(left, right))) >= math.radians(12):
            break
        k += direction
    return total


def _solve(contours, ci, j, radius, base, diagnostic=None, *, spur_floor=0., counter_scale=1.0):
    segs = contours[ci]
    a, b = segs[j], segs[(j+1) % len(segs)]
    u, v = seg_tangent_in(a), seg_tangent_out(b)
    turn = math.atan2(cross(u, v), dot(u, v))
    if turn >= -math.radians(.1) or turn <= -math.pi+1e-5:
        return None
    phi = -turn
    acute = phi > math.pi/2 + 1e-8
    if acute:
        radius *= counter_scale
    target = F90*radius*radius
    # Both ends of a segment may have fillets. Only extend a flank if its
    # other end cannot consume it too. This keeps a positive original run.
    limits = [FLANK_FRACTION, FLANK_FRACTION]
    minimum = 0.
    soft_spur = spur_floor > 0 and acute
    if soft_spur:
        minimum = spur_floor * radius
        for side, k in enumerate(((j-1) % len(segs), (j+1) % len(segs))):
            t1, t2 = seg_tangent_in(segs[k]), seg_tangent_out(segs[(k+1) % len(segs)])
            if math.atan2(cross(t1, t2), dot(t1, t2)) >= -math.radians(.1):
                limits[side] = .90
    robust_base = None
    def candidate(r):
        nonlocal robust_base
        try:
            solution = _circle(a, b, r, phi, limits)
        except ValueError:
            return None
        if solution is None:
            if diagnostic is not None:
                diagnostic["reason"] = "no_tangent_circle_within_flank_limits"
            return None
        changed = _changed(contours, ci, j, solution)
        loss = abs(_op(base, changed, pathops.PathOp.DIFFERENCE).area)
        if loss > LOCAL_LOSS_TOLERANCE and not soft_spur:
            if diagnostic is not None:
                diagnostic.update(reason="candidate_loses_ink", lost_area=loss)
            return None
        area = abs(_op(changed, base, pathops.PathOp.DIFFERENCE).area)
        # A local replacement cannot add more ink than its closed arc/flank
        # patch. Analytic Green area is an independent float64 consistency
        # check; impossible PathOps measurements require a GEOS measurement.
        tail = _portion(a, 1-solution[0], 1)
        head = _portion(b, 0, solution[1])
        patch = _nodes_preserving_segment_start(solution[2]+_reverse([head])+_reverse([tail]))
        pen = AreaPen(None)
        _NodeGlyph([patch]).draw(pen)
        local_area = abs(pen.value)
        if loss > LOCAL_LOSS_TOLERANCE or area > local_area + max(.001, local_area*1e-5):
            try:
                from .check_equal_ink import _filled_geos, _geos_roundoff_bound
            except ImportError:
                from check_equal_ink import _filled_geos, _geos_roundoff_bound
            if robust_base is None:
                robust_base, _ = _filled_geos({'g':_NodeGlyph([_nodes_preserving_segment_start(c) for c in contours])},'g',.001)
            robust_new, _ = _filled_geos({'g':_NodeGlyph(_changed(contours,ci,j,solution,as_nodes=True))},'g',.001)
            actual_loss = robust_base.difference(robust_new.buffer(.002)).area
            precision = _geos_roundoff_bound((robust_base,robust_new),(robust_base.area,robust_new.area))
            if actual_loss > precision:
                return None
            if diagnostic is not None:
                diagnostic['local_area_backend'] = 'geos'
                diagnostic['pathops_impossible_area'] = area
                diagnostic['analytic_local_patch_area'] = local_area
            area = robust_new.difference(robust_base).area
        return Fillet(solution[0], solution[1], solution[2], r, area, target, False)
    # The first offset-curve collision/space limit bounds a safe local branch.
    # Continue from zero instead of jumping past a curved-flank singularity.
    ceiling = radius if phi <= math.pi/2 + 1e-8 else max(radius, min(seg_length(a), seg_length(b)))
    low_r, low, high_r = 0.0, None, ceiling
    for k in range(1, 25):
        r = ceiling*k/24
        found = candidate(r)
        if found is None:
            high_r = r
            break
        low_r, low = r, found
        if acute and found.area >= target and r >= minimum:
            high_r = r
            break
    else:
        high_r = ceiling
    if low is not None and (not acute and low_r == ceiling):
        return low
    # For an acute join bracket the *measured* added area, including curved
    # sides. A failed/capped tangent solution is an upper bound, never a wedge
    # or angle-only shortcut. Space-limited joins report their smaller area.
    if low is not None and acute and low.area >= target and low_r >= minimum:
        high_r, low_r, low = low_r, 0.0, None
    best = low
    for _ in range(30):
        mid = (low_r+high_r)/2
        found = candidate(mid)
        if found is None:
            high_r = mid
        elif acute and found.area >= target and mid >= minimum:
            high_r = mid
            if best is None or abs(found.area-target) < abs(best.area-target):
                best = found
        else:
            low_r, low = mid, found
            if best is None or (acute and abs(found.area-target) < abs(best.area-target)) or not acute:
                best = found
        if high_r-low_r < 1e-7:
            break
    if minimum and best is not None and best.radius < minimum:
        # When the full floor will not fit, retain the largest safe circle.
        floor_solution = candidate(minimum)
        if floor_solution is not None:
            best = floor_solution
        elif low is not None and low.radius > best.radius:
            best = low
    if best is not None and soft_spur and spur_floor < .60:
        # Michael's third-round prototype also limits the tangent-ray reach.
        # A curved flank can fit a larger actual arc while still respecting
        # the 90% arc-length cap. That excess ink is visible on Thin n and u.
        limit = .90 * min(_free_run(segs, j, -1), _free_run(segs, j, 1)) / math.tan(phi / 2)
        if limit < best.radius:
            thin_share = (.60 - spur_floor) / (.60 - .40)
            limited = candidate(best.radius + thin_share * (limit - best.radius))
            if limited is None:
                raise ValueError('could not fit the tapered tangent-run limit on the curved flanks')
            limited.tangent_run_limit = limit
            best = limited
    if best is not None:
        best.capped = (abs(best.area-target) > max(.1, target*1e-4)) if acute else best.radius < radius-1e-4
    return best


def _as_cubic(segment):
    if segment[0] == 'curve':
        return segment
    start, end = segment[1:]
    delta = sub(end, start)
    return ('curve', start, add(start, mul(delta, 1/3)), add(start, mul(delta, 2/3)), end)


def _backed_flank(segment, depth=None):
    """Bury a patch's hidden edge inside existing ink without moving its arc.

    The reverse flank travels with original ink on its right. Inset only its
    controls, retaining both contact endpoints. This invisible backing avoids
    white seam pockets when independently interpolated/quantized boundaries
    would otherwise coincide only approximately.
    """
    segment = _as_cubic(segment)
    if depth is None:
        depth = min(3.0, .1*seg_length(segment))
    start_tangent, end_tangent = seg_tangent_out(segment), seg_tangent_in(segment)
    return ('curve', segment[1],
            add(segment[2], mul((start_tangent[1], -start_tangent[0]), depth)),
            add(segment[3], mul((end_tangent[1], -end_tangent[0]), depth)), segment[4])


def _additive_patch(segments, join, solution):
    vertex = seg_end(segments[join])
    if solution is None:
        return _nodes_preserving_segment_start([('curve', vertex, vertex, vertex, vertex)]*4)
    incoming = _portion(segments[join], 1-solution.incoming, 1)
    outgoing = _portion(segments[(join+1) % len(segments)], 0, solution.outgoing)
    # Reverse the two original flank pieces in travel order: cutB->vertex,
    # vertex->cutA. The circular bridge runs cutA->cutB, so this is CCW ink.
    pieces = solution.bridges + [_backed_flank(_reverse([outgoing])[0]),
                                 _backed_flank(_reverse([incoming])[0])]
    patch = _nodes_preserving_segment_start(pieces)
    if nodes_to_pathops(patch).clockwise:
        raise ValueError('additive fillet patch has negative winding')
    return patch


class _NodeGlyph:
    width = 0
    def __init__(self, contours):
        self.contours = contours
    def draw(self, pen):
        for contour in self.contours:
            segments = nodes_to_segments(contour)
            if not segments:
                continue
            pen.moveTo(segments[0][1])
            for segment in segments:
                if segment[0] == 'line':
                    pen.lineTo(segment[-1])
                else:
                    pen.curveTo(*segment[2:])
            pen.closePath()


def _verify_source_geos(baseline, candidate, master_index, maximum_added_area=None):
    """Independent fallback for coincident-edge float32 boolean failures."""
    try:
        from .check_equal_ink import compare_glyphs
    except ImportError:
        from check_equal_ink import compare_glyphs
    # Each boundary is flattened within 0.001 units. Their combined distance
    # envelope is 0.002 units; this is a spatial approximation allowance, never
    # an area budget. Keep both raw and residual measurements in the report.
    metrics, _, _ = compare_glyphs({'source': _NodeGlyph(baseline)},
                                  {'source': _NodeGlyph(candidate)}, 'source',
                                  max_outline_loss_distance=.002, flatten_tolerance=.001)
    if metrics.area_conservation_error > metrics.area_conservation_tolerance:
        raise ValueError(f'equal-ink master {master_index}: GEOS conservation failed')
    if metrics.residual_lost_area > metrics.area_conservation_tolerance:
        raise ValueError(f'equal-ink master {master_index}: GEOS confirms '
                         f'{metrics.residual_lost_area:.8f} square units lost beyond '
                         f'the 0.002-unit source flattening envelope '
                         f'(raw {metrics.lost_area:.8f})')
    approximation_area = metrics.baseline_flattening_area_bound+metrics.candidate_flattening_area_bound
    if maximum_added_area is not None and metrics.added_area > maximum_added_area+approximation_area+metrics.area_conservation_tolerance:
        raise ValueError(f'equal-ink master {master_index}: GEOS added area '
                         f'{metrics.added_area:.8f} exceeds local fillet area '
                         f'{maximum_added_area:.8f} plus the measured flattening bound '
                         f'{approximation_area:.8f}')
    if metrics.baseline_counters != metrics.candidate_counters or metrics.unmatched_candidate_counters:
        raise ValueError(f'equal-ink master {master_index}: GEOS confirms changed counters')
    return dict(master=master_index, backend='geos', flattening_tolerance=.001,
                outline_distance_envelope=.002, raw_lost_area=metrics.lost_area,
                residual_lost_area=metrics.residual_lost_area, added_area=metrics.added_area,
                baseline_counters=metrics.baseline_counters,
                candidate_counters=metrics.candidate_counters,
                added_area_flattening_bound=approximation_area,
                conservation_error=metrics.area_conservation_error,
                precision_bound=metrics.area_conservation_tolerance)


def round_upright_a_notch(master_contours, radii, weights):
    """Match the three upright notch silhouettes in Michael's r2_a proof."""
    from fontTools.varLib.models import piecewiseLinearMap

    # Fitted to the rightmost column of documentation/proofs/issues/issue-125/
    # runde-2/r2_a.png at 664bbad5, using the clean Geist column to calibrate
    # font units. Regular is already close; Thin needs the largest change.
    # Reduce the calibrated Thin arc by the same 0.4/0.6 ratio as the spurs.
    # The Regular and Black optical corrections retain their reviewed values.
    reviewed = {100: 21., 400: 34.75, 900: 38.75}
    rounded, measurements = [], []
    for index, (original, r90, weight) in enumerate(zip(master_contours, radii, weights, strict=True)):
        contours = _normalize(original)
        outer = contours[0]
        if len(outer) != 15 or outer[-1][0] != 'curve' or outer[0][0] != 'curve':
            raise ValueError('unrecognized upright a bowl-to-tail junction')
        radius = max(spur_floor_at(weight) * r90, piecewiseLinearMap(weight, reviewed))
        u, v = seg_tangent_in(outer[-1]), seg_tangent_out(outer[0])
        phi = -math.atan2(cross(u, v), dot(u, v))
        circle = _circle(outer[-1], outer[0], radius, phi, (.90, .90))
        if circle is None:
            raise ValueError('upright a notch cannot reach the reviewed radius')
        result = _changed(contours, 0, len(outer)-1, circle, as_nodes=True)
        verification = _verify_source_geos(original, result, index)
        rounded.append(result)
        measurements.append(dict(radius=radius, area=verification['added_area'], target=F90*r90*r90))
    return rounded, dict(contour=0, join=14, status='rounded', semantic='upright_a_bowl_to_tail',
                         masters=measurements)


def round_italic_a_notch(master_contours, radii, weights):
    """Reach across the smooth subdivision of the italic bowl-to-tail flank."""
    rounded, measurements = [], []
    for index, (original, r90, weight) in enumerate(zip(master_contours, radii, weights, strict=True)):
        outer = nodes_to_segments(original[0])
        incoming, connector, outgoing = outer[2:5]
        u, v = seg_tangent_in(incoming), seg_tangent_out(connector)
        phi = -math.atan2(cross(u, v), dot(u, v))
        if (len(outer) != 17 or not all(seg[0] == 'curve' for seg in outer[2:5])
                or phi <= math.pi/2 or dot(seg_tangent_in(connector), seg_tangent_out(outgoing)) < .999):
            raise ValueError('unrecognized italic a bowl-to-tail junction')
        target = F90 * r90**2

        def fit(radius):
            circle = _circle(incoming, outgoing, radius, phi, (.90, .90))
            if circle is None:
                raise ValueError('italic a notch cannot reach the reviewed radius')
            cut_in, cut_out, bridge = circle
            replaced = [_portion(incoming, 1-cut_in, 1), connector, _portion(outgoing, 0, cut_out)]
            permitted = .90 * (seg_length(connector) + seg_length(outgoing))
            if seg_length(connector) + seg_length(replaced[-1]) > permitted:
                raise ValueError('italic a notch exceeds the reviewed tail reach')
            # Integrate the closed patch. The selected solution below is also
            # checked against the complete two-contour glyph independently.
            pen = AreaPen(None)
            _NodeGlyph([_nodes_preserving_segment_start(bridge + _reverse(replaced))]).draw(pen)
            return circle, abs(pen.value)

        low, high = spur_floor_at(weight) * r90, r90
        radius = low
        circle, area = fit(radius)
        if area < target:
            for _ in range(20):
                radius = (low + high) / 2
                circle, area = fit(radius)
                if abs(area - target) < .002:
                    break
                if area < target:
                    low = radius
                else:
                    high = radius
        cut_in, cut_out, bridge = circle
        # The bridge travels left to right all the way to the tail. A circular
        # tip with a neck doubles back in x and fails this design check.
        for segment in bridge:
            xs = [point[0] for point in segment[1:]]
            if xs != sorted(xs):
                raise ValueError('italic a notch doubles back before the tail')
        silhouette = [*outer[:2], _portion(incoming, 0, 1-cut_in), *bridge,
                      _portion(outgoing, cut_out, 1), *outer[5:]]
        result = [_nodes_preserving_segment_start(silhouette), *original[1:]]
        verification = _verify_source_geos(original, result, index, area)
        rounded.append(result)
        measurements.append(dict(radius=radius, area=verification['added_area'],
                                 target=target, capped=abs(area - target) > .01))
    return rounded, dict(contour=0, join=2, status='rounded', semantic='italic_a_bowl_to_tail',
                         masters=measurements)


def _y_tail_contact(arm, flanks, radius):
    """Find the tangent circle on the entire free flank, across its cubic knots."""
    tangent = seg_tangent_in(arm)
    origin = _offset(arm, 1., radius)
    maximum = .90 * sum(seg_length(s) for s in flanks)
    travelled = 0.
    contacts = []
    for index, flank in enumerate(flanks):
        # The center of a tangent circle lies on the offset arm line. A
        # curved flank can meet that line several times. Keep only empty
        # circles on the outward boundary and take the downstream contact.
        def side(t):
            return cross(sub(_offset(flank, t, radius), origin), tangent)

        divisions = 24 if flank[0] == 'curve' else 1
        for part in range(divisions):
            lo, hi = part/divisions, (part+1)/divisions
            at_lo = side(lo)
            if at_lo * side(hi) > 0:
                continue
            for _ in range(42):
                mid = (lo + hi) / 2
                if at_lo * side(mid) <= 0:
                    hi = mid
                else:
                    lo = mid
            touch = (lo + hi) / 2
            center = _offset(flank, touch, radius)
            cut = -dot(sub(center, origin), tangent) / seg_length(arm)
            if not 0 < cut < .90:
                continue
            consumed = _portion(flank, 0, touch)
            if travelled + seg_length(consumed) > maximum:
                continue
            replaced = [_portion(arm, 1-cut, 1), *flanks[:index], consumed]
            if any(dist(center, _point(s, k/32)) < radius - 1e-5 for s in replaced for k in range(33)):
                continue
            arc = _arc(_point(arm, 1-cut), _point(flank, touch), center, radius)
            contacts.append((cut, arc, index, touch, travelled + seg_length(consumed)))
        travelled += seg_length(flank)
    if not contacts:
        raise ValueError('default y has no safe tangent circle on the free descender flank')
    return contacts[-1]


def round_y_junction(master_contours, radii, weights, italic):
    """Round Michael's ledge-free y all the way onto the terminal when needed."""
    from fontTools.varLib.models import piecewiseLinearMap

    rounded, measurements = [], []
    for i, (original, r90, weight) in enumerate(zip(master_contours, radii, weights, strict=True)):
        segs, = _normalize(original)
        arm, *flanks = segs[6:10]
        if [s[0] for s in [arm, *flanks]] != ['line', 'curve', 'curve', 'line'] or flanks[-1][1][1] != flanks[-1][2][1]:
            raise ValueError('unrecognized option-B y junction')
        # Optical sizes fitted to the rightmost column of Michael's
        # r3_y_vorschau.png (5ef6ee4c). Italic matches its ordinary radius.
        optical = r90 if italic else piecewiseLinearMap(weight, {100: 53., 400: 53., 700: 42., 900: 37.})
        radius = max(.60*r90, min(r90, optical))
        cut, arc, contact, touch, reach = _y_tail_contact(arm, flanks, radius)
        remainder = _portion(flanks[contact], touch, 1)
        # Preserve two cubic slots and one line after the arc throughout the
        # axis, even where the contact has passed a knot or reached the flat.
        if contact == 0:
            tail = [remainder, *flanks[1:]]
        elif contact == 1:
            tail = [_portion(remainder, 0, .5), _portion(remainder, .5, 1), flanks[-1]]
        else:
            tail = [_as_cubic(_portion(remainder, 0, 1/3)), _as_cubic(_portion(remainder, 1/3, 2/3)),
                    _portion(remainder, 2/3, 1)]
        silhouette = [*segs[:6], _portion(arm, 0, 1-cut), *arc, *tail, *segs[10:]]
        result = [_nodes_preserving_segment_start(silhouette)]
        verification = _verify_source_geos(original, result, i)
        measurements.append(dict(radius=radius, target=F90*r90**2, area=verification['added_area'],
                                 flank=contact, reach=reach))
        rounded.append(result)
    return rounded, dict(contour=0, join=6, status='rounded', semantic='y_arm_to_descender', masters=measurements)


def _b_waist_flanks(contours):
    resolved = _normalize(resolve_clean_contours(contours))
    candidates = []
    for ci, segments in enumerate(resolved):
        nodes = _nodes_preserving_segment_start(segments)
        if nodes_to_pathops(nodes).clockwise:
            continue
        bounds = _alignment_bounds(nodes)
        w, h = bounds[2]-bounds[0], bounds[3]-bounds[1]
        def near_waist(point):
            return point[0] > bounds[0]+.45*w and bounds[1]+.35*h < point[1] < bounds[1]+.65*h
        for j, incoming in enumerate(segments):
            k = (j+1) % len(segments)
            outgoing = segments[k]
            if not near_waist(seg_end(incoming)):
                continue
            if outgoing[0] == 'line' and near_waist(seg_end(outgoing)):
                after = segments[(k+1) % len(segments)]
                if incoming[0] == after[0] == 'curve':
                    u, v = seg_tangent_in(incoming), seg_tangent_out(after)
                    turn = math.atan2(cross(u, v), dot(u, v))
                    if turn < -.01:
                        candidates.append((-turn, incoming, after, outgoing, seg_end(incoming)))
            if incoming[0] == outgoing[0] == 'curve':
                u, v = seg_tangent_in(incoming), seg_tangent_out(outgoing)
                turn = math.atan2(cross(u, v), dot(u, v))
                if turn < -.01:
                    vertex = seg_end(incoming)
                    candidates.append((-turn, incoming, outgoing, ('line', vertex, vertex), vertex))
    if not candidates:
        raise ValueError('B has no resolved semantic waist join')
    best = max(candidates, key=lambda c: c[0])
    # Recover the selected original resolved segment indices for a continuous
    # rounded outer contour, rather than a separate contact patch.
    for ci, segments in enumerate(resolved):
        for i, segment in enumerate(segments):
            if segment == best[1]:
                for k, other in enumerate(segments):
                    if other == best[2]:
                        return (*best, segments, i, k)
    raise ValueError('B waist segment identity was lost')


def _waist_patch(incoming, outgoing, connector, circle):
    a, b, bridges = circle
    tail = _portion(incoming, 1-a, 1)
    head = _portion(outgoing, 0, b)
    pieces = bridges+[_backed_flank(_reverse([head])[0]),
                      _as_cubic(_reverse([connector])[0]),
                      _backed_flank(_reverse([tail])[0])]
    patch = _nodes_preserving_segment_start(pieces)
    if nodes_to_pathops(patch).clockwise:
        raise ValueError('B waist patch has negative winding')
    return patch


def _solve_b_waist(contours, radius):
    try:
        from .check_equal_ink import _filled_geos, _geos_counters
    except ImportError:
        from check_equal_ink import _filled_geos, _geos_counters
    phi, incoming, outgoing, connector, vertex, outer_segments, incoming_index, outgoing_index = _b_waist_flanks(contours)
    baseline, _ = _filled_geos({'B': _NodeGlyph(contours)}, 'B', .001)
    target = F90*radius*radius
    def candidate(r):
        try:
            circle = _circle(incoming, outgoing, r, phi)
        except ValueError:
            return None
        if circle is None:
            return None
        try:
            patch = _waist_patch(incoming, outgoing, connector, circle)
        except ValueError:
            return None
        shape, _ = _filled_geos({'B': _NodeGlyph([patch])}, 'B', .001)
        area = shape.difference(baseline).area
        return dict(patch=patch, radius=r, area=area, target=target,
                    connector_length=seg_length(connector),
                    incoming_parameter=circle[0], outgoing_parameter=circle[1])
    acute = phi > math.pi/2
    ceiling = max(radius, min(seg_length(incoming), seg_length(outgoing))) if acute else radius
    samples = [.05*(ceiling/.05)**(i/63) for i in range(64)]
    previous_r, previous, best = 0., None, None
    lower, upper = 0., ceiling
    bracketed = False
    for r in samples:
        found = candidate(r)
        if found is None:
            if previous is not None:
                lower, upper, bracketed = previous_r, r, True
                break
            continue
        if best is None or abs(found['area']-target) < abs(best['area']-target):
            best = found
        if acute and found['area'] >= target:
            lower, upper, bracketed = previous_r, r, True
            break
        previous_r, previous = r, found
    if bracketed:
        for _ in range(28):
            r = (lower+upper)/2
            found = candidate(r)
            if found is None:
                upper = r
            else:
                if best is None or abs(found['area']-target) < abs(best['area']-target):
                    best = found
                if acute and found['area'] >= target:
                    upper = r
                else:
                    lower = r
            if upper-lower < 1e-6:
                break
    if best is None:
        raise ValueError('B waist has no safe circle within the flank bound')
    # Check the actual nonzero compound, including raw overlap winding.
    combined, _ = _filled_geos({'B': _NodeGlyph(contours+[best['patch']])}, 'B', .001)
    if baseline.difference(combined.buffer(.002)).area > 1e-6:
        raise ValueError('semantic B waist patch removes baseline ink')
    if len(_geos_counters(combined)) != len(_geos_counters(baseline)):
        raise ValueError('semantic B waist patch changes counter topology')
    best['capped'] = abs(best['area']-target) > max(.1, target*1e-4) if acute else best['radius'] < radius-1e-4
    circle = _circle(incoming,outgoing,best['radius'],phi)
    remaining = []
    index = (outgoing_index+1)%len(outer_segments)
    while index != incoming_index:
        remaining.append(outer_segments[index])
        index = (index+1)%len(outer_segments)
    rounded_outer = [_portion(incoming,0,1-circle[0]), *circle[2],
                     _portion(outgoing,circle[1],1), *remaining]
    best['rounded_outer'] = _nodes_preserving_segment_start(rounded_outer)
    return best


def _inactive_cut(segment, at_end=False):
    """Reserve finite original-curve pieces for an inactive two-arc slot.

    Collapsed cubics can acquire opposite-winding loops after TrueType delta
    rounding. One exact incoming tail and one outgoing head preserve the
    original geometry and keep interpolation on both sides of the corner.
    Each cubic gets a four-unit run on the integer lattice; short flanks
    retain the 45% bound.
    """
    length = seg_length(segment)
    if length <= 1e-10:
        return 0.0
    reach = min(4.0, FLANK_FRACTION*length)
    return reach/length if segment[0] == 'line' else (1-_cubic_split_t_for_arclen(segment, reach, False) if at_end else _cubic_split_t_for_arclen(segment, reach, True))


def round_compatible_contours(master_contours: Sequence[Sequence[Sequence[Node]]],
                              radii: Sequence[float], *, semantic_b_waist: bool = False,
                              soft_spurs=False, spur_floors=None, counter_scales=None, local_guard=None, static_projection=None):
    """Return (master_contours, report) with compatible cubic topology.

    Supply clean source outlines, never already rounded outlines. Corresponding
    contours must have matching segment kinds/order in all masters. Winding is
    normalized by nesting. ``radii`` are r90 values, one per master. The
    default outline has one continuous boundary per source contour.
    A 'fillets' guard keeps the original contours with isolated ink additions;
    a 'flanks' guard backs the rounded boundary with short strips following
    the original curves at trimmed joins.
    Subunit members are inactive; other weights keep compatible arc slots.
    Report entries have status ``rounded`` or ``skipped``. Rounded entries
    identify each master's radius, actual added area, target and cap status.
    Skipped entries explain which master had no safe local solution. Capping
    can reflect the 45% space bound or an earlier curved offset-branch limit.
    """
    if len(master_contours) != len(radii) or not master_contours:
        raise ValueError("one radius is required for every master")
    if any(not math.isfinite(r) or r <= 0 for r in radii):
        raise ValueError("radii must be finite and positive")
    masters = [_normalize(contours) for contours in master_contours]
    signature = lambda m: [[s[0] for s in c] for c in m]
    if any(signature(m) != signature(masters[0]) for m in masters[1:]):
        raise ValueError("clean master contours have incompatible segment topology")
    bases = [_path([segments_to_nodes(c) for c in m]) for m in masters]
    if counter_scales is None:
        counter_scales = [1.] * len(masters)
    if spur_floors is None:
        spur_floors = [.60 if soft_spurs else 0.] * len(masters)
    chosen, report = {}, []
    for ci, contour in enumerate(masters[0]):
        counter = nodes_to_pathops(_nodes_preserving_segment_start(contour)).clockwise
        for j in range(len(contour)):
            solutions, diagnostics = [], []
            failed = False
            for m, r, base, scale, floor in zip(masters, radii, bases, counter_scales, spur_floors, strict=True):
                a, b = m[ci][j], m[ci][(j+1) % len(contour)]
                u, v = seg_tangent_in(a), seg_tangent_out(b)
                concave = math.atan2(cross(u, v), dot(u, v)) < -math.radians(.1)
                diagnostic = dict(status="inactive")
                solution = _solve(m, ci, j, r, base, diagnostic,
                                  spur_floor=0. if counter else floor,
                                  counter_scale=scale if counter else 1.) if concave else None
                if solution is not None and solution.area < MIN_ADDED_AREA:
                    diagnostic.update(status="inactive", reason="subunit_fillet_member", area=solution.area, radius=solution.radius)
                    solution = None
                    concave = False
                if concave and solution is None:
                    failed = True
                    diagnostic["status"] = "unsafe"
                    diagnostic.setdefault("reason", "no_safe_fillet_on_local_tangent_branch")
                elif solution:
                    diagnostic["status"] = "solved"
                solutions.append(solution)
                diagnostics.append(diagnostic)
            if failed:
                report.append(dict(contour=ci, join=j, status="skipped",
                                   reason="one_or_more_masters_have_no_safe_solution",
                                   masters=diagnostics))
                continue
            if not any(solutions):
                if any(d.get('reason') == 'subunit_fillet_member' for d in diagnostics):
                    report.append(dict(contour=ci,join=j,status='skipped',reason='subunit_fillet',
                                       minimum_area=MIN_ADDED_AREA,masters=[dict(d, area=d.get('area', 0)) for d in diagnostics]))
                continue
            if max(s.area for s in solutions if s) < MIN_COMPATIBLE_FILLET_AREA:
                # A bridge smaller than one TrueType square unit is below the
                # output grid's feature scale. Interpolating a Black-only micro
                # bridge against degenerate Thin/Regular slots can form a loop.
                # Skip the corresponding join consistently in every master.
                report.append(dict(contour=ci, join=j, status="skipped",
                                   reason="subunit_fillet", minimum_area=MIN_COMPATIBLE_FILLET_AREA,
                                   masters=[dict(area=s.area, radius=s.radius) if s else dict(area=0, inactive=True)
                                            for s in solutions]))
                continue
            chosen[ci, j] = solutions
            report.append(dict(contour=ci, join=j, status="rounded", masters=[
                dict(radius=s.radius, area=s.area, target=s.target, capped=s.capped,
                     **({'tangent_run_limit': s.tangent_run_limit} if s.tangent_run_limit is not None else {}))
                if s else dict(radius=0, area=0, target=F90*r*r, inactive=True,
                               reason=d.get('reason', 'join_not_concave'),
                               measured_area=d.get('area', 0))
                for s, r, d in zip(solutions, radii, diagnostics)]))
    waist_solutions = []
    if semantic_b_waist:
        waist_solutions = [_solve_b_waist([_nodes_preserving_segment_start(c) for c in master], radius)
                           for master, radius in zip(masters, radii)]
        report.append(dict(contour=-1, join=-1, status='rounded', semantic='B_waist',
                           masters=[{key:value for key,value in solution.items() if key not in ('patch','rounded_outer')}
                                    for solution in waist_solutions]))
    output = []
    for mi, master in enumerate(masters):
        contours = [_nodes_preserving_segment_start(segs) for segs in master]
        if chosen or waist_solutions:
            rounded = []
            for ci,segs in enumerate(master):
                result,n = [],len(segs)
                for j,seg in enumerate(segs):
                    before = chosen.get((ci,(j-1)%n),[None]*len(masters))[mi]
                    after = chosen.get((ci,j),[None]*len(masters))[mi]
                    start = before.outgoing if before else (_inactive_cut(seg) if (ci,(j-1)%n) in chosen else 0)
                    end = 1-after.incoming if after else (1-_inactive_cut(seg,True) if (ci,j) in chosen else 1)
                    if start >= end:
                        raise ValueError(f'fillets overlap on contour {ci}, segment {j}, master {mi}')
                    result.append(_portion(seg, start, end))
                    if (ci,j) in chosen:
                        if after: result.extend(after.bridges)
                        else:
                            outgoing = segs[(j+1)%n]
                            cut = _inactive_cut(outgoing)
                            result.extend([_as_cubic(_portion(seg,1-_inactive_cut(seg,True),1)),
                                           _as_cubic(_portion(outgoing,0,cut))])
                rounded.append(_nodes_preserving_segment_start(result))
            if waist_solutions:
                outer_index = max((i for i,segs in enumerate(master)
                                   if not nodes_to_pathops(_nodes_preserving_segment_start(segs)).clockwise),
                                  key=lambda i:nodes_to_pathops(_nodes_preserving_segment_start(master[i])).area)
                rounded[outer_index] = waist_solutions[mi]['rounded_outer']
            contours = rounded
            if static_projection is not None:
                static_projection.append(rounded.copy())
            if local_guard == 'fillets':
                # Preserve the curved base across interpolation and add the
                # solved ink locally. Exact named statics use the boundary above.
                contours = [_nodes_preserving_segment_start(segs) for segs in master]
                contours.extend(_additive_patch(master[ci], j, solutions[mi])
                                for (ci, j), solutions in chosen.items())
            if local_guard == 'flanks':
                for ci, segs in enumerate(master):
                    for j, seg in enumerate(segs):
                        if seg[0] == 'curve' and ((ci, j) in chosen or (ci, (j-1) % len(segs)) in chosen):
                            # Follow only the original trimmed curve, then return
                            # inside the stroke. Keep full contours out of the guard.
                            reverse = _reverse([seg])[0]
                            contours.append(_nodes_preserving_segment_start([seg, _backed_flank(reverse, 15.)]))
        elif static_projection is not None:
            static_projection.append(contours)
        final = _path(contours)
        loss = abs(_op(bases[mi], final, pathops.PathOp.DIFFERENCE).area)
        counter_change = _counter_count(final) != _counter_count(bases[mi])
        added = abs(_op(final, bases[mi], pathops.PathOp.DIFFERENCE).area)
        expected = sum(solutions[mi].area for solutions in chosen.values() if solutions[mi])
        if waist_solutions:
            expected += waist_solutions[mi]['area']
        fast_failure = loss > AREA_TOLERANCE or counter_change or added > expected + AREA_TOLERANCE * max(1, len(chosen))
        if fast_failure:
            verification = _verify_source_geos([segments_to_nodes(c) for c in master], contours, mi, expected)
            verification['pathops_lost_area'] = loss
            verification['pathops_added_area'] = added
            # Report the independent evidence on the first join record without
            # changing the report's rounded/skipped entry contract.
            if report:
                report[0].setdefault('source_verification', []).append(verification)
        output.append(contours)
    return output, report
