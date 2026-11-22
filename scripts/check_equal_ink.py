#!/usr/bin/env python3
"""Measure directional ink loss and surviving counters in Sans release fonts.

Both input directories are expected to have the repository release layout:
``ttf/`` and ``variable/``. At every requested weight the tool checks both
variable-font instances; named weights are additionally checked in their direct
static TTFs. ``--include-otf-statics`` additionally checks matching files in
``otf/``; every selected static requires a matching clean baseline. The default
backend adaptively flattens curves to a recorded
0.01-unit distance bound and uses independent double-precision GEOS booleans.
Noded contour faces are selected by nonzero winding, retaining nested islands
and overlapping bars. The optional outline-distance allowance dilates only the
candidate; raw directional ink loss remains in the JSON report. Choose a
nonzero distance from a measured conversion/quantization bound, never from an
area budget. PathOps remains available only as an explicit cross-check.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from dataclasses import asdict, dataclass
import json
import math
from pathlib import Path
import sys
from typing import Iterable

from fontTools.pens.basePen import BasePen
from fontTools.pens.recordingPen import DecomposingRecordingPen
from fontTools.ttLib import TTFont

try:
    from .latin_core import CODEPOINTS
except ImportError:
    from latin_core import CODEPOINTS

DEFAULT_FLATTEN_TOLERANCE = 0.01
COUNTER_NOISE_AREA = 0.001  # Ignore only sub-millifont-unit-square numerical holes.


DEFAULT_WEIGHTS = (100, 150, 200, 250, 300, 350, 400, 450, 500, 550, 600,
                   650, 700, 750, 800, 850, 900)
WEIGHT_STYLES = {
    100: ("Thin", "ThinItalic"),
    200: ("ExtraLight", "ExtraLightItalic"),
    300: ("Light", "LightItalic"),
    400: ("Regular", "Italic"),
    500: ("Medium", "MediumItalic"),
    600: ("SemiBold", "SemiBoldItalic"),
    700: ("Bold", "BoldItalic"),
    800: ("ExtraBold", "ExtraBoldItalic"),
    900: ("Black", "BlackItalic"),
}
VF_FILENAMES = {
    "upright": "NamcheShadowSans[wght].ttf",
    "italic": "NamcheShadowSans-Italic[wght].ttf",
}
STYLE_INDEX = {"upright": 0, "italic": 1}


@dataclass(frozen=True)
class InkMetrics:
    baseline_area: float
    candidate_area: float
    lost_area: float
    residual_lost_area: float
    added_area: float
    baseline_counters: int
    candidate_counters: int
    counter_area_ratios: tuple[float, ...]
    unmatched_candidate_counters: int
    area_conservation_error: float
    area_conservation_tolerance: float
    geometry_backend: str = 'pathops'
    flattening_tolerance_font_units: float = 0.0
    baseline_flattening_area_bound: float = 0.0
    candidate_flattening_area_bound: float = 0.0
    maximum_flattened_curve_deviation: float = 0.0
    dilation_arc_maximum_deviation: float = 0.0


def _filled_path(glyph_set, name: str):
    """Return a simplified nonzero-filled union, decomposing components first."""
    import pathops

    recording = DecomposingRecordingPen(glyph_set)
    glyph_set[name].draw(recording)
    path = pathops.Path()
    recording.replay(path.getPen())
    return pathops.simplify(path, fix_winding=True, clockwise=False)


def _boolean_area(path) -> float:
    """Return filled area, subtracting clockwise hole contours explicitly."""
    simplified = _simplify(path)
    area = sum(
        -abs(float(contour.area)) if contour.clockwise else abs(float(contour.area))
        for contour in simplified.contours
    )
    # A canonical outline has counter-clockwise exteriors and clockwise holes.
    # The explicit signed-contour sum avoids turning holes into added ink.
    if area < -1e-6:
        raise ValueError(f"simplified filled path has negative net area: {area:g}")
    return max(area, 0.0)


def _control_scale(path) -> float:
    """Largest absolute control coordinate, used for PathOps float32 precision."""
    bounds = path.controlPointBounds
    return max((abs(float(value)) for value in bounds), default=0.0)


def _perimeter_upper_bound(path) -> float:
    """Control-polygon length upper-bounds a Bezier path's perimeter."""
    total = 0.0
    for contour in path.contours:
        current = start = None
        for command, points in contour.segments:
            if command == "moveTo":
                start = current = points[0]
            elif command in {"lineTo", "qCurveTo", "curveTo"}:
                if current is None:
                    continue
                for point in points:
                    total += math.dist(current, point)
                    current = point
            elif command == "closePath" and current is not None and start is not None:
                total += math.dist(current, start)
                current = start
    return total


def _float32_rounding_bound(paths, areas: Iterable[float]) -> float:
    """Conservative area bound from float32 coordinate rounding.

    A float32 control coordinate rounds by at most half an ULP. A Bezier curve
    stays in its controls' convex hull, so moving each control by delta moves its
    boundary by at most delta. The planar parallel-curve bound P*delta + pi*delta²
    bounds the area change of each outline. Sum it over the two source and two
    boolean-result outlines used by the conservation identity; add float64 area
    accumulation noise. This scales with actual coordinates and perimeter.
    """
    paths = tuple(paths)
    scale = max((_control_scale(path) for path in paths), default=0.0)
    if scale == 0:
        coordinate_delta = 2.0 ** -150
    else:
        _, exponent = math.frexp(scale)
        coordinate_delta = 2.0 ** (exponent - 24)  # half-ULP for binary32
    geometric_bound = sum(
        _perimeter_upper_bound(path) * coordinate_delta
        + math.pi * coordinate_delta * coordinate_delta
        for path in paths
    )
    accumulation_bound = max(1e-9, sum(abs(float(area)) for area in areas) * 1e-12)
    return geometric_bound + accumulation_bound


def _simplify(path):
    import pathops

    return pathops.simplify(path, fix_winding=True, clockwise=False)


def _boolean_difference(subject, clip):
    """Compute a canonical boolean difference through pathops.op."""
    import pathops

    subject = _simplify(subject)
    clip = _simplify(clip)
    result = pathops.op(subject, clip, pathops.PathOp.DIFFERENCE, fix_winding=True, clockwise=False)
    return _simplify(result)


def _dilate(path, radius: float):
    """Dilate a filled path by radius using a round-joined centered boundary stroke."""
    import pathops

    path = _simplify(path)
    if radius <= 0:
        return path
    stroke = pathops.Path()
    stroke.addPath(path)
    stroke.stroke(
        2 * radius, pathops.LineCap.ROUND_CAP, pathops.LineJoin.ROUND_JOIN, 4.0
    )
    # PathOps stroke emits conics for round joins/caps, while its boolean
    # operators accept quadratics/cubics. Convert with sub-unit error well below
    # any chosen radius, then canonicalize the union result.
    stroke.convertConicsToQuads(max(0.01, radius / 16))
    result = pathops.op(path, stroke, pathops.PathOp.UNION, fix_winding=True, clockwise=False)
    return _simplify(result)


def _counter_contours(path):
    """Return the actual hole polygons from a simplified, consistently wound outline."""
    return [contour for contour in path.contours if contour.clockwise]


def _match_counter_contours(baseline_holes, candidate_holes) -> tuple[tuple[float, ...], int]:
    """Match holes by shared polygon area, not their sorted areas or counts."""
    import pathops

    intersections = []
    for baseline_index, baseline_hole in enumerate(baseline_holes):
        for candidate_index, candidate_hole in enumerate(candidate_holes):
            overlap = pathops.op(
                baseline_hole, candidate_hole, pathops.PathOp.INTERSECTION,
                fix_winding=True, clockwise=False,
            )
            overlap_area = _boolean_area(overlap)
            if overlap_area > 0:
                intersections.append((overlap_area, baseline_index, candidate_index))

    # Counters are few per glyph; greedy maximum-overlap matching is stable and
    # ensures one candidate hole cannot stand in for multiple baseline holes.
    intersections.sort(reverse=True)
    matched_baseline: set[int] = set()
    matched_candidate: set[int] = set()
    overlap_for_baseline: dict[int, float] = {}
    for overlap_area, baseline_index, candidate_index in intersections:
        if baseline_index in matched_baseline or candidate_index in matched_candidate:
            continue
        matched_baseline.add(baseline_index)
        matched_candidate.add(candidate_index)
        overlap_for_baseline[baseline_index] = overlap_area

    ratios = tuple(
        overlap_for_baseline.get(index, 0.0) / abs(float(hole.area))
        if abs(float(hole.area)) else 0.0
        for index, hole in enumerate(baseline_holes)
    )
    return ratios, len(candidate_holes) - len(matched_candidate)


def _compare_pathops(
    baseline_glyph_set,
    candidate_glyph_set,
    baseline_name: str,
    candidate_name: str | None = None,
    max_outline_loss_distance: float = 0.0,
) -> tuple[InkMetrics, float, float]:
    """Compare one glyph; return geometry and the two effective advances."""
    import pathops

    candidate_name = candidate_name or baseline_name
    try:
        baseline = _filled_path(baseline_glyph_set, baseline_name)
        candidate = _filled_path(candidate_glyph_set, candidate_name)

        lost = _boolean_difference(baseline, candidate)
        added = _boolean_difference(candidate, baseline)
        dilated_candidate = _dilate(candidate, max_outline_loss_distance)
        residual_lost = _boolean_difference(baseline, dilated_candidate)

        baseline_area = _boolean_area(baseline)
        candidate_area = _boolean_area(candidate)
        lost_area = _boolean_area(lost)
        added_area = _boolean_area(added)
        residual_lost_area = _boolean_area(residual_lost)
        conservation_error = abs((baseline_area - candidate_area) - (lost_area - added_area))
        conservation_tolerance = _float32_rounding_bound(
            (baseline, candidate, lost, added),
            (baseline_area, candidate_area, lost_area, added_area),
        )

        baseline_counters = _counter_contours(baseline)
        candidate_counters = _counter_contours(candidate)
        ratios, unmatched_candidate_counters = _match_counter_contours(
            baseline_counters, candidate_counters
        )
    except Exception as error:
        raise ValueError(f"{baseline_name}->{candidate_name}: {error}") from error
    metrics = InkMetrics(
        baseline_area=baseline_area,
        candidate_area=candidate_area,
        lost_area=lost_area,
        residual_lost_area=residual_lost_area,
        added_area=added_area,
        baseline_counters=len(baseline_counters),
        candidate_counters=len(candidate_counters),
        counter_area_ratios=ratios,
        unmatched_candidate_counters=unmatched_candidate_counters,
        area_conservation_error=conservation_error,
        area_conservation_tolerance=conservation_tolerance,
    )
    return (
        metrics,
        float(baseline_glyph_set[baseline_name].width),
        float(candidate_glyph_set[candidate_name].width),
    )


class _FlattenPen(BasePen):
    """Flatten each Bezier into chords with a control-hull distance bound."""
    def __init__(self, tolerance):
        super().__init__(None)
        self.tolerance = tolerance
        self.contours = []
        self.points = []
        self.control_perimeter = 0.0
        self.maximum_deviation = 0.0
        self.segment_count = 0

    @staticmethod
    def _distance_to_segment(point, start, end):
        dx, dy = end[0]-start[0], end[1]-start[1]
        denominator = dx*dx+dy*dy
        if denominator == 0:
            return math.dist(point, start)
        t = max(0.0, min(1.0, ((point[0]-start[0])*dx+(point[1]-start[1])*dy)/denominator))
        return math.hypot(point[0]-start[0]-t*dx, point[1]-start[1]-t*dy)

    def _flatten(self, controls, depth=0):
        deviation = max(self._distance_to_segment(p, controls[0], controls[-1])
                        for p in controls[1:-1])
        if deviation <= self.tolerance:
            self.points.append(controls[-1])
            self.maximum_deviation = max(self.maximum_deviation, deviation)
            self.segment_count += 1
            return
        if depth >= 32:
            raise ValueError('Bezier flattening cannot meet the requested distance bound')
        levels = [list(controls)]
        while len(levels[-1]) > 1:
            row = levels[-1]
            levels.append([((a[0]+b[0])/2, (a[1]+b[1])/2) for a, b in zip(row, row[1:])])
        left = [row[0] for row in levels]
        right = [row[-1] for row in reversed(levels)]
        self._flatten(left, depth+1)
        self._flatten(right, depth+1)

    def _moveTo(self, point):
        self.points = [tuple(point)]

    def _lineTo(self, point):
        self.control_perimeter += math.dist(self.points[-1], point)
        self.points.append(tuple(point))
        self.segment_count += 1

    def _curve(self, controls):
        if not all(math.isfinite(value) for p in controls for value in p):
            raise ValueError('non-finite outline coordinate')
        self.control_perimeter += sum(math.dist(a, b) for a, b in zip(controls, controls[1:]))
        self._flatten(controls)

    def _curveToOne(self, a, b, end):
        self._curve([self.points[-1], tuple(a), tuple(b), tuple(end)])

    def _qCurveToOne(self, control, end):
        self._curve([self.points[-1], tuple(control), tuple(end)])

    def _closePath(self):
        if self.points:
            if self.points[0] != self.points[-1]:
                self.control_perimeter += math.dist(self.points[-1], self.points[0])
                self.points.append(self.points[0])
            if len(self.points) >= 4:
                self.contours.append(self.points)
        self.points = []

    def _endPath(self):
        self._closePath()


def _winding_number(point, contours):
    """Signed nonzero winding of the original flattened contour collection."""
    x, y = point.x, point.y
    winding = 0
    for contour in contours:
        for a, b in zip(contour, contour[1:]):
            side = (b[0]-a[0])*(y-a[1])-(x-a[0])*(b[1]-a[1])
            if a[1] <= y < b[1] and side > 0:
                winding += 1
            elif b[1] <= y < a[1] and side < 0:
                winding -= 1
    return winding


def _polygon_parts(geometry):
    if geometry.geom_type == 'Polygon':
        return [geometry]
    if hasattr(geometry, 'geoms'):
        return [polygon for part in geometry.geoms for polygon in _polygon_parts(part)]
    return []


def _filled_geos(glyph_set, name, tolerance):
    from shapely.geometry import GeometryCollection, LineString
    from shapely.ops import polygonize, unary_union
    pen = _FlattenPen(tolerance)
    recording = DecomposingRecordingPen(glyph_set)
    glyph_set[name].draw(recording)
    recording.replay(pen)
    if not pen.contours:
        return GeometryCollection(), pen
    # Node every crossing before polygonization. Contour nesting parity alone
    # loses overlapping black slashes and letters inside copyright rings.
    network = unary_union([LineString(c) for c in pen.contours])
    selected = [face for face in polygonize(network)
                if _winding_number(face.representative_point(), pen.contours) != 0]
    return unary_union(selected) if selected else GeometryCollection(), pen


def _geos_counters(ink):
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    rings = [Polygon(ring) for polygon in _polygon_parts(ink) for ring in polygon.interiors]
    if not rings:
        return []
    # Subtract embedded black islands before extracting connected white
    # components. Union first avoids counting a depth-three hole twice.
    white = unary_union(rings).difference(ink)
    return [p for p in _polygon_parts(white) if p.area >= COUNTER_NOISE_AREA]


def _match_geos_counters(baseline, candidate):
    overlaps = sorted(((a.intersection(b).area, i, j)
                       for i, a in enumerate(baseline) for j, b in enumerate(candidate)), reverse=True)
    seen_a, seen_b, matched = set(), set(), {}
    for area, i, j in overlaps:
        if area <= 0 or i in seen_a or j in seen_b:
            continue
        seen_a.add(i)
        seen_b.add(j)
        matched[i] = area
    return tuple(matched.get(i, 0)/p.area for i, p in enumerate(baseline)), len(candidate)-len(seen_b)


def _geos_roundoff_bound(geometries, areas):
    """Float64 coordinate/area accumulation bound, independent of ink limits."""
    scale = max((abs(v) for g in geometries if not g.is_empty for v in g.bounds), default=1.0)
    perimeter = sum(g.length for g in geometries)
    return 64*math.ulp(max(1.0, scale))*perimeter + 64*math.ulp(max(1.0, sum(abs(a) for a in areas)))


def _compare_geos(baseline_glyph_set, candidate_glyph_set, baseline_name,
                  candidate_name, max_outline_loss_distance, flatten_tolerance):
    if not math.isfinite(flatten_tolerance) or flatten_tolerance <= 0:
        raise ValueError('flatten_tolerance must be finite and positive')
    baseline, bp = _filled_geos(baseline_glyph_set, baseline_name, flatten_tolerance)
    candidate, cp = _filled_geos(candidate_glyph_set, candidate_name, flatten_tolerance)
    lost, added = baseline.difference(candidate), candidate.difference(baseline)
    buffer_error = 0.0
    if max_outline_loss_distance > 0:
        ratio = min(1.0, flatten_tolerance/max_outline_loss_distance)
        quad_segs = max(16, math.ceil(math.pi/(4*math.acos(1-ratio))))
        buffer_error = max_outline_loss_distance*(1-math.cos(math.pi/(4*quad_segs)))
        dilated = candidate.buffer(max_outline_loss_distance, quad_segs=quad_segs)
        residual = baseline.difference(dilated)
    else:
        residual = lost
    baseline_holes, candidate_holes = _geos_counters(baseline), _geos_counters(candidate)
    ratios, unmatched = _match_geos_counters(baseline_holes, candidate_holes)
    areas = baseline.area, candidate.area, lost.area, added.area
    conservation_error = abs((areas[0]-areas[1])-(areas[2]-areas[3]))
    metrics = InkMetrics(
        baseline_area=baseline.area, candidate_area=candidate.area,
        lost_area=lost.area, residual_lost_area=residual.area, added_area=added.area,
        baseline_counters=len(baseline_holes), candidate_counters=len(candidate_holes),
        counter_area_ratios=ratios, unmatched_candidate_counters=unmatched,
        area_conservation_error=conservation_error,
        area_conservation_tolerance=_geos_roundoff_bound((baseline, candidate, lost, added), areas),
        geometry_backend='geos', flattening_tolerance_font_units=flatten_tolerance,
        baseline_flattening_area_bound=2*bp.control_perimeter*flatten_tolerance+len(bp.contours)*math.pi*flatten_tolerance**2,
        candidate_flattening_area_bound=2*cp.control_perimeter*flatten_tolerance+len(cp.contours)*math.pi*flatten_tolerance**2,
        maximum_flattened_curve_deviation=max(bp.maximum_deviation, cp.maximum_deviation),
        dilation_arc_maximum_deviation=buffer_error,
    )
    return metrics, float(baseline_glyph_set[baseline_name].width), float(candidate_glyph_set[candidate_name].width)


def compare_glyphs(baseline_glyph_set, candidate_glyph_set, baseline_name,
                   candidate_name=None, max_outline_loss_distance=0.0,
                   geometry_backend='geos', flatten_tolerance=DEFAULT_FLATTEN_TOLERANCE):
    """Measure directional filled-area loss using independent float64 GEOS."""
    candidate_name = candidate_name or baseline_name
    if not math.isfinite(max_outline_loss_distance) or max_outline_loss_distance < 0:
        raise ValueError('outline loss distance must be finite and nonnegative')
    if geometry_backend == 'pathops':
        return _compare_pathops(baseline_glyph_set, candidate_glyph_set, baseline_name,
                                candidate_name, max_outline_loss_distance)
    if geometry_backend != 'geos':
        raise ValueError(f'unknown geometry backend: {geometry_backend}')
    try:
        return _compare_geos(baseline_glyph_set, candidate_glyph_set, baseline_name,
                             candidate_name, max_outline_loss_distance, flatten_tolerance)
    except Exception as error:
        raise ValueError(f'{baseline_name}->{candidate_name}: {error}') from error


def _names_by_codepoint(font: TTFont, path: Path) -> dict[str, list[int]]:
    cmap = font.getBestCmap()
    actual = set(cmap)
    if actual != CODEPOINTS:
        missing = sorted(CODEPOINTS - actual)
        extra = sorted(actual - CODEPOINTS)
        raise ValueError(
            f"{path}: cmap must equal GF Latin Core ({len(CODEPOINTS)} codepoints); "
            f"missing={[f'U+{cp:04X}' for cp in missing]}, "
            f"extra={[f'U+{cp:04X}' for cp in extra]}"
        )
    names: dict[str, list[int]] = defaultdict(list)
    for codepoint in sorted(CODEPOINTS):
        names[cmap[codepoint]].append(codepoint)
    return dict(names)


def _open_font(path: Path, location: dict[str, int] | None = None):
    font = TTFont(path, lazy=False, recalcTimestamp=False)
    if location is not None and "fvar" not in font:
        font.close()
        raise ValueError(f"{path}: expected a variable font for weight {location['wght']}")
    glyph_set = font.getGlyphSet(location=location) if location is not None else font.getGlyphSet()
    return font, glyph_set


def _compare_pair(
    baseline_path: Path,
    candidate_path: Path,
    style: str,
    weight: int,
    source: str,
    max_ink_loss: float,
    minimum_counter_area_ratio: float,
    max_outline_loss_distance: float,
    baseline_variable: bool | None = None,
    candidate_variable: bool | None = None,
    geometry_backend: str = 'geos',
    flatten_tolerance: float = DEFAULT_FLATTEN_TOLERANCE,
    include_unencoded: bool = False,
) -> tuple[list[dict], list[str]]:
    if baseline_variable is None:
        baseline_variable = source == "variable"
    if candidate_variable is None:
        candidate_variable = source == "variable"
    baseline_font, baseline_glyphs = _open_font(
        baseline_path, {"wght": weight} if baseline_variable else None
    )
    candidate_font, candidate_glyphs = _open_font(
        candidate_path, {"wght": weight} if candidate_variable else None
    )
    rows: list[dict] = []
    failures: list[str] = []
    try:
        baseline_names = _names_by_codepoint(baseline_font, baseline_path)
        candidate_names = _names_by_codepoint(candidate_font, candidate_path)
        baseline_mapping = {cp: name for name, cps in baseline_names.items() for cp in cps}
        candidate_mapping = {cp: name for name, cps in candidate_names.items() for cp in cps}

        # The cmap contract is codepoint coverage. Production pipelines can
        # legitimately assign different internal names or glyph order, so pair
        # outlines through each cmap rather than requiring equal glyph names.
        # Group aliases to avoid repeating expensive booleans for one outline.
        pairs: dict[tuple[str, str], list[int]] = defaultdict(list)
        for codepoint in sorted(CODEPOINTS):
            pairs[(baseline_mapping[codepoint], candidate_mapping[codepoint])].append(codepoint)
        if include_unencoded:
            # Retained components, alternates and ligatures have no cmap entry.
            # Their production names are part of this source-build contract.
            for name in candidate_font.getGlyphOrder():
                if name not in candidate_names:
                    pairs.setdefault((name, name), [])
        for (baseline_name, candidate_name), codepoints in sorted(pairs.items()):
            try:
                metrics, baseline_width, candidate_width = compare_glyphs(
                    baseline_glyphs, candidate_glyphs, baseline_name, candidate_name,
                    max_outline_loss_distance, geometry_backend, flatten_tolerance,
                )
            except Exception as error:
                prefix = f"{style} wght={weight} {source} {codepoints!r}"
                failures.append(f"{prefix}: geometry comparison failed: {error}")
                rows.append({
                    "style": style,
                    "weight": weight,
                    "source": source,
                    "baseline_glyph": baseline_name,
                    "candidate_glyph": candidate_name,
                    "codepoints": [f"U+{codepoint:04X}" for codepoint in codepoints],
                    "geometry_error": str(error),
                })
                continue
            entry = {
                "style": style,
                "weight": weight,
                "source": source,
                "baseline_glyph": baseline_name,
                "candidate_glyph": candidate_name,
                "codepoints": [f"U+{codepoint:04X}" for codepoint in codepoints],
                **asdict(metrics),
                "baseline_advance": baseline_width,
                "candidate_advance": candidate_width,
            }
            rows.append(entry)
            prefix = f"{style} wght={weight} {source} {codepoints!r} ({baseline_name}->{candidate_name})"
            if baseline_width != candidate_width:
                failures.append(
                    f"{prefix}: advance changed {baseline_width:g} -> {candidate_width:g}"
                )
            if metrics.area_conservation_error > metrics.area_conservation_tolerance:
                failures.append(
                    f"{prefix}: boolean area conservation error "
                    f"{metrics.area_conservation_error:.8f} exceeds {geometry_backend} precision bound "
                    f"{metrics.area_conservation_tolerance:.8f}"
                )
            if metrics.residual_lost_area > max_ink_loss:
                failures.append(
                    f"{prefix}: residual loss after {max_outline_loss_distance:g}-unit "
                    f"outline tolerance is {metrics.residual_lost_area:.4f} square units "
                    f"(limit {max_ink_loss:g}; raw loss {metrics.lost_area:.4f})"
                )
            if metrics.baseline_counters != metrics.candidate_counters:
                failures.append(
                    f"{prefix}: counter count changed "
                    f"{metrics.baseline_counters} -> {metrics.candidate_counters}"
                )
            if metrics.unmatched_candidate_counters:
                failures.append(
                    f"{prefix}: {metrics.unmatched_candidate_counters} candidate counter(s) "
                    "do not overlap any baseline counter"
                )
            if metrics.counter_area_ratios and min(metrics.counter_area_ratios) < minimum_counter_area_ratio:
                failures.append(
                    f"{prefix}: smallest matched counter overlap is "
                    f"{min(metrics.counter_area_ratios):.4%} of baseline "
                    f"(minimum {minimum_counter_area_ratio:.4%})"
                )
    finally:
        baseline_font.close()
        candidate_font.close()
    return rows, failures


def _static_path(root: Path, style: str, weight: int, extension: str = "ttf") -> Path:
    return root / extension / f"NamcheShadowSans-{WEIGHT_STYLES[weight][STYLE_INDEX[style]]}.{extension}"


def validate(
    baseline_dir: Path,
    candidate_dir: Path,
    weights: Iterable[int] = DEFAULT_WEIGHTS,
    max_ink_loss: float = 2.0,
    minimum_counter_area_ratio: float = 0.05,
    max_outline_loss_distance: float = 0.0,
    geometry_backend: str = 'geos',
    flatten_tolerance: float = DEFAULT_FLATTEN_TOLERANCE,
    include_unencoded_variable: bool = False,
    include_otf_statics: bool = False,
) -> dict:
    """Compare VFs and named TTF statics, plus OTF statics when requested."""
    rows: list[dict] = []
    failures: list[str] = []
    weights = tuple(weights)
    if not math.isfinite(max_outline_loss_distance) or max_outline_loss_distance < 0:
        raise ValueError("max_outline_loss_distance must be finite and nonnegative")
    if geometry_backend not in ('geos', 'pathops'):
        raise ValueError(f'unknown geometry backend: {geometry_backend}')
    if not math.isfinite(flatten_tolerance) or flatten_tolerance <= 0:
        raise ValueError('flatten_tolerance must be finite and positive')
    invalid = [weight for weight in weights if not 100 <= weight <= 900]
    if invalid:
        raise ValueError(f"weights must be within 100..900: {invalid}")

    for style, vf_filename in VF_FILENAMES.items():
        baseline_vf = baseline_dir / "variable" / vf_filename
        candidate_vf = candidate_dir / "variable" / vf_filename
        if not baseline_vf.is_file() or not candidate_vf.is_file():
            raise FileNotFoundError(f"missing matching variable font: {baseline_vf} or {candidate_vf}")
        for weight in weights:
            found, errors = _compare_pair(
                baseline_vf, candidate_vf, style, weight, "variable",
                max_ink_loss, minimum_counter_area_ratio,
                max_outline_loss_distance,
                geometry_backend=geometry_backend, flatten_tolerance=flatten_tolerance,
                include_unencoded=include_unencoded_variable,
            )
            print(f'Checked {style} variable wght={weight}: {len(found)} glyphs, {len(errors)} findings', flush=True)
            rows.extend(found)
            failures.extend(errors)

            if weight in WEIGHT_STYLES:
                for extension in ('ttf', 'otf') if include_otf_statics else ('ttf',):
                    baseline_static = _static_path(baseline_dir, style, weight, extension)
                    candidate_static = _static_path(candidate_dir, style, weight, extension)
                    if not candidate_static.is_file():
                        raise FileNotFoundError(f"missing candidate static {extension.upper()}: {candidate_static}")
                    if not baseline_static.is_file():
                        raise FileNotFoundError(f'missing clean static {extension.upper()} baseline: {baseline_static}')
                    found, errors = _compare_pair(
                        baseline_static, candidate_static, style, weight,
                        'static' if extension == 'ttf' else 'static-otf',
                        max_ink_loss, minimum_counter_area_ratio,
                        max_outline_loss_distance,
                        baseline_variable=False,
                        candidate_variable=False,
                        geometry_backend=geometry_backend, flatten_tolerance=flatten_tolerance,
                    )
                    print(f'Checked {style} static {extension.upper()} wght={weight}: '
                          f'{len(found)} glyphs, {len(errors)} findings', flush=True)
                    rows.extend(found)
                    failures.extend(errors)

    if geometry_backend == 'geos':
        import shapely
        backend_version = f'Shapely {shapely.__version__}; GEOS {shapely.geos_version_string}'
    else:
        backend_version = 'skia-pathops'
    return {
        "geometry_backend_version": backend_version,
        "includes_unencoded_variable_glyphs": include_unencoded_variable,
        "includes_otf_static_fonts": include_otf_statics,
        "baseline_dir": str(baseline_dir),
        "candidate_dir": str(candidate_dir),
        "weights": list(weights),
        "geometry_backend": geometry_backend,
        "flattening_tolerance_font_units": flatten_tolerance if geometry_backend == 'geos' else 0.0,
        "counter_noise_area_square_units": COUNTER_NOISE_AREA if geometry_backend == 'geos' else 0.0,
        "max_ink_loss_square_units": max_ink_loss,
        "minimum_counter_area_ratio": minimum_counter_area_ratio,
        "max_outline_loss_distance_font_units": max_outline_loss_distance,
        "glyph_measurements": rows,
        "measurement_count": len(rows),
        "failure_count": len(failures),
        "failures": failures,
        "passed": not failures,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-dir", type=Path, required=True)
    parser.add_argument("--candidate-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True, help="write the full JSON report here")
    parser.add_argument(
        "--weights", type=int, nargs="+", default=list(DEFAULT_WEIGHTS),
        help="wght coordinates to inspect (default: 100 150 ... 900)",
    )
    parser.add_argument(
        "--max-ink-loss", type=float, default=2.0,
        help="maximum baseline-minus-candidate ink area per glyph, in square font units",
    )
    parser.add_argument(
        "--minimum-counter-area-ratio", type=float, default=0.05,
        help="minimum surviving counter area as a fraction of its baseline area",
    )
    parser.add_argument(
        "--max-outline-loss-distance", type=float, default=0.0,
        help=("dilate candidate outlines by this radius before applying the ink-loss "
              "gate; raw loss remains in the report (default: 0 font units)"),
    )
    parser.add_argument('--geometry-backend', choices=('geos', 'pathops'), default='geos',
                        help='independent float64 GEOS (default), or legacy PathOps cross-check')
    parser.add_argument('--flatten-tolerance', type=float, default=DEFAULT_FLATTEN_TOLERANCE,
                        help='maximum Bezier-to-chord distance for GEOS (default: 0.01 font units)')
    parser.add_argument('--include-unencoded-variable', action='store_true',
                        help='also check every retained VF component, alternate and ligature by glyph name')
    parser.add_argument('--include-otf-statics', action='store_true',
                        help='also compare named static OTFs against matching clean OTF baselines')
    args = parser.parse_args(argv)
    if args.max_ink_loss < 0:
        parser.error("--max-ink-loss must be nonnegative")
    if not 0 <= args.minimum_counter_area_ratio <= 1:
        parser.error("--minimum-counter-area-ratio must be between 0 and 1")
    if args.max_outline_loss_distance < 0:
        parser.error("--max-outline-loss-distance must be nonnegative")

    try:
        report = validate(
            args.baseline_dir.resolve(), args.candidate_dir.resolve(),
            args.weights, args.max_ink_loss, args.minimum_counter_area_ratio,
            args.max_outline_loss_distance, args.geometry_backend, args.flatten_tolerance,
            args.include_unencoded_variable, args.include_otf_statics,
        )
    except Exception as error:
        report = {
            "baseline_dir": str(args.baseline_dir),
            "candidate_dir": str(args.candidate_dir),
            "weights": args.weights,
            "includes_otf_static_fonts": args.include_otf_statics,
            "passed": False,
            "failures": [str(error)],
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n")
        print(f"FAIL: {error}", file=sys.stderr)
        return 1

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    if report["passed"]:
        print(f"PASS: {report['measurement_count']} glyph/style/weight measurements; report: {args.output}")
        return 0
    print(f"FAIL: {report['failure_count']} failures; report: {args.output}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
