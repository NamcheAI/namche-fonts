#!/usr/bin/env python3
"""
Round only concave (inner) corners in Geist .glyphspackage sources.

- Keeps convex outer corners sharp
- Remove-overlap first (pathops union / difference), then ink-trap collapse, then fillet outers
- Fillets hole/counter concave corners (D/B/P/R/A) with a stricter feature cap
- Acute fill interiors (A/M/N/V/W crotches) get angle-scaled radii so they
  stay optically coherent with orthogonal stem/bar joins
- Preview uses evenodd compound paths so counters stay open

Usage:
  python3 scripts/round_inner_corners.py --dry-run
  python3 scripts/round_inner_corners.py --write --radius 40
  # Change radius after a previous pass (resets from background first):
  python3 scripts/round_inner_corners.py --write --restore-from-background --radius 40
  # Reproduce the profile the shipped Sans italic masters were baked with:
  python3 scripts/round_inner_corners.py --write --radius 40 --italic-recipe
"""

from __future__ import annotations

import argparse
import math
import re
import sys
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

# Delivery family name (source packages remain Geist; renamed at export).
SOURCE_FAMILY_NAME = "Geist"
FAMILY_NAME = "NamcheShadowSans"

try:
    import pathops
    from fontTools.misc import bezierTools
    from fontTools.pens.recordingPen import RecordingPen
except ImportError as exc:  # pragma: no cover
    sys.stderr.write(
        "Missing dependency. Install with: pip3 install skia-pathops fonttools\n"
    )
    raise SystemExit(1) from exc


Point = Tuple[float, float]
Node = Tuple[float, float, str]  # x, y, type

MASTER_IDS = {
    "Thin": "EE2FFE84-06F1-4AFB-BBEC-60D09A436D14",
    "Regular": "6C190511-B94A-4F5A-B519-D6E9DB0E7B93",
    "Black": "3507EE3D-0D92-4546-A145-3A991F0A2B71",
}

MASTER_RADIUS_SCALE = {
    # Optical coherence vs stem (Geist Thin ≈32 UPM): full absolute R melts Thin
    # junctions (R/stem > 1). Keep Regular/Black at 1.0 (absolute R); ease Thin
    # toward ~0.55–0.7 R/stem so Soft-inner reads as one family.
    MASTER_IDS["Thin"]: 0.55,
    MASTER_IDS["Regular"]: 1.00,
    MASTER_IDS["Black"]: 1.00,
}

# The Sans italic masters were baked with the first revision of this filter:
# a plain circular fillet (no acute-angle reduction, no mouth cap) and a
# heavier Black scale. `--italic-recipe` restores it so the committed
# NamcheShadowSans-Italic outlines stay reproducible from
# sources/NamcheShadowSans-Italic.glyphspackage; the default profile is the
# later upright tuning and does not reproduce them.
ITALIC_RECIPE_MASTER_SCALE = {
    MASTER_IDS["Thin"]: 0.55,
    MASTER_IDS["Regular"]: 1.00,
    MASTER_IDS["Black"]: 1.35,
}

# Set by --italic-recipe.
ITALIC_RECIPE = False


def master_radius_scale(layer_id: str) -> float:
    table = ITALIC_RECIPE_MASTER_SCALE if ITALIC_RECIPE else MASTER_RADIUS_SCALE
    return table.get(layer_id, 1.0)


DIGIT_NAMES = {
    "0": "zero",
    "1": "one",
    "2": "two",
    "3": "three",
    "4": "four",
    "5": "five",
    "6": "six",
    "7": "seven",
    "8": "eight",
    "9": "nine",
}

PROOF_GLYPHS = (
    [chr(c) for c in range(ord("A"), ord("Z") + 1)]
    + [chr(c) for c in range(ord("a"), ord("z") + 1)]
    + [
        "zero",
        "one",
        "two",
        "three",
        "four",
        "five",
        "six",
        "seven",
        "eight",
        "nine",
        # composites i/j reference these
        "idotless",
        "jdotless",
    ]
)


# ---------------------------------------------------------------------------
# geometry helpers
# ---------------------------------------------------------------------------

def dist(a: Point, b: Point) -> float:
    return math.hypot(b[0] - a[0], b[1] - a[1])


def sub(a: Point, b: Point) -> Point:
    return (a[0] - b[0], a[1] - b[1])


def add(a: Point, b: Point) -> Point:
    return (a[0] + b[0], a[1] + b[1])


def mul(a: Point, s: float) -> Point:
    return (a[0] * s, a[1] * s)


def dot(a: Point, b: Point) -> float:
    return a[0] * b[0] + a[1] * b[1]


def cross(a: Point, b: Point) -> float:
    return a[0] * b[1] - a[1] * b[0]


def norm(v: Point) -> Point:
    length = math.hypot(v[0], v[1])
    if length < 1e-12:
        return (0.0, 0.0)
    return (v[0] / length, v[1] / length)


def line_intersect(p1: Point, p2: Point, p3: Point, p4: Point) -> Optional[Point]:
    r = sub(p2, p1)
    s = sub(p4, p3)
    den = cross(r, s)
    if abs(den) < 1e-9:
        return None
    t = cross(sub(p3, p1), s) / den
    return add(p1, mul(r, t))


def signed_area_points(pts: Sequence[Point]) -> float:
    """Positive = CCW (outer, fill to left); negative = CW (hole)."""
    area = 0.0
    n = len(pts)
    for i in range(n):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % n]
        area += x1 * y2 - x2 * y1
    return area * 0.5


def oncurve_points_from_nodes(nodes: Sequence[Node]) -> List[Point]:
    return [(x, y) for x, y, t in nodes if t != "o"]


def is_hole_path(nodes: Sequence[Node]) -> bool:
    pts = oncurve_points_from_nodes(nodes)
    if len(pts) < 3:
        return False
    return signed_area_points(pts) < 0


def path_feature_size(pts: Sequence[Point]) -> float:
    """Rough local stem/feature scale from path bounds."""
    if not pts:
        return 40.0
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    bw = max(xs) - min(xs)
    bh = max(ys) - min(ys)
    return max(20.0, min(bw, bh) * 0.35)


# Concave joins sharper than this are treated as ink-trap wedges rather than
# ordinary corners; see the wedge branch in fillet_mixed().
WEDGE_ANGLE = math.radians(135)
# A wedge must also be shallow. Stem/shoulder junction notches reach 77-129 units
# out of the corner; the diagonal interiors of v/w/x/y/z/K/M/N/V/W reach 297+, and
# those define the letter, so they get an ordinary fillet instead.
WEDGE_MAX_REACH = 200.0
# Notch depth consumed per unit of slider radius (fraction of reach).
WEDGE_DEPTH_GAIN = 2.0

# Fraction of a segment two neighbouring fillets may consume between them.
SEG_TRIM_BUDGET = 0.98


HOLE_FEATURE_CAP = 0.40  # counters get at most this fraction of their feature size

# Orthogonal stem/bar joins (H/E/F/t) keep full radius. Acute fill interiors
# (A apex, M/N/V/W crotches, K junctions) clog optically at the same R, so
# shrink toward the 90° reference. Floor keeps a readable soft-inner cue.
ACUTE_REF_ANGLE = math.pi / 2  # 90°
ACUTE_RADIUS_FLOOR = 0.32
# Max mouth size for acute tips, as a multiple of the slider radius. Stops
# tan(phi/2) from opening a wide blunt chord, while still leaving a readable
# round (a hard cap at r_use itself made M/N/V/W go nearly sharp).
ACUTE_MOUTH_FACTOR = 1.15
ACUTE_MOUTH_MAX = 52.0


def capped_radius(radius: float, l1: float, l2: float, feature: float) -> float:
    """Limit fillet so large slider values cannot consume counters/bowls.

    Tight joins (short segments / small features) stay smaller than open
    corners so the slider still moves geometry without over-rounding.
    """
    return min(radius, 0.40 * min(l1, l2), 0.45 * feature)


def angle_adjusted_radius(radius: float, phi: float) -> float:
    """Reduce radius for acute fill interiors (large path-turn ``phi``).

    ``phi`` is the absolute exterior turn at a concave join. Fill interior
    angle is ``pi - phi``. At 90° interior the radius is unchanged; sharper
    tips scale down proportionally (clamped by ``ACUTE_RADIUS_FLOOR``).
    """
    if ITALIC_RECIPE:
        return radius
    interior = math.pi - abs(phi)
    if interior >= ACUTE_REF_ANGLE - 1e-6:
        return radius
    scale = max(ACUTE_RADIUS_FLOOR, interior / ACUTE_REF_ANGLE)
    return radius * scale


def acute_mouth_cap(radius: float, r_use: float) -> float:
    """Limit how far acute fillets cut back along each flank."""
    if ITALIC_RECIPE:
        return math.inf
    return max(r_use, min(radius * ACUTE_MOUTH_FACTOR, ACUTE_MOUTH_MAX))


def hole_radius(radius: float, nodes: Sequence[Node]) -> float:
    """Stricter radius for counter paths so D/B/P/R/A round without filling."""
    feature = path_feature_size(oncurve_points_from_nodes(nodes))
    return min(radius, HOLE_FEATURE_CAP * feature)


# ---------------------------------------------------------------------------
# Glyphs node parsing / formatting
# ---------------------------------------------------------------------------

NODE_RE = re.compile(
    r"\(\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*,\s*([a-z]+)\s*\)"
)


def glyph_filename(name: str) -> str:
    if re.fullmatch(r"[A-Z]", name):
        return f"{name}_.glyph"
    return f"{name}.glyph"


def parse_nodes(block: str) -> List[Node]:
    return [(float(x), float(y), t) for x, y, t in NODE_RE.findall(block)]


def format_nodes(nodes: Sequence[Node]) -> str:
    lines = ["nodes = ("]
    for x, y, t in nodes:
        xi = int(round(x))
        yi = int(round(y))
        lines.append(f"({xi},{yi},{t}),")
    lines.append(")")
    return "\n".join(lines)


def nodes_are_polyline(nodes: Sequence[Node]) -> bool:
    return all(t in ("l", "ls") for _, _, t in nodes)


# ---------------------------------------------------------------------------
# ink-trap collapse (line paths)
# ---------------------------------------------------------------------------

def collapse_ink_traps(points: List[Point], max_short: float = 160.0) -> List[Point]:
    """Replace short diagonal notches between long edges with their intersection."""
    pts = list(points)
    guard = 0
    while guard < 64:
        guard += 1
        n = len(pts)
        if n < 4:
            break
        collapsed_at: Optional[int] = None
        for i in range(n):
            a = pts[(i - 1) % n]
            b = pts[i]
            c = pts[(i + 1) % n]
            d = pts[(i + 2) % n]
            short_len = dist(b, c)
            if short_len > max_short:
                continue
            # Long edges on both sides of the notch
            if dist(a, b) < short_len * 1.15 or dist(c, d) < short_len * 1.15:
                continue
            v1 = norm(sub(b, a))
            v2 = norm(sub(d, c))
            # roughly perpendicular long edges (Geist stem/bar joins)
            if abs(dot(v1, v2)) > 0.55:
                continue
            v = line_intersect(a, b, c, d)
            if v is None:
                continue
            # notch tip should sit near the virtual corner
            if dist(v, b) > max_short * 1.35 and dist(v, c) > max_short * 1.35:
                continue
            new_pts: List[Point] = []
            skip = (i + 1) % n
            for j, p in enumerate(pts):
                if j == i:
                    new_pts.append(v)
                elif j == skip:
                    continue
                else:
                    new_pts.append(p)
            pts = new_pts
            collapsed_at = i
            break
        if collapsed_at is None:
            break
    return [(round(x, 3), round(y, 3)) for x, y in pts]


def polyline_to_nodes(points: Sequence[Point]) -> List[Node]:
    return [(p[0], p[1], "l") for p in points]


def _nodes_geometry_changed(a: Sequence[Node], b: Sequence[Node]) -> bool:
    if len(a) != len(b):
        return True
    for (x0, y0, t0), (x1, y1, t1) in zip(a, b):
        if t0 != t1 or abs(x0 - x1) > 0.1 or abs(y0 - y1) > 0.1:
            return True
    return False


def collapse_ink_traps_nodes(
    nodes: List[Node], max_short: float = 160.0
) -> List[Node]:
    """
    Collapse Geist ink-trap notches on polyline paths (H/E/F/T/k/x).

    Mixed curve/line paths are returned untouched: pathops remove-overlap
    already resolves their real ink traps, and any spur heuristic here would
    eat legitimate stroke terminals (a tail, e crossbar, y).
    """
    if len(nodes) < 4 or is_hole_path(nodes):
        return nodes

    if not nodes_are_polyline(nodes):
        return nodes

    pts_in = [(x, y) for x, y, _ in nodes]
    pts = collapse_ink_traps(pts_in, max_short=max_short)
    return _drop_zero_length_oncurves(polyline_to_nodes(pts))


def _drop_zero_length_oncurves(nodes: Sequence[Node]) -> List[Node]:
    """Remove consecutive on-curve duplicates that can appear after trap joins."""
    if len(nodes) < 3:
        return list(nodes)
    on_idx = [i for i, n in enumerate(nodes) if n[2] != "o"]
    if len(on_idx) < 3:
        return list(nodes)
    drop_on = set()
    for k, i in enumerate(on_idx):
        j = on_idx[(k + 1) % len(on_idx)]
        if dist((nodes[i][0], nodes[i][1]), (nodes[j][0], nodes[j][1])) < 0.05:
            drop_on.add(j)
    if not drop_on:
        return list(nodes)
    # Also drop offcurves that only served a removed on-curve end.
    out: List[Node] = []
    n = len(nodes)
    i = 0
    while i < n:
        if i in drop_on:
            i += 1
            continue
        if nodes[i][2] == "o":
            # Keep offcurves only if their following on-curve survives.
            j = i
            while j < n and nodes[j][2] == "o":
                j += 1
            if j < n and j not in drop_on:
                out.extend(nodes[i:j])
            i = j
            continue
        out.append(nodes[i])
        i += 1
    return out if len(out) >= 3 else list(nodes)


# ---------------------------------------------------------------------------
# fillet concave corners
# ---------------------------------------------------------------------------

def fillet_nodes(nodes: List[Node], radius: float) -> Tuple[List[Node], int]:
    """
    Fillet sharp concave corners. Fill is assumed to the left of the path
    (Glyphs / PostScript). Negative cross turn => inner corner.

    Hole/counter paths (CW) are filleted too — that is where D/B/P/R/A keep
    their stem/bowl concave joins — but with a stricter feature cap.
    """
    if radius <= 0 or len(nodes) < 3:
        return nodes, 0

    r_use = hole_radius(radius, nodes) if is_hole_path(nodes) else radius
    if r_use < 0.5:
        return nodes, 0

    on_idx = [i for i, n in enumerate(nodes) if n[2] != "o"]
    if len(on_idx) < 3:
        return nodes, 0

    if nodes_are_polyline(nodes):
        pts = [(x, y) for x, y, _ in nodes]
        new_nodes, count = fillet_polyline(pts, r_use)
        return new_nodes, count

    return fillet_mixed(nodes, r_use)


def fillet_polyline(points: List[Point], radius: float) -> Tuple[List[Node], int]:
    n = len(points)
    feature = path_feature_size(points)
    mods = {}
    for i in range(n):
        a = points[(i - 1) % n]
        b = points[i]
        c = points[(i + 1) % n]
        d1 = sub(b, a)
        d2 = sub(c, b)
        if cross(d1, d2) >= -1e-6:
            continue  # outer or colinear
        l1 = math.hypot(*d1)
        l2 = math.hypot(*d2)
        if l1 < 1 or l2 < 1:
            continue
        u1 = (d1[0] / l1, d1[1] / l1)
        u2 = (d2[0] / l2, d2[1] / l2)
        ang = math.atan2(cross(u1, u2), dot(u1, u2))
        if ang >= -1e-3:
            continue
        phi = abs(ang)
        # skip near-flat
        if phi < math.radians(18):
            continue
        # skip very sharp spikes (leftover micro notches)
        if phi > math.radians(165):
            continue
        tan_half = math.tan(phi / 2)
        if tan_half < 1e-9:
            continue
        r_use = angle_adjusted_radius(
            capped_radius(radius, l1, l2, feature), phi
        )
        if r_use < 0.5:
            continue
        # Cap trim so acute tips don't open a wide blunt chord (tan(phi/2)
        # grows fast past 90°), while keeping a visible round.
        trim = min(
            r_use * tan_half,
            min(l1, l2) * 0.40,
            acute_mouth_cap(radius, r_use),
        )
        r_eff = r_use
        if trim + 1e-9 < r_use * tan_half:
            r_eff = trim / tan_half
        if trim < 0.5:
            continue
        p1 = sub(b, mul(u1, trim))
        p2 = add(b, mul(u2, trim))
        k = (4.0 / 3.0) * math.tan(phi / 4.0)
        cp1 = add(p1, mul(u1, r_eff * k))
        cp2 = sub(p2, mul(u2, r_eff * k))
        mods[i] = (p1, cp1, cp2, p2)

    if not mods:
        return polyline_to_nodes(points), 0

    out: List[Node] = []
    for i in range(n):
        if i in mods:
            p1, cp1, cp2, p2 = mods[i]
            out.append((p1[0], p1[1], "l"))
            out.append((cp1[0], cp1[1], "o"))
            out.append((cp2[0], cp2[1], "o"))
            out.append((p2[0], p2[1], "c"))
        else:
            x, y = points[i]
            out.append((x, y, "l"))
    return out, len(mods)


# --- segment view of a contour (lines + cubics) ----------------------------

# ("line", p0, p1) | ("curve", p0, c1, c2, p3)
Segment = tuple


def nodes_to_segments(nodes: Sequence[Node]) -> List[Segment]:
    """Split a closed contour into line/cubic segments in ring order."""
    n = len(nodes)
    on_indices = [i for i, nd in enumerate(nodes) if nd[2] != "o"]
    if len(on_indices) < 2:
        return []
    segs: List[Segment] = []
    for k, i_from in enumerate(on_indices):
        i_to = on_indices[(k + 1) % len(on_indices)]
        p0 = (nodes[i_from][0], nodes[i_from][1])
        p3 = (nodes[i_to][0], nodes[i_to][1])
        between: List[Node] = []
        j = (i_from + 1) % n
        while j != i_to:
            between.append(nodes[j])
            j = (j + 1) % n
        if len(between) == 2 and between[0][2] == "o" and between[1][2] == "o":
            segs.append(
                ("curve", p0, (between[0][0], between[0][1]),
                 (between[1][0], between[1][1]), p3)
            )
        else:
            segs.append(("line", p0, p3))
    return segs


def segments_to_nodes(segs: Sequence[Segment]) -> List[Node]:
    """Rebuild Glyphs nodes from segments (emits each segment's end point)."""
    out: List[Node] = []
    for seg in segs:
        if seg[0] == "curve":
            _, _p0, c1, c2, p3 = seg
            out.append((c1[0], c1[1], "o"))
            out.append((c2[0], c2[1], "o"))
            out.append((p3[0], p3[1], "c"))
        else:
            _, _p0, p1 = seg
            out.append((p1[0], p1[1], "l"))
    return out


def seg_start(seg: Segment) -> Point:
    return seg[1]


def seg_end(seg: Segment) -> Point:
    return seg[-1]


def seg_length(seg: Segment) -> float:
    if seg[0] == "curve":
        return float(bezierTools.approximateCubicArcLength(seg[1], seg[2], seg[3], seg[4]))
    return dist(seg[1], seg[2])


def seg_tangent_out(seg: Segment) -> Point:
    """Unit direction leaving the segment's start point."""
    if seg[0] == "curve":
        _, p0, c1, c2, p3 = seg
        for target in (c1, c2, p3):
            v = norm(sub(target, p0))
            if v != (0.0, 0.0):
                return v
        return (0.0, 0.0)
    return norm(sub(seg[2], seg[1]))


def seg_tangent_in(seg: Segment) -> Point:
    """Unit direction arriving at the segment's end point."""
    if seg[0] == "curve":
        _, p0, c1, c2, p3 = seg
        for target in (c2, c1, p0):
            v = norm(sub(p3, target))
            if v != (0.0, 0.0):
                return v
        return (0.0, 0.0)
    return norm(sub(seg[2], seg[1]))


def _cubic_split_t_for_arclen(seg: Segment, want: float, from_start: bool) -> float:
    """Parameter t where the arc length measured from one end equals `want`."""
    _, p0, c1, c2, p3 = seg
    total = float(bezierTools.approximateCubicArcLength(p0, c1, c2, p3))
    if total <= 1e-9:
        return 0.5
    target = want if from_start else total - want
    lo, hi = 0.0, 1.0
    for _ in range(32):
        mid = (lo + hi) * 0.5
        first, _rest = bezierTools.splitCubicAtT(p0, c1, c2, p3, mid)
        if float(bezierTools.approximateCubicArcLength(*first)) < target:
            lo = mid
        else:
            hi = mid
    return (lo + hi) * 0.5


def trim_seg_end(seg: Segment, amount: float) -> Segment:
    """Shorten a segment by `amount` measured back from its end point."""
    if amount <= 0:
        return seg
    if seg[0] == "curve":
        t = _cubic_split_t_for_arclen(seg, amount, from_start=False)
        first, _rest = bezierTools.splitCubicAtT(seg[1], seg[2], seg[3], seg[4], t)
        return ("curve", first[0], first[1], first[2], first[3])
    p0, p1 = seg[1], seg[2]
    u = norm(sub(p1, p0))
    return ("line", p0, sub(p1, mul(u, amount)))


def trim_seg_start(seg: Segment, amount: float) -> Segment:
    """Shorten a segment by `amount` measured forward from its start point."""
    if amount <= 0:
        return seg
    if seg[0] == "curve":
        t = _cubic_split_t_for_arclen(seg, amount, from_start=True)
        _first, rest = bezierTools.splitCubicAtT(seg[1], seg[2], seg[3], seg[4], t)
        return ("curve", rest[0], rest[1], rest[2], rest[3])
    p0, p1 = seg[1], seg[2]
    u = norm(sub(p1, p0))
    return ("line", add(p0, mul(u, amount)), p1)


def _depth_along(seg: Segment, at_end: bool, vertex: Point, axis: Point,
                 depth: float, max_cut: float) -> float:
    """
    Arc length to trim off ``seg`` so its free endpoint sits ``depth`` away from
    ``vertex`` measured along ``axis``. Bisection: depth grows monotonically as
    we walk away from the vertex.
    """
    lo, hi = 0.0, max_cut
    for _ in range(32):
        mid = 0.5 * (lo + hi)
        cut = trim_seg_end(seg, mid) if at_end else trim_seg_start(seg, mid)
        pt = seg_end(cut) if at_end else seg_start(cut)
        if dot(sub(pt, vertex), axis) < depth:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def _circular_scoop_cubic(p1: Point, p2: Point, apex: Point, radius: float) -> Optional[Segment]:
    """
    Cubic approximating a circular arc through ``p1``→``p2`` that bulges toward
    ``apex`` (the old notch tip).

    ``radius`` >= half-chord: larger radius is flatter; radius == half-chord is a
    semicircle (deepest scoop). Values below half-chord are clamped up.
    """
    chord_v = sub(p2, p1)
    c_len = dist(p1, p2)
    if c_len < 0.5:
        return None
    half = c_len / 2.0
    r_use = max(float(radius), half + 1e-3)
    mid = mul(add(p1, p2), 0.5)
    # Left normal of p1→p2; flip so it points toward the apex (into the notch).
    normal = norm((chord_v[1], -chord_v[0]))
    if normal == (0.0, 0.0):
        return None
    if dot(sub(apex, mid), normal) < 0:
        normal = mul(normal, -1.0)
    height = math.sqrt(max(0.0, r_use * r_use - half * half))
    # Center sits opposite the bulge so the minor arc runs toward the apex.
    center = sub(mid, mul(normal, height))

    def _tan_at(p: Point) -> Point:
        rad = sub(p, center)
        t = norm((-rad[1], rad[0]))
        if t == (0.0, 0.0):
            return (0.0, 0.0)
        if dot(t, chord_v) < 0:
            t = mul(t, -1.0)
        return t

    t1 = _tan_at(p1)
    t2 = _tan_at(p2)
    if t1 == (0.0, 0.0) or t2 == (0.0, 0.0):
        return None
    sweep = 2.0 * math.asin(min(1.0, half / r_use))
    handle = r_use * (4.0 / 3.0) * math.tan(max(sweep / 4.0, 1e-6))
    return ("curve", p1, add(p1, mul(t1, handle)), sub(p2, mul(t2, handle)), p2)


def _path_bounds_center(nodes: Sequence[Node]) -> Point:
    pts = oncurve_points_from_nodes(nodes)
    if not pts:
        return (0.0, 0.0)
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return (0.5 * (min(xs) + max(xs)), 0.5 * (min(ys) + max(ys)))


def fillet_mixed(nodes: List[Node], radius: float) -> Tuple[List[Node], int]:
    """
    Fillet concave corners in a contour, including joins where one or both
    sides are cubics (bowl-to-stem on a/e/u/r/m/n/g/s, etc.).

    Ordinary corners get a circular fillet of the requested radius. Near
    antiparallel *polyline* joins (ink-trap notches on H/E/F) grow a circular
    scoop. Stem–arch crotches (curve involved) stay ordinary fillets — never
    wedges. Near-flat G1 stem–bowl joins (u) get an inserted soft-inner.
    """
    segs = nodes_to_segments(nodes)
    m = len(segs)
    if m < 3:
        return nodes, 0

    on_pts = oncurve_points_from_nodes(nodes)
    feature = path_feature_size(on_pts)
    center = _path_bounds_center(nodes)
    lengths = [seg_length(s) for s in segs]
    hole = is_hole_path(nodes)

    def _stem_arch_soft_inner(
        j: int,
        nxt: int,
        u1: Point,
        u2: Point,
        vertex: Point,
        l1: float,
        l2: float,
        *,
        require_counter_side: bool,
    ) -> bool:
        """
        Insert a slider-radius soft-inner at stem↔bowl/arch joins.

        Ordinary circular-fillet math collapses on shallow (near-G1) kinks;
        cut back ~R on each flank and scoop into the black instead.

        ``require_counter_side``: for G1 near-flat joins, require glyph center
        to the right of travel (u bowl inners). Concave arch crotches already
        identify as inner corners, so they skip that check.
        """
        if hole:
            return False
        has_curve = segs[j][0] == "curve" or segs[nxt][0] == "curve"
        both_lines = segs[j][0] == "line" and segs[nxt][0] == "line"
        if not has_curve or both_lines:
            return False
        has_line = segs[j][0] == "line" or segs[nxt][0] == "line"
        # G1 near-flat: stem line ↔ bowl curve, tangents still co-directional.
        # Concave arch crotches are often near-antiparallel (dot < 0) — OK.
        if require_counter_side:
            if not has_line or dot(u1, u2) < 0.85:
                return False
        if has_line:
            line_seg = segs[j] if segs[j][0] == "line" else segs[nxt]
            line_dir = (
                seg_tangent_in(line_seg)
                if segs[j][0] == "line"
                else seg_tangent_out(line_seg)
            )
            if abs(line_dir[1]) < 0.75:
                return False
        left_n = norm((-u1[1], u1[0]))
        if left_n == (0.0, 0.0):
            return False
        if require_counter_side:
            right_n = norm((u1[1], -u1[0]))
            to_c = norm(sub(center, vertex))
            if (
                right_n == (0.0, 0.0)
                or to_c == (0.0, 0.0)
                or dot(right_n, to_c) < 0.15
            ):
                return False
        r_use = min(radius, 0.40 * min(l1, l2), 0.45 * feature)
        if r_use < 0.5:
            return False
        trim = min(r_use, min(l1, l2) * 0.35)
        if trim < 0.5:
            return False
        cut_end[j] = trim
        cut_start[nxt] = trim
        is_wedge[j] = True
        apexes[j] = add(vertex, mul(left_n, r_use))
        bridge_r[j] = r_use
        active.append(j)
        return True

    # Pass 1: decide which junctions get a fillet and how far each flank is cut.
    cut_end = [0.0] * m    # trimmed off the end of segment j
    cut_start = [0.0] * m  # trimmed off the start of segment j
    is_wedge = [False] * m
    apexes: List[Optional[Point]] = [None] * m
    bridge_r = [0.0] * m
    active: List[int] = []
    for j in range(m):
        nxt = (j + 1) % m
        u1 = seg_tangent_in(segs[j])
        u2 = seg_tangent_out(segs[nxt])
        if u1 == (0.0, 0.0) or u2 == (0.0, 0.0):
            continue
        l1, l2 = lengths[j], lengths[nxt]
        if l1 < 1 or l2 < 1:
            continue

        both_lines = segs[j][0] == "line" and segs[nxt][0] == "line"
        has_curve = segs[j][0] == "curve" or segs[nxt][0] == "curve"
        vertex = seg_end(segs[j])
        cr = cross(u1, u2)
        ang = math.atan2(cr, dot(u1, u2))
        phi = abs(ang)

        # Near-flat G1 stem–bowl (u bottoms): lower half + curve continues into
        # the bowl (not up into an n/h arch spring).
        if cr >= -1e-6 and phi < math.radians(18):
            bowl_ok = False
            if vertex[1] <= center[1]:
                if segs[j][0] == "curve" and seg_start(segs[j])[1] < vertex[1] - 10:
                    bowl_ok = True
                if segs[nxt][0] == "curve" and seg_end(segs[nxt])[1] < vertex[1] - 10:
                    bowl_ok = True
            if bowl_ok and _stem_arch_soft_inner(
                j, nxt, u1, u2, vertex, l1, l2, require_counter_side=True
            ):
                continue
            continue

        if cr >= -1e-6:
            continue  # convex: keep outer corners sharp
        if phi < math.radians(18) or phi > math.radians(178):
            continue
        tan_half = math.tan(phi / 2)
        if tan_half < 1e-9:
            continue

        axis = norm(add(mul(u1, -1.0), u2)) if phi > WEDGE_ANGLE else (0.0, 0.0)
        reach_a = dot(sub(seg_start(segs[j]), vertex), axis) if axis != (0.0, 0.0) else 0.0
        reach_b = dot(sub(seg_end(segs[nxt]), vertex), axis) if axis != (0.0, 0.0) else 0.0
        reach_min = min(reach_a, reach_b)

        # Ink-trap wedges: polyline-only (H/E/F notches).
        use_poly_wedge = (
            both_lines
            and axis != (0.0, 0.0)
            and 1.0 < reach_min <= WEDGE_MAX_REACH
        )
        # Stem–arch crotches: cubic flank + shallow tip. Open the mouth along
        # the notch axis, then bridge with a circular scoop of slider radius.
        use_arch_soft = (
            has_curve
            and not hole
            and axis != (0.0, 0.0)
            and 1.0 < reach_min <= WEDGE_MAX_REACH
            and phi > WEDGE_ANGLE
        )
        if use_poly_wedge or use_arch_soft:
            if use_arch_soft:
                r_use = min(radius, 0.45 * feature)
                if r_use < 0.5:
                    continue
                # Wider mouth than classic ink-trap so R reads at ~slider size.
                closed = min(0.55, (r_use * 1.35) / reach_min)
            else:
                r_use = angle_adjusted_radius(min(radius, 1.25 * feature), phi)
                if r_use < 0.5:
                    continue
                depth_gain = WEDGE_DEPTH_GAIN * max(
                    ACUTE_RADIUS_FLOOR, min(1.0, (math.pi - phi) / ACUTE_REF_ANGLE)
                )
                closed = min(0.65, radius * depth_gain / reach_min)
            depth_a = closed * reach_a
            depth_b = closed * reach_b
            if depth_a < 0.5 or depth_b < 0.5:
                continue
            a = _depth_along(segs[j], True, vertex, axis, depth_a, l1)
            b = _depth_along(segs[nxt], False, vertex, axis, depth_b, l2)
            if a < 0.5 or b < 0.5:
                continue
            cut_end[j] = a
            cut_start[nxt] = b
            is_wedge[j] = True
            apexes[j] = vertex
            bridge_r[j] = r_use
            active.append(j)
            continue

        r_use = angle_adjusted_radius(
            capped_radius(radius, l1, l2, feature), phi
        )
        if r_use < 0.5:
            continue
        trim = min(
            r_use * tan_half,
            min(l1, l2) * 0.40,
            acute_mouth_cap(radius, r_use),
        )
        if trim < 0.5:
            continue
        cut_end[j] = trim
        cut_start[nxt] = trim
        bridge_r[j] = (
            trim / tan_half if tan_half > 1e-9 else r_use
        )
        active.append(j)

    if not active:
        return nodes, 0

    # Two fillets sharing a segment cannot between them remove more than the
    # segment holds. Wedge flanks may vanish completely.
    for _ in range(12):
        worst = 1.0
        for j in range(m):
            used = cut_start[j] + cut_end[j]
            if used <= 0:
                continue
            wedge_touch = is_wedge[(j - 1) % m] or is_wedge[j]
            budget = lengths[j] * (1.0 if wedge_touch else SEG_TRIM_BUDGET)
            if used > budget:
                worst = min(worst, budget / used)
        if worst >= 0.999:
            break
        for j in range(m):
            cut_start[j] *= worst
            cut_end[j] *= worst
            bridge_r[j] *= worst

    active = [j for j in active if cut_end[j] >= 0.5 and cut_start[(j + 1) % m] >= 0.5]
    if not active:
        return nodes, 0
    live = set(active)
    for j in range(m):
        if j not in live:
            cut_end[j] = 0.0
        if (j - 1) % m not in live:
            cut_start[j] = 0.0

    # Pass 2: apply the cuts. A flank consumed end to end collapses to a point.
    trimmed: List[Segment] = []
    gone: List[bool] = []
    for j in range(m):
        seg = segs[j]
        remaining = lengths[j] - cut_start[j] - cut_end[j]
        if remaining < 0.5:
            head = trim_seg_start(seg, min(cut_start[j], lengths[j])) if cut_start[j] > 0 else seg
            pt = seg_start(head)
            trimmed.append(("line", pt, pt))
            gone.append(True)
            continue
        if cut_start[j] > 0:
            seg = trim_seg_start(seg, cut_start[j])
        if cut_end[j] > 0:
            seg = trim_seg_end(seg, cut_end[j])
        trimmed.append(seg)
        gone.append(False)

    def _tangent_in(idx: int) -> Point:
        for _ in range(m):
            if not gone[idx]:
                return seg_tangent_in(trimmed[idx])
            idx = (idx - 1) % m
        return (0.0, 0.0)

    def _tangent_out(idx: int) -> Point:
        for _ in range(m):
            if not gone[idx]:
                return seg_tangent_out(trimmed[idx])
            idx = (idx + 1) % m
        return (0.0, 0.0)

    # Pass 3: emit surviving segments; bridge gaps with circular fillets/scoops.
    out_segs: List[Segment] = []
    for j in range(m):
        if not gone[j]:
            out_segs.append(trimmed[j])
        if j not in live:
            continue
        nxt = (j + 1) % m
        p1 = seg_end(trimmed[j])
        p2 = seg_start(trimmed[nxt])
        chord = dist(p1, p2)
        if chord < 0.5:
            continue
        t1 = _tangent_in(j)
        t2 = _tangent_out(nxt)
        phi = 0.0
        if t1 != (0.0, 0.0) and t2 != (0.0, 0.0):
            phi = abs(math.atan2(cross(t1, t2), dot(t1, t2)))

        if is_wedge[j] and apexes[j] is not None:
            # Scoop toward the notch tip — never flatten to a chord.
            # Prefer the slider radius as the circle radius when the mouth is
            # wide enough (arch soft-inners). Otherwise fit a milder scoop to
            # the chord (classic ink-trap wedges on H/E/F).
            half = chord / 2.0
            if bridge_r[j] >= half + 1e-3:
                r_scoop = bridge_r[j]
            else:
                t = min(1.0, bridge_r[j] / 80.0)
                # Milder sagitta: t=0 → ~2.9*half; t=1 → ~1.7*half.
                r_scoop = half / (0.35 + 0.24 * t)
            scoop = _circular_scoop_cubic(p1, p2, apexes[j], r_scoop)
            if scoop is not None:
                out_segs.append(scoop)
                continue

        if t1 == (0.0, 0.0) or t2 == (0.0, 0.0):
            continue
        sin_half = math.sin(phi / 2)
        if sin_half < 1e-6:
            continue
        r_arc = chord / (2 * sin_half)
        handle = r_arc * (4.0 / 3.0) * math.tan(phi / 4.0)
        handle = min(handle, chord)
        cp1 = add(p1, mul(t1, handle))
        cp2 = sub(p2, mul(t2, handle))
        out_segs.append(("curve", p1, cp1, cp2, p2))

    return segments_to_nodes(out_segs), len(active)


# ---------------------------------------------------------------------------
# pathops merge
# ---------------------------------------------------------------------------

def nodes_to_pathops(nodes: Sequence[Node], closed: bool = True) -> pathops.Path:
    """
    Convert Glyphs nodes to a pathops.Path. Handles contours that start with
    offcurves (common for O/u): the closing cubic uses those leading handles.
    """
    path = pathops.Path()
    pen = path.getPen()
    n = len(nodes)
    on_indices = [i for i, nd in enumerate(nodes) if nd[2] != "o"]
    if not on_indices:
        return path

    start_i = on_indices[0]
    sx, sy, _ = nodes[start_i]
    pen.moveTo((sx, sy))

    for k in range(len(on_indices)):
        i_from = on_indices[k]
        i_to = on_indices[(k + 1) % len(on_indices)]
        between: List[Node] = []
        j = (i_from + 1) % n
        while j != i_to:
            between.append(nodes[j])
            j = (j + 1) % n
        tx, ty, _tt = nodes[i_to]
        closing = (k + 1) % len(on_indices) == 0
        if len(between) == 2 and between[0][2] == "o" and between[1][2] == "o":
            o1, o2 = between[0], between[1]
            pen.curveTo((o1[0], o1[1]), (o2[0], o2[1]), (tx, ty))
            if closing:
                break
        elif not between:
            if closing:
                break
            pen.lineTo((tx, ty))
        else:
            if closing:
                break
            pen.lineTo((tx, ty))

    if closed:
        pen.closePath()
    return path


def recording_to_node_paths(rec: RecordingPen) -> List[List[Node]]:
    paths: List[List[Node]] = []
    current: List[Node] = []
    pending_offs: List[Point] = []

    def flush():
        nonlocal current
        if current:
            # pathops closes contours by repeating the start point. Left in
            # place it becomes a zero-length segment, and fillet_nodes then
            # skips the corner it sits on (l1 < 1) — that is how the italic A
            # counter lost the round on its lower-left crotch.
            while (
                len(current) > 1
                and current[-1][2] == "l"
                and abs(current[-1][0] - current[0][0]) < 1e-6
                and abs(current[-1][1] - current[0][1]) < 1e-6
            ):
                current.pop()
            paths.append(current)
            current = []

    for op, args in rec.value:
        if op == "moveTo":
            flush()
            x, y = args[0]
            current = [(x, y, "l")]
            pending_offs = []
        elif op == "lineTo":
            x, y = args[0]
            current.append((x, y, "l"))
        elif op == "qCurveTo":
            # Convert TrueType-style quads to cubics (rare from pathops).
            pts = list(args)
            if not pts:
                continue
            on = pts[-1]
            offs = pts[:-1]
            if not offs:
                current.append((on[0], on[1], "l"))
            else:
                # Approximate each quad with a cubic
                prev = (current[-1][0], current[-1][1]) if current else offs[0]
                for oi, off in enumerate(offs):
                    next_on = on if oi == len(offs) - 1 else offs[oi + 1]
                    # mid on-curve for implied points if multiple offs
                    if oi < len(offs) - 1:
                        next_on = (
                            (off[0] + offs[oi + 1][0]) * 0.5,
                            (off[1] + offs[oi + 1][1]) * 0.5,
                        )
                    cp1 = (prev[0] + 2 / 3 * (off[0] - prev[0]), prev[1] + 2 / 3 * (off[1] - prev[1]))
                    cp2 = (next_on[0] + 2 / 3 * (off[0] - next_on[0]), next_on[1] + 2 / 3 * (off[1] - next_on[1]))
                    current.append((cp1[0], cp1[1], "o"))
                    current.append((cp2[0], cp2[1], "o"))
                    current.append((next_on[0], next_on[1], "c"))
                    prev = next_on
        elif op == "curveTo":
            # args: (cp1, cp2, pt) or multiple
            if len(args) == 3:
                cp1, cp2, pt = args
                current.append((cp1[0], cp1[1], "o"))
                current.append((cp2[0], cp2[1], "o"))
                current.append((pt[0], pt[1], "c"))
            else:
                # sequential triples
                pts = list(args)
                while len(pts) >= 3:
                    cp1, cp2, pt = pts[:3]
                    pts = pts[3:]
                    current.append((cp1[0], cp1[1], "o"))
                    current.append((cp2[0], cp2[1], "o"))
                    current.append((pt[0], pt[1], "c"))
        elif op == "closePath":
            flush()
        elif op == "endPath":
            flush()
    flush()
    return paths


# Fraction of a path's own area that may stick out of a candidate parent and
# still count as "nested". Boolean output is exact here, so this only absorbs
# floating-point noise along shared edges.
NESTED_LEAK_TOLERANCE = 1e-3


def path_is_nested(inner: pathops.Path, outer: pathops.Path) -> bool:
    """True when ``inner`` lies (essentially) completely inside ``outer``.

    Testing a single point is not enough. A crossbar drawn as its own shape
    (A, and any other letter built as silhouette + bar) starts inside the
    letter body but reaches past it, so a point test reports it as a counter
    and ``merge_paths`` subtracts it instead of unioning it — which is how the
    Sans italic A lost its counter (issue #78).
    """
    inner_area = abs(inner.area)
    if inner_area <= 1e-6:
        return False
    if abs(outer.area) <= inner_area + 1e-6:
        return False
    try:
        rec = RecordingPen()
        pathops.difference([inner], [outer], rec)
        leftover = pathops.Path()
        rec.replay(leftover.getPen())
    except Exception:
        return False
    return abs(leftover.area) <= inner_area * NESTED_LEAK_TOLERANCE


def path_depth_map(paths: Sequence[pathops.Path]) -> List[int]:
    n = len(paths)
    parent: List[Optional[int]] = [None] * n
    for i, p in enumerate(paths):
        candidates = []
        for j, q in enumerate(paths):
            if i == j:
                continue
            if path_is_nested(p, q):
                candidates.append(j)
        if candidates:
            parent[i] = min(candidates, key=lambda j: abs(paths[j].area))

    depths = [0] * n
    for i in range(n):
        d = 0
        k = i
        seen = set()
        while parent[k] is not None and k not in seen:
            seen.add(k)
            k = parent[k]  # type: ignore
            d += 1
            if d > 12:
                break
        depths[i] = d
    return depths


def _bounds_overlap(a: pathops.Path, b: pathops.Path, pad: float = 0.5) -> bool:
    ax0, ay0, ax1, ay1 = a.bounds
    bx0, by0, bx1, by1 = b.bounds
    return not (
        ax1 + pad < bx0
        or bx1 + pad < ax0
        or ay1 + pad < by0
        or by1 + pad < ay0
    )


def needs_additive_union(node_paths: List[List[Node]]) -> bool:
    """True when two non-nested paths overlap (e.g. t stem + crossbar)."""
    if len(node_paths) < 2:
        return False
    popaths = [nodes_to_pathops(nodes) for nodes in node_paths]
    depths = path_depth_map(popaths)
    for i in range(len(popaths)):
        for j in range(i + 1, len(popaths)):
            if depths[i] != depths[j]:
                continue
            if not _bounds_overlap(popaths[i], popaths[j]):
                continue
            # nested pairs have different depths; same-depth overlap => union
            pi = list(popaths[i].firstPoints)[0]
            pj = list(popaths[j].firstPoints)[0]
            if popaths[i].contains(pj) or popaths[j].contains(pi):
                continue
            return True
    return False


def merge_paths(node_paths: List[List[Node]]) -> List[List[Node]]:
    if not node_paths:
        return []
    if len(node_paths) == 1:
        return node_paths

    popaths = [nodes_to_pathops(nodes) for nodes in node_paths]
    depths = path_depth_map(popaths)
    subjects = [popaths[i] for i in range(len(popaths)) if depths[i] == 0]
    holes = [popaths[i] for i in range(len(popaths)) if depths[i] == 1]
    if not subjects:
        subjects = list(popaths)
        holes = []

    rec = RecordingPen()
    if holes:
        pathops.difference(subjects, holes, rec)
    elif len(subjects) == 1:
        subjects[0].draw(rec)
    else:
        pathops.union(subjects, rec)

    merged = recording_to_node_paths(rec)
    return merged if merged else node_paths


def resolve_paths(
    node_paths: List[List[Node]], *, cleanup_single: bool = True
) -> List[List[Node]]:
    """
    Remove-overlap / topology resolve (run before trap collapse + fillet):
    - 2+ paths: difference nested holes / union same-depth overlaps
    - 1 path: pathops.union cleanup (self-overlap / winding) when cleanup_single
    """
    if not node_paths:
        return []
    if len(node_paths) >= 2:
        return merge_paths(node_paths)
    if not cleanup_single:
        return node_paths
    try:
        p = nodes_to_pathops(node_paths[0])
        rec = RecordingPen()
        pathops.union([p], rec)
        cleaned = recording_to_node_paths(rec)
        return cleaned if cleaned else node_paths
    except Exception:
        return node_paths


def node_paths_to_evenodd_svg_d(paths: Sequence[Sequence[Node]]) -> str:
    """Flatten outers−holes to a compound SVG path suitable for fill-rule=evenodd."""
    node_paths = [list(p) for p in paths if p]
    if not node_paths:
        return ""
    popaths = [nodes_to_pathops(nodes) for nodes in node_paths]
    depths = path_depth_map(popaths)
    subjects = [popaths[i] for i in range(len(popaths)) if depths[i] == 0]
    holes = [popaths[i] for i in range(len(popaths)) if depths[i] >= 1]
    if not subjects:
        subjects = list(popaths)
        holes = []

    rec = RecordingPen()
    try:
        if holes:
            pathops.difference(subjects, holes, rec)
        elif len(subjects) > 1:
            pathops.union(subjects, rec)
        else:
            subjects[0].draw(rec)
    except Exception:
        # Fallback: concatenate individual contour ds
        parts = [nodes_to_svg_d(nodes) for nodes in node_paths]
        return " ".join(d for d in parts if d)

    merged = recording_to_node_paths(rec)
    if not merged:
        parts = [nodes_to_svg_d(nodes) for nodes in node_paths]
        return " ".join(d for d in parts if d)
    parts = [nodes_to_svg_d(nodes) for nodes in merged]
    return " ".join(d for d in parts if d)


# ---------------------------------------------------------------------------
# glyph file surgery
# ---------------------------------------------------------------------------

def _inside_background(prefix: str) -> bool:
    """Return True if current position is inside a background = { ... } block."""
    depth = 0
    i = 0
    while i < len(prefix):
        if prefix.startswith("background = {", i):
            depth += 1
            i += len("background = {")
            continue
        ch = prefix[i]
        if ch == "{" and depth > 0:
            depth += 1
        elif ch == "}" and depth > 0:
            depth -= 1
        i += 1
    return depth > 0


def _read_balanced(text: str, open_idx: int, open_ch: str, close_ch: str) -> Tuple[Optional[str], int]:
    if open_idx >= len(text) or text[open_idx] != open_ch:
        return None, -1
    depth = 0
    i = open_idx
    while i < len(text):
        ch = text[i]
        if ch == open_ch:
            depth += 1
        elif ch == close_ch:
            depth -= 1
            if depth == 0:
                return text[open_idx + 1 : i], i
        i += 1
    return None, -1


def parse_shape_dicts(shapes_body: str) -> List[dict]:
    """Parse individual shape { ... } dicts from a shapes = ( ... ) body."""
    shapes = []
    i = 0
    body = shapes_body
    while True:
        m = re.search(r"\{", body[i:])
        if not m:
            break
        start = i + m.start()
        dict_body, end = _read_balanced(body, start, "{", "}")
        if dict_body is None:
            break
        raw = body[start : end + 1]
        if "ref = " in raw:
            shapes.append(
                {
                    "component": True,
                    "raw": raw,
                    "closed": False,
                    "nodes": [],
                }
            )
        else:
            closed_m = re.search(r"closed = ([01]);", raw)
            closed = bool(int(closed_m.group(1))) if closed_m else True
            nm = re.search(r"nodes = \((.*?)\n\)\s*;", raw, re.S)
            if not nm:
                nm = re.search(r"nodes = \((.*?)\)\s*;", raw, re.S)
            nodes = parse_nodes(nm.group(1)) if nm else []
            shapes.append(
                {
                    "component": False,
                    "raw": raw,
                    "closed": closed,
                    "nodes": nodes,
                }
            )
        i = end + 1
    return shapes


def format_shape(closed: bool, nodes: Sequence[Node]) -> str:
    node_str = format_nodes(nodes)
    lines = ["{", f"closed = {1 if closed else 0};"]
    nlines = node_str.splitlines()
    lines.append(nlines[0])
    for line in nlines[1:-1]:
        lines.append(line)
    lines.append(nlines[-1] + ";")
    lines.append("}")
    return "\n".join(lines)


def process_layer_shapes(
    shapes_body: str, radius: float
) -> Tuple[Optional[str], int, int]:
    """
    Returns (new_shapes_body|None, fillets, path_count).
    new_shapes_body is None when geometry is unchanged.
    Components are preserved as-is; path shapes are rewritten only when needed.

    Order: remove-overlap → ink-trap collapse → fillet outers and holes.
    """
    shapes = parse_shape_dicts(shapes_body)
    if not shapes:
        return None, 0, 0
    if any(s["component"] for s in shapes):
        # leave composite glyphs alone (i/j); process idotless separately
        return None, 0, 0

    # Ink traps grow with weight; allow larger collapse window for Black.
    max_short = max(160.0, radius * 10.0)

    prepared: List[List[Node]] = []
    for s in shapes:
        nodes = s["nodes"]
        if not nodes:
            continue
        prepared.append(nodes)

    if not prepared:
        return None, 0, 0

    # 1) Remove overlap / resolve topology first (always, including single paths).
    merged = resolve_paths(prepared, cleanup_single=True)
    if len(merged) != len(prepared):
        did_merge = True
    else:
        did_merge = any(
            _nodes_geometry_changed(a, b) for a, b in zip(prepared, merged)
        )

    # 2) Collapse ink traps on outers (single-path Geist notches survive boolean).
    notches_collapsed = False
    after_traps: List[List[Node]] = []
    for nodes in merged:
        if is_hole_path(nodes):
            after_traps.append(nodes)
            continue
        collapsed = collapse_ink_traps_nodes(nodes, max_short=max_short)
        if _nodes_geometry_changed(nodes, collapsed):
            notches_collapsed = True
        after_traps.append(collapsed)

    # 3) Fillet concave corners on outers and holes (D counters live on holes).
    total_fillets = 0
    out_paths: List[List[Node]] = []
    for nodes in after_traps:
        new_nodes, count = fillet_nodes(nodes, radius)
        total_fillets += count
        out_paths.append(_drop_zero_length_oncurves(new_nodes))

    if total_fillets == 0 and not notches_collapsed and not did_merge:
        return None, 0, len(out_paths)

    out_shapes = [format_shape(True, nodes) for nodes in out_paths]
    # Glyphs arrays need commas between shape dicts.
    joined = ",\n".join(out_shapes)
    new_body = "\n" + joined + "\n"
    return new_body, total_fillets, len(out_shapes)


def _iter_layer_regions(text: str) -> List[Tuple[str, int, int]]:
    """Return (layer_id, region_start, region_end) for each layerId block."""
    regions = []
    for m in re.finditer(r'layerId = "([^"]+)";', text):
        layer_id = m.group(1)
        next_m = re.search(r'layerId = "', text[m.end() :])
        layer_end = m.end() + next_m.start() if next_m else len(text)
        regions.append((layer_id, m.end(), layer_end))
    return regions


def _find_foreground_shapes(
    text: str, region_start: int, layer_end: int
) -> Optional[Tuple[int, int, str]]:
    region = text[region_start:layer_end]
    pos = 0
    while True:
        sm = re.search(r"shapes = \(", region[pos:])
        if not sm:
            return None
        abs_kw = region_start + pos + sm.start()
        abs_paren = region_start + pos + sm.end() - 1
        prefix = text[region_start:abs_kw]
        if _inside_background(prefix):
            pos += sm.end()
            continue
        body, close_i = _read_balanced(text, abs_paren, "(", ")")
        if body is None:
            return None
        return abs_paren + 1, close_i, body


def _find_background_shapes(
    text: str, layer_id_pos: int
) -> Optional[str]:
    """
    Background usually sits just before layerId in the same layer dict.
    Search backward from layerId for background = { ... shapes = ( ... ) }.
    """
    window_start = max(0, layer_id_pos - 8000)
    window = text[window_start:layer_id_pos]
    # last background block in the window
    matches = list(re.finditer(r"background = \{", window))
    if not matches:
        return None
    bg_rel = matches[-1].start()
    bg_abs = window_start + bg_rel
    bg_body, bg_end = _read_balanced(text, bg_abs + len("background = "), "{", "}")
    if bg_body is None:
        return None
    sm = re.search(r"shapes = \(", bg_body)
    if not sm:
        return None
    # paren index inside bg_body
    paren_in_bg = sm.end() - 1
    shapes_body, _ = _read_balanced(bg_body, paren_in_bg, "(", ")")
    return shapes_body


def restore_foreground_from_background(path: Path, write: bool) -> Tuple[bool, str]:
    """Copy each layer's background shapes into foreground (undo prior fillet passes)."""
    text = path.read_text(encoding="utf-8")
    if "background = {" not in text:
        return False, "no background"
    # Need layerId positions for background lookup
    replacements = []  # (fg_start, fg_end, new_body)
    restored = 0
    for m in re.finditer(r'layerId = "([^"]+)";', text):
        layer_id = m.group(1)
        next_m = re.search(r'layerId = "', text[m.end() :])
        layer_end = m.end() + next_m.start() if next_m else len(text)
        bg_body = _find_background_shapes(text, m.start())
        if bg_body is None:
            continue
        fg = _find_foreground_shapes(text, m.end(), layer_end)
        if fg is None:
            continue
        fg_start, fg_end, fg_body = fg
        if fg_body == bg_body:
            continue
        # Never replace path outlines with component backgrounds (or vice versa).
        bg_has_paths = "nodes = (" in bg_body
        fg_has_paths = "nodes = (" in fg_body
        bg_has_refs = "ref = " in bg_body
        fg_has_refs = "ref = " in fg_body
        if bg_has_refs and not bg_has_paths and fg_has_paths:
            continue
        if fg_has_refs and not fg_has_paths and bg_has_paths:
            continue
        if bg_has_paths and fg_has_paths:
            if bg_body.count("closed =") != fg_body.count("closed =") and (
                "o)," in fg_body or ",c)" in fg_body or ",cs)" in fg_body
            ):
                # Allow restore when foreground was filleted (curves present)
                # even if path count changed due to prior union — only if bg is polyline-heavy.
                pass
        replacements.append((fg_start, fg_end, bg_body, layer_id))
        restored += 1

    if not replacements:
        return False, "already original / no bg shapes"

    new_text = text
    for fg_start, fg_end, bg_body, _layer_id in reversed(replacements):
        if write:
            new_text = new_text[:fg_start] + bg_body + new_text[fg_end:]

    if write and new_text != text:
        path.write_text(new_text, encoding="utf-8")
    return True, f"restored {restored} layer(s) from background"


def process_glyph_file(
    path: Path, radius: float, write: bool, restore: bool = False
) -> Tuple[bool, str]:
    reports_prefix = []
    if restore:
        restored, rinfo = restore_foreground_from_background(path, write=write)
        if restored:
            reports_prefix.append(rinfo)
        elif write:
            # still try fillet; report restore status
            reports_prefix.append(rinfo)

    text = path.read_text(encoding="utf-8")
    if "ref = " in text and "nodes = (" not in text:
        return False, "component-only (skipped)"

    sections = []
    for layer_id, region_start, layer_end in _iter_layer_regions(text):
        found = _find_foreground_shapes(text, region_start, layer_end)
        if found:
            body_start, body_end, body = found
            sections.append((layer_id, body_start, body_end, body))

    if not sections:
        return False, "no path shapes"

    # Apply from end to start so offsets stay valid
    new_text = text
    total_fillets = 0
    any_geometry = False
    reports = list(reports_prefix)
    for layer_id, body_start, body_end, body in reversed(sections):
        scale = master_radius_scale(layer_id)
        layer_radius = radius * scale
        new_body, fillets, npaths = process_layer_shapes(body, layer_radius)
        total_fillets += fillets
        if new_body is not None:
            any_geometry = True
            reports.append(
                f"{layer_id[:8]}… r={layer_radius:.1f} fillets={fillets} paths={npaths}"
            )
            if write:
                new_text = new_text[:body_start] + new_body + new_text[body_end:]
        else:
            reports.append(f"{layer_id[:8]}… r={layer_radius:.1f} unchanged")

    new_text = repair_shapes_array_commas(new_text)
    changed = write and new_text != text
    if changed:
        path.write_text(new_text, encoding="utf-8")

    return any_geometry or changed or bool(reports_prefix), "; ".join(reports)


def repair_shapes_array_commas(text: str) -> str:
    """Insert missing commas between consecutive {…} dicts in OpenStep arrays.

    Glyphs rejects packages when shape arrays contain `}\\n{` instead of `},\\n{`.
    """
    fixed = re.sub(r"\}(\s*)\{", r"},\1{", text)
    fixed = re.sub(r"\},(\s*),(\s*)\{", r"},\1{", fixed)
    return fixed


# ---------------------------------------------------------------------------
# Library API (in-memory / export from a source package)
# ---------------------------------------------------------------------------

def default_original_package() -> Path:
    here = Path(__file__).resolve().parent
    return here.parent / "originals" / "geist" / "sources" / "Geist.glyphspackage"


def default_package() -> Path:
    here = Path(__file__).resolve().parent
    return here.parent / "sources" / "NamcheShadowSans.glyphspackage"


def apply_radius_to_glyph_text(text: str, radius: float) -> Tuple[str, int]:
    """Return (new_text, total_fillets) applying inner rounds to all masters."""
    if "ref = " in text and "nodes = (" not in text:
        return text, 0

    sections = []
    for layer_id, region_start, layer_end in _iter_layer_regions(text):
        found = _find_foreground_shapes(text, region_start, layer_end)
        if found:
            body_start, body_end, body = found
            sections.append((layer_id, body_start, body_end, body))

    if not sections:
        return text, 0

    new_text = text
    total_fillets = 0
    for layer_id, body_start, body_end, body in reversed(sections):
        scale = master_radius_scale(layer_id)
        layer_radius = radius * scale
        new_body, fillets, _npaths = process_layer_shapes(body, layer_radius)
        total_fillets += fillets
        if new_body is not None:
            new_text = new_text[:body_start] + new_body + new_text[body_end:]
    return repair_shapes_array_commas(new_text), total_fillets


def _resolve_glyph_name(ch: str) -> Optional[str]:
    if ch == " ":
        return None
    if ch in DIGIT_NAMES:
        return DIGIT_NAMES[ch]
    if ch == "i":
        return "idotless"
    if ch == "j":
        return "jdotless"
    if re.fullmatch(r"[A-Za-z]", ch):
        return ch
    return None


def glyphs_for_string(s: str) -> List[str]:
    names = []
    seen = set()
    for ch in s:
        name = _resolve_glyph_name(ch)
        if name and name not in seen:
            seen.add(name)
            names.append(name)
    return names


def load_filleted_layer(
    package: Path,
    glyph_name: str,
    master: str,
    radius: float,
) -> Tuple[List[List[Node]], float]:
    """
    Load a glyph from package, apply radius in memory, return (paths, width)
    for the requested master (Thin/Regular/Black).
    """
    wanted_layer = MASTER_IDS.get(master, MASTER_IDS["Regular"])
    fp = package / "glyphs" / glyph_filename(glyph_name)
    if not fp.exists():
        return [], 0.0
    text = fp.read_text(encoding="utf-8")
    # Always run (even at radius 0) so ink-trap collapse + boolean resolve apply.
    text, _ = apply_radius_to_glyph_text(text, radius)

    m = re.search(rf'layerId = "{re.escape(wanted_layer)}";', text)
    if not m:
        m = re.search(r'layerId = "([^"]+)";', text)
        if not m:
            return [], 0.0

    region_start = m.end()
    next_m = re.search(r'layerId = "', text[region_start:])
    layer_end = region_start + next_m.start() if next_m else len(text)
    wm = re.search(r"width = ([0-9.]+);", text[m.start() : layer_end])
    width = float(wm.group(1)) if wm else 500.0

    fg = _find_foreground_shapes(text, region_start, layer_end)
    if fg is None:
        return [], width
    _a, _b, body = fg
    paths: List[List[Node]] = []
    for s in parse_shape_dicts(body):
        if s["component"]:
            ref_m = re.search(r"ref = ([^;]+);", s["raw"])
            if not ref_m:
                continue
            ref_name = ref_m.group(1).strip()
            scale_m = re.search(r"scale = \(([^,]+),([^)]+)\);", s["raw"])
            pos_m = re.search(r"pos = \(([^,]+),([^)]+)\);", s["raw"])
            sub_paths, _ = load_filleted_layer(package, ref_name, master, radius)
            ox = float(pos_m.group(1)) if pos_m else 0.0
            oy = float(pos_m.group(2)) if pos_m else 0.0
            sx = float(scale_m.group(1)) if scale_m else 1.0
            sy = float(scale_m.group(2)) if scale_m else 1.0
            for nodes in sub_paths:
                transformed = [
                    (x * sx + ox, y * sy + oy, t) for x, y, t in nodes
                ]
                paths.append(transformed)
            continue
        if s["nodes"]:
            paths.append(s["nodes"])
    return paths, width


def nodes_to_svg_d(nodes: Sequence[Node]) -> str:
    """
    Convert Glyphs nodes to an SVG path. Handles closed cubic contours that
    start with offcurves (common for O/zero): closing segment uses leading offs.
    """
    n = len(nodes)
    if n == 0:
        return ""
    on_indices = [i for i, nd in enumerate(nodes) if nd[2] != "o"]
    if not on_indices:
        return ""

    start_i = on_indices[0]
    sx, sy, _ = nodes[start_i]
    parts = [f"M{sx:.1f} {sy:.1f}"]

    for k in range(len(on_indices)):
        i_from = on_indices[k]
        i_to = on_indices[(k + 1) % len(on_indices)]
        between: List[Node] = []
        j = (i_from + 1) % n
        while j != i_to:
            between.append(nodes[j])
            j = (j + 1) % n
        tx, ty, _tt = nodes[i_to]
        closing = (k + 1) % len(on_indices) == 0
        if len(between) == 2 and between[0][2] == "o" and between[1][2] == "o":
            o1, o2 = between[0], between[1]
            parts.append(
                f"C{o1[0]:.1f} {o1[1]:.1f} {o2[0]:.1f} {o2[1]:.1f} {tx:.1f} {ty:.1f}"
            )
            if closing:
                break
        elif not between:
            if closing:
                break
            parts.append(f"L{tx:.1f} {ty:.1f}")
        else:
            if closing:
                break
            parts.append(f"L{tx:.1f} {ty:.1f}")

    parts.append("Z")
    return " ".join(parts)


# Cache: package path → masterId → leftKey → rightKey → value
_KERN_CACHE: dict = {}
# Cache: package path → glyph name → (kernLeft, kernRight)
_KERN_GROUP_CACHE: dict = {}


def _strip_glyphs_name(token: str) -> str:
    token = token.strip()
    if len(token) >= 2 and token[0] == '"' and token[-1] == '"':
        return token[1:-1]
    return token


def _load_kerning_table(package: Path, master: str) -> dict:
    """Parse kerningLTR for one master into {leftKey: {rightKey: value}}."""
    master_id = MASTER_IDS.get(master, MASTER_IDS["Regular"])
    cache_key = (str(package.resolve()), master_id)
    if cache_key in _KERN_CACHE:
        return _KERN_CACHE[cache_key]

    info = package / "fontinfo.plist"
    table: dict = {}
    if not info.is_file():
        _KERN_CACHE[cache_key] = table
        return table

    text = info.read_text(encoding="utf-8")
    m = re.search(r"kerningLTR\s*=\s*\{", text)
    if not m:
        _KERN_CACHE[cache_key] = table
        return table

    # Master block: "UUID" = { ... };
    master_m = re.search(
        rf'"{re.escape(master_id)}"\s*=\s*\{{', text[m.end() :]
    )
    if not master_m:
        _KERN_CACHE[cache_key] = table
        return table
    start = m.end() + master_m.end()
    depth = 1
    i = start
    while i < len(text) and depth:
        ch = text[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
        i += 1
    block = text[start : i - 1]

    # Entries: "left" = { "right" = -12; ... };
    for left_m in re.finditer(
        r'("(?:\\.|[^"])*"|[A-Za-z0-9_.@-]+)\s*=\s*\{', block
    ):
        left_key = _strip_glyphs_name(left_m.group(1))
        sub_start = left_m.end()
        depth = 1
        j = sub_start
        while j < len(block) and depth:
            if block[j] == "{":
                depth += 1
            elif block[j] == "}":
                depth -= 1
            j += 1
        sub = block[sub_start : j - 1]
        rights: dict = {}
        for rm in re.finditer(
            r'("(?:\\.|[^"])*"|[A-Za-z0-9_.@-]+)\s*=\s*(-?\d+(?:\.\d+)?)\s*;',
            sub,
        ):
            rights[_strip_glyphs_name(rm.group(1))] = float(rm.group(2))
        if rights:
            table[left_key] = rights

    _KERN_CACHE[cache_key] = table
    return table


def _glyph_kern_groups(package: Path, glyph_name: str) -> Tuple[Optional[str], Optional[str]]:
    """Return (kernLeft, kernRight) group names for a glyph."""
    cache_key = (str(package.resolve()), glyph_name)
    if cache_key in _KERN_GROUP_CACHE:
        return _KERN_GROUP_CACHE[cache_key]
    fp = package / "glyphs" / glyph_filename(glyph_name)
    left = right = None
    if fp.is_file():
        text = fp.read_text(encoding="utf-8")
        lm = re.search(r"kernLeft\s*=\s*([^;]+);", text)
        rm = re.search(r"kernRight\s*=\s*([^;]+);", text)
        if lm:
            left = _strip_glyphs_name(lm.group(1))
        if rm:
            right = _strip_glyphs_name(rm.group(1))
    _KERN_GROUP_CACHE[cache_key] = (left, right)
    return left, right


def _pair_kern(
    table: dict,
    package: Path,
    left_name: Optional[str],
    right_name: Optional[str],
) -> float:
    """Glyphs-style kerning lookup (glyph or @MMK_L_/@MMK_R_ class keys)."""
    if not left_name or not right_name or not table:
        return 0.0
    _l_left, l_right = _glyph_kern_groups(package, left_name)
    r_left, _r_right = _glyph_kern_groups(package, right_name)
    left_keys = [left_name]
    if l_right:
        left_keys.append(f"@MMK_L_{l_right}")
    right_keys = [right_name]
    if r_left:
        right_keys.append(f"@MMK_R_{r_left}")
    for lk in left_keys:
        rights = table.get(lk)
        if not rights:
            continue
        for rk in right_keys:
            if rk in rights:
                return float(rights[rk])
    return 0.0


def _space_width(package: Path, master: str) -> float:
    fp = package / "glyphs" / "space.glyph"
    if not fp.is_file():
        return 250.0
    text = fp.read_text(encoding="utf-8")
    layer_id = MASTER_IDS.get(master, MASTER_IDS["Regular"])
    wm = re.search(
        rf'layerId = "{re.escape(layer_id)}";[\s\S]*?width = ([0-9.]+);',
        text,
    )
    if wm:
        return float(wm.group(1))
    wm = re.search(r"width = ([0-9.]+);", text)
    return float(wm.group(1)) if wm else 250.0


def render_preview_svg(
    package: Path,
    preview_text: str,
    radius: float,
    master: str = "Regular",
    fill: str = "#e8ebe4",
    background: str = "#0a0a0a",
) -> str:
    """Render a proof string as SVG using real advances + Geist kerning."""
    parts: List[str] = []
    x_cursor = 0.0
    kern_table = _load_kerning_table(package, master)
    space_w = _space_width(package, master)
    prev_name: Optional[str] = None

    for ch in preview_text:
        if ch == " ":
            x_cursor += space_w
            prev_name = None
            continue
        name = _resolve_glyph_name(ch)
        if not name:
            x_cursor += space_w
            prev_name = None
            continue

        kern = _pair_kern(kern_table, package, prev_name, name)
        x_cursor += kern

        paths, width = load_filleted_layer(package, name, master, radius)
        # Single evenodd compound path so counters stay open in every SVG host.
        d = node_paths_to_evenodd_svg_d(paths)
        if d:
            parts.append(
                f'<g transform="translate({x_cursor:.1f},0)">'
                f'<path d="{d}" fill="{fill}" fill-rule="evenodd"/>'
                f"</g>"
            )
        if ch == "i":
            # crude tittle
            parts.append(
                f'<g transform="translate({x_cursor:.1f},0)" fill="{fill}">'
                f'<rect x="85" y="580" width="70" height="70"/></g>'
            )
            ip = package / "glyphs" / "i.glyph"
            if ip.exists():
                it = ip.read_text(encoding="utf-8")
                layer_id = MASTER_IDS.get(master, MASTER_IDS["Regular"])
                wm = re.search(
                    rf'layerId = "{re.escape(layer_id)}";[\s\S]*?width = ([0-9.]+);',
                    it,
                )
                if wm:
                    width = float(wm.group(1))
        x_cursor += width
        prev_name = name

    vb_w = max(x_cursor + 80, 400)
    vb_h = 900
    return (
        f'<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {vb_w:.0f} {vb_h}" '
        f'width="100%" height="100%" preserveAspectRatio="xMidYMid meet">\n'
        f'<rect width="100%" height="100%" fill="{background}"/>\n'
        f'<g transform="translate(40,{vb_h - 120}) scale(1,-1)">\n'
        f'{"".join(parts)}\n'
        f"</g>\n</svg>\n"
    )


def apply_family_name(
    package: Path,
    family_name: str = FAMILY_NAME,
    source_family: str = SOURCE_FAMILY_NAME,
) -> None:
    """Rewrite Glyphs familyName / VF fileName from source family to delivery name."""
    info = package / "fontinfo.plist"
    if not info.is_file():
        return
    text = info.read_text(encoding="utf-8")
    # Quoted or bare familyName assignment
    text = re.sub(
        rf'(familyName\s*=\s*)(?:"{re.escape(source_family)}"|{re.escape(source_family)})\s*;',
        rf'\1"{family_name}";',
        text,
        count=1,
    )
    text = text.replace(f'"{source_family}[wght]"', f'"{family_name}[wght]"')
    info.write_text(text, encoding="utf-8")


def export_dir_name(radius: float) -> str:
    return f"{FAMILY_NAME}-r{int(round(radius))}"


def export_filleted_package(
    source_package: Path,
    dest_dir: Path,
    radius: float,
    glyph_names: Optional[Sequence[str]] = None,
    family_name: str = FAMILY_NAME,
) -> Path:
    """
    Copy pristine package to dest_dir/{family}.glyphspackage, rename family, apply fillets.
    Returns path to the written glyphspackage.
    """
    import shutil

    names = list(glyph_names) if glyph_names is not None else list(PROOF_GLYPHS)
    dest_pkg = dest_dir / f"{family_name}.glyphspackage"
    if dest_pkg.exists():
        shutil.rmtree(dest_pkg)
    dest_dir.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source_package, dest_pkg)
    apply_family_name(dest_pkg, family_name=family_name)

    glyphs_dir = dest_pkg / "glyphs"
    for name in names:
        fp = glyphs_dir / glyph_filename(name)
        if not fp.exists():
            continue
        text = fp.read_text(encoding="utf-8")
        new_text, _fillets = apply_radius_to_glyph_text(text, radius)
        if new_text != text:
            fp.write_text(new_text, encoding="utf-8")
    return dest_pkg


def _delivery_ttf_name(path: Path, family_name: str = FAMILY_NAME) -> Path:
    """Map Geist-*.ttf → Namche-Shadow-*.ttf when needed."""
    name = path.name
    if name.startswith(f"{SOURCE_FAMILY_NAME}-") or name.startswith(f"{SOURCE_FAMILY_NAME}["):
        name = family_name + name[len(SOURCE_FAMILY_NAME) :]
    elif name.startswith(SOURCE_FAMILY_NAME) and not name.startswith(family_name):
        name = family_name + name[len(SOURCE_FAMILY_NAME) :]
    return path.with_name(name)


def build_ttfs_from_glyphspackage(
    glyphspackage: Path, out_ttf_dir: Path, family_name: str = FAMILY_NAME
) -> List[Path]:
    """
    Build static + variable TTFs with fontmake if available.
    Returns list of written font paths (may be empty if fontmake missing).
    """
    import shutil
    import subprocess
    import tempfile

    out_ttf_dir.mkdir(parents=True, exist_ok=True)
    written: List[Path] = []

    # Prefer project venv if present
    venv_fontmake = Path(__file__).resolve().parent.parent / ".venv-inner-round" / "bin" / "fontmake"
    venv_python = Path(__file__).resolve().parent.parent / ".venv-inner-round" / "bin" / "python"
    if venv_fontmake.is_file():
        cmd_prefix = [str(venv_fontmake)]
    elif shutil.which("fontmake"):
        cmd_prefix = [shutil.which("fontmake")]
    elif venv_python.is_file():
        cmd_prefix = [str(venv_python), "-m", "fontmake"]
    else:
        try:
            subprocess.run(
                [sys.executable, "-m", "fontmake", "--help"],
                check=True,
                capture_output=True,
            )
            cmd_prefix = [sys.executable, "-m", "fontmake"]
        except Exception:
            return written

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        # Master TTFs (no interpolation). Variable/instances can still fail when
        # feature-capped fillets produce different point counts across masters.
        try:
            proc = subprocess.run(
                cmd_prefix
                + [
                    "-g",
                    str(glyphspackage),
                    "-o",
                    "ttf",
                    "--output-dir",
                    str(tmp_path / "ttf"),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            if proc.returncode != 0:
                sys.stderr.write(
                    "fontmake masters failed:\n"
                    + (proc.stderr or proc.stdout or "")[-2000:]
                    + "\n"
                )
            else:
                for f in (tmp_path / "ttf").rglob("*.ttf"):
                    dest = _delivery_ttf_name(out_ttf_dir / f.name, family_name)
                    shutil.copy2(f, dest)
                    written.append(dest)
        except Exception as exc:
            sys.stderr.write(f"fontmake masters failed: {exc}\n")

        # Best-effort variable (may fail on master incompatibility)
        try:
            proc = subprocess.run(
                cmd_prefix
                + [
                    "-g",
                    str(glyphspackage),
                    "-o",
                    "variable",
                    "--output-dir",
                    str(tmp_path / "variable"),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            if proc.returncode == 0:
                for f in (tmp_path / "variable").glob("*.ttf"):
                    dest = _delivery_ttf_name(out_ttf_dir / f.name, family_name)
                    shutil.copy2(f, dest)
                    written.append(dest)
            else:
                sys.stderr.write(
                    "fontmake variable skipped (masters not compatible after filleting)\n"
                )
        except Exception as exc:
            sys.stderr.write(f"fontmake variable failed: {exc}\n")

    return written


def reset_working_sources_from_original(
    original: Path, working: Path
) -> None:
    import shutil

    if working.exists():
        shutil.rmtree(working)
    shutil.copytree(original, working)


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--package",
        type=Path,
        default=default_package(),
        help="Path to NamcheShadowSans.glyphspackage",
    )
    ap.add_argument(
        "--radius",
        type=float,
        default=40.0,
        help="Fillet radius in UPM (constant across masters; default 40)",
    )
    ap.add_argument(
        "--glyphs",
        nargs="*",
        default=None,
        help="Glyph names to process (default: proof set)",
    )
    ap.add_argument(
        "--italic-recipe",
        action="store_true",
        help=(
            "Use the fillet profile that baked the Sans italic masters "
            "(plain circular fillet, Black scale 1.35). Reproduces every "
            "straight-sided italic master; the curve-carrying glyphs have "
            "since drifted."
        ),
    )
    ap.add_argument("--write", action="store_true", help="Write changes to .glyph files")
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="Report only (default if --write not set)",
    )
    ap.add_argument(
        "--restore-from-background",
        action="store_true",
        help="Reset foreground outlines from background before filleting (needed to change radius)",
    )
    ap.add_argument(
        "--reset-sources",
        action="store_true",
        help="Replace the working Namche source with the immutable original Geist copy and exit",
    )
    ap.add_argument(
        "--original",
        type=Path,
        default=None,
        help="Path to pristine Geist.glyphspackage (default: originals/geist/...)",
    )
    args = ap.parse_args(argv)

    global ITALIC_RECIPE
    ITALIC_RECIPE = bool(args.italic_recipe)

    if args.reset_sources:
        original = args.original or default_original_package()
        working = args.package
        if not original.is_dir():
            sys.stderr.write(f"Original package not found: {original}\n")
            return 1
        reset_working_sources_from_original(original, working)
        print(f"Reset {working} from {original}")
        return 0

    write = bool(args.write) and not args.dry_run
    glyphs_dir = args.package / "glyphs"
    if not glyphs_dir.is_dir():
        sys.stderr.write(f"Glyphs folder not found: {glyphs_dir}\n")
        return 1

    names = args.glyphs if args.glyphs else list(PROOF_GLYPHS)
    print(
        f"{'WRITE' if write else 'DRY-RUN'}  package={args.package}  radius={args.radius}  "
        f"restore={args.restore_from_background}  "
        f"profile={'italic' if ITALIC_RECIPE else 'upright'}  glyphs={len(names)}"
    )

    touched = 0
    for name in names:
        fp = glyphs_dir / glyph_filename(name)
        if not fp.exists():
            print(f"  MISS  {name}")
            continue
        try:
            changed, info = process_glyph_file(
                fp,
                args.radius,
                write=write,
                restore=args.restore_from_background,
            )
        except Exception as exc:
            print(f"  FAIL  {name}: {exc}")
            continue
        mark = "OK" if changed else "—"
        if changed:
            touched += 1
        print(f"  {mark:3}  {name}: {info}")

    print(f"Done. {'Wrote' if write else 'Would touch'} ~{touched} glyphs.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
