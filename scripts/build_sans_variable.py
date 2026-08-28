#!/usr/bin/env python3
"""Build the rounded Namche Shadow Sans variable fonts (upright and italic).

The input is a native Glyphs 4 OTF export whose seven RoundCorner filters use
the ``compatible`` option.  The committed release OTF statics preserve those
export outlines, so they are an equivalent input; ``--italic`` selects the
italic masters and produces ``NamcheShadowSans-Italic[wght]``.  The OTF outlines are the visual source of truth.
Where the filter still emits different cubic segmentation at named weights,
this script splits the existing Bezier curves at common arc-length positions.
Splitting a Bezier does not change its shape.  All masters are then converted
to compatible TrueType curves together and assembled into a wght variable font.

The five glyphs whose rounded masters are not ready for interpolation are
deliberately excluded from the variable font; they remain in every static.
"""

from __future__ import annotations

import argparse
import itertools
import math
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

import numpy as np
from fontTools.designspaceLib import AxisDescriptor, DesignSpaceDocument, InstanceDescriptor, SourceDescriptor
from fontTools.misc.bezierTools import calcCubicArcLength, splitCubicAtT
from fontTools.otlLib.builder import buildStatTable
from fontTools.pens.cu2quPen import Cu2QuMultiPen
from fontTools.pens.recordingPen import RecordingPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.subset import Options, Subsetter
from fontTools.ttLib import TTFont
from fontTools.varLib import build as build_variable
from fontTools.varLib.instancer import instantiateVariableFont


WEIGHTS = (
    ("Thin", 100),
    ("ExtraLight", 200),
    ("Light", 300),
    ("Regular", 400),
    ("Medium", 500),
    ("SemiBold", 600),
    ("Bold", 700),
    ("ExtraBold", 800),
    ("Black", 900),
)
PARKED_GLYPHS = frozenset({"uni046A", "uni046B", "uni03BC", "uni0E3F", "uni20B1"})
CANONICAL_START_GLYPHS = frozenset({"Scedilla", "Uogonek", "uni0163", "uni01E4"})
FAMILY = "Namche Shadow Sans"
FAMILY_PS = "NamcheShadowSans"


def display_style(base: str, italic: bool) -> str:
    """Public style name for a weight ("Regular", "Thin Italic", "Italic")."""
    if not italic:
        return base
    return "Italic" if base == "Regular" else f"{base} Italic"


def file_style(base: str, italic: bool) -> str:
    """Style component of static filenames and PostScript names."""
    if not italic:
        return base
    return "Italic" if base == "Regular" else f"{base}Italic"


Point = tuple[float, float]


@dataclass(frozen=True)
class Segment:
    kind: str
    points: tuple[Point, ...]

    @property
    def start(self) -> Point:
        return self.points[0]

    @property
    def end(self) -> Point:
        return self.points[-1]

    def length(self) -> float:
        if self.kind == "line":
            return math.dist(self.start, self.end)
        return calcCubicArcLength(*self.points)

    def piece(self, start: float, end: float) -> tuple[Point, Point, Point, Point]:
        """Return an exact cubic representation of the [start, end] subsegment."""
        if not (0 <= start < end <= 1):
            raise ValueError((start, end))
        if self.kind == "line":
            p0 = _lerp(self.start, self.end, start)
            p3 = _lerp(self.start, self.end, end)
            return p0, _lerp(p0, p3, 1 / 3), _lerp(p0, p3, 2 / 3), p3
        piece = tuple(self.points)
        if end < 1:
            piece = tuple(splitCubicAtT(*piece, end)[0])
        if start > 0:
            piece = tuple(splitCubicAtT(*piece, start / end)[1])
        return piece  # type: ignore[return-value]


def _lerp(a: Point, b: Point, t: float) -> Point:
    return a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t


def _recording(font: TTFont, glyph_name: str) -> list[tuple[str, tuple]]:
    pen = RecordingPen()
    font.getGlyphSet()[glyph_name].draw(pen)
    return pen.value


def _contours(recording: Sequence[tuple[str, tuple]]) -> list[list[Segment]]:
    contours: list[list[Segment]] = []
    current: list[Segment] | None = None
    start: Point | None = None
    point: Point | None = None
    for operation, args in recording:
        if operation == "moveTo":
            if current is not None:
                raise ValueError("moveTo before closePath")
            start = point = args[0]
            current = []
        elif operation == "lineTo":
            if current is None or point is None:
                raise ValueError("lineTo outside contour")
            end = args[0]
            if end != point:
                current.append(Segment("line", (point, end)))
            point = end
        elif operation == "curveTo":
            if current is None or point is None or len(args) != 3:
                raise ValueError(f"unsupported curveTo: {args!r}")
            current.append(Segment("curve", (point, args[0], args[1], args[2])))
            point = args[2]
        elif operation == "closePath":
            if current is None or point is None or start is None:
                raise ValueError("closePath outside contour")
            if point != start:
                current.append(Segment("line", (point, start)))
            contours.append(current)
            current = None
            start = point = None
        else:
            raise ValueError(f"unsupported outline operation: {operation}")
    if current is not None:
        raise ValueError("open contour")
    return contours


def _signature(recording: Sequence[tuple[str, tuple]]) -> tuple[tuple[str, int], ...]:
    return tuple((operation, len(args)) for operation, args in recording)


def _dedupe(values: Iterable[float], tolerance: float = 1e-9) -> list[float]:
    result: list[float] = []
    for value in sorted(values):
        if not result or abs(value - result[-1]) > tolerance:
            result.append(value)
    result[0] = 0.0
    result[-1] = 1.0
    return result


def _segment_boundaries(contour: Sequence[Segment]) -> list[float]:
    lengths = [segment.length() for segment in contour]
    total = sum(lengths)
    if total <= 0:
        raise ValueError("zero-length contour")
    boundaries = [0.0]
    position = 0.0
    for length in lengths:
        position += length
        boundaries.append(position / total)
    boundaries[-1] = 1.0
    return boundaries


def _canonicalize_start(contour: Sequence[Segment]) -> list[Segment]:
    """Rotate a closed contour to a stable top-left on-curve point."""
    if not contour:
        return []
    highest = max(segment.start[1] for segment in contour)
    candidates = [
        index
        for index, segment in enumerate(contour)
        if abs(segment.start[1] - highest) <= 1e-6
    ]
    start = min(candidates, key=lambda index: contour[index].start[0])
    return list(contour[start:]) + list(contour[:start])


def _t_for_arc_fraction(segment: Segment, fraction: float) -> float:
    if fraction <= 0:
        return 0.0
    if fraction >= 1:
        return 1.0
    if segment.kind == "line":
        return fraction
    target = segment.length() * fraction
    low, high = 0.0, 1.0
    for _ in range(36):
        middle = (low + high) / 2
        left = splitCubicAtT(*segment.points, middle)[0]
        if calcCubicArcLength(*left) < target:
            low = middle
        else:
            high = middle
    return (low + high) / 2


def _normalized_contour(contour: Sequence[Segment], boundaries: Sequence[float]) -> list[tuple[Point, Point, Point]]:
    source_boundaries = _segment_boundaries(contour)
    result: list[tuple[Point, Point, Point]] = []
    segment_index = 0
    for start, end in zip(boundaries, boundaries[1:]):
        while start >= source_boundaries[segment_index + 1] - 1e-10 and segment_index < len(contour) - 1:
            segment_index += 1
        segment_start = source_boundaries[segment_index]
        segment_end = source_boundaries[segment_index + 1]
        if end > segment_end + 1e-8:
            raise ValueError("common boundary interval crossed a source segment")
        local_start = (start - segment_start) / (segment_end - segment_start)
        local_end = (end - segment_start) / (segment_end - segment_start)
        t0 = _t_for_arc_fraction(contour[segment_index], local_start)
        t1 = _t_for_arc_fraction(contour[segment_index], local_end)
        _, c1, c2, p3 = contour[segment_index].piece(t0, t1)
        result.append((c1, c2, p3))
    # Arc-length bisection can leave the closing point a few trillionths of a
    # unit away from the move point. ReverseContourPen then interprets that as
    # an explicit closing line in only those masters, breaking compatibility.
    # Snap the mathematically identical endpoint back to the exact start.
    if result:
        c1, c2, _ = result[-1]
        result[-1] = c1, c2, contour[0].start
    return result


def _align_piece_starts(
    pieces_by_master: Sequence[list[tuple[Point, Point, Point]]],
) -> tuple[list[Point], list[list[tuple[Point, Point, Point]]]]:
    """Align cyclic contour starts to the Regular master's geometry."""
    reference_index = next(index for index, (_, weight) in enumerate(WEIGHTS) if weight == 400)

    def normalized_endpoints(pieces: Sequence[tuple[Point, Point, Point]]) -> np.ndarray:
        points = np.asarray([piece[-1] for piece in pieces], dtype=float)
        points -= points.mean(axis=0)
        scale = np.linalg.norm(points)
        return points / scale if scale else points

    reference = normalized_endpoints(pieces_by_master[reference_index])
    starts: list[Point] = []
    aligned: list[list[tuple[Point, Point, Point]]] = []
    for pieces in pieces_by_master:
        points = normalized_endpoints(pieces)
        shift = min(
            range(len(pieces)),
            key=lambda value: float(np.square(reference - np.roll(points, -value, axis=0)).sum()),
        )
        rotated = pieces[shift:] + pieces[:shift]
        starts.append(rotated[-1][-1])
        aligned.append(rotated)
    return starts, aligned


def _normalize_recordings(recordings: Sequence[Sequence[tuple[str, tuple]]], glyph_name: str) -> list[list[tuple[str, tuple]]]:
    masters = [_contours(recording) for recording in recordings]
    contour_count = len(masters[0])
    if any(len(contours) != contour_count for contours in masters):
        raise ValueError("contour-count mismatch")
    normalized: list[list[tuple[str, tuple]]] = [[] for _ in masters]
    for contour_index in range(contour_count):
        contours = [master[contour_index] for master in masters]
        if glyph_name in CANONICAL_START_GLYPHS:
            contours = [_canonicalize_start(contour) for contour in contours]
        boundaries = _dedupe(
            boundary
            for contour in contours
            for boundary in _segment_boundaries(contour)
        )
        pieces_by_master = [_normalized_contour(contour, boundaries) for contour in contours]
        starts = [contour[0].start for contour in contours]
        if glyph_name in CANONICAL_START_GLYPHS:
            starts, pieces_by_master = _align_piece_starts(pieces_by_master)
        for master_index, (start, pieces) in enumerate(zip(starts, pieces_by_master)):
            normalized[master_index].append(("moveTo", (start,)))
            normalized[master_index].extend(("curveTo", piece) for piece in pieces)
            normalized[master_index].append(("closePath", ()))
    return normalized


def _op_contours(recording: Sequence[tuple[str, tuple]]) -> list[list[tuple[str, tuple]]]:
    chunks: list[list[tuple[str, tuple]]] = []
    current: list[tuple[str, tuple]] = []
    for operation in recording:
        current.append(operation)
        if operation[0] == "closePath":
            chunks.append(current)
            current = []
    if current:
        chunks.append(current)
    return chunks


ContourKey = tuple[float, Point]


def _points_key(points: Sequence[Point]) -> ContourKey:
    """Signed shoelace area plus centroid; area separates outers from counters."""
    area = 0.5 * sum(
        x1 * y2 - x2 * y1
        for (x1, y1), (x2, y2) in zip(points, [*points[1:], points[0]])
    )
    centroid = (
        sum(x for x, _ in points) / len(points),
        sum(y for _, y in points) / len(points),
    )
    return area, centroid


def _chunk_key(chunk: Sequence[tuple[str, tuple]]) -> ContourKey:
    return _points_key([point for _, arguments in chunk for point in arguments])


def _assignment_cost(first: ContourKey, second: ContourKey) -> float:
    (area_a, centroid_a), (area_b, centroid_b) = first, second
    if (area_a >= 0) != (area_b >= 0):
        return math.inf
    return math.dist(centroid_a, centroid_b) + abs(
        abs(area_a) ** 0.5 - abs(area_b) ** 0.5
    )


def _best_permutation(
    reference: Sequence[ContourKey], candidates: Sequence[ContourKey]
) -> tuple[int, ...]:
    count = len(reference)
    if count <= 6:
        return min(
            itertools.permutations(range(count)),
            key=lambda perm: sum(
                _assignment_cost(reference[index], candidates[perm[index]])
                for index in range(count)
            ),
        )
    used: set[int] = set()
    order: list[int] = []
    for target in reference:
        best = min(
            (index for index in range(count) if index not in used),
            key=lambda index: _assignment_cost(target, candidates[index]),
        )
        used.add(best)
        order.append(best)
    return tuple(order)


def _match_contour_order(
    recordings: Sequence[Sequence[tuple[str, tuple]]],
) -> list[Sequence[tuple[str, tuple]]]:
    """Reorder every master's contours to correspond with the first master's.

    Glyphs exports can list a glyph's contours in a different order per weight
    (the italic ``fi``, ``oe``, ``infinity``, and ``uni0424`` did).  Pairing
    contours by list index then interpolates one contour into another, which
    destroys the glyph at every non-master weight while all masters render
    correctly.  Centroid matching restores the correspondence before any
    structural comparison happens.
    """
    base_chunks = _op_contours(recordings[0])
    count = len(base_chunks)
    if count < 2:
        return list(recordings)
    # Match each master against its reordered predecessor: adjacent weights
    # drift far less than Thin-to-Black, keeping the assignment unambiguous.
    reference = [_chunk_key(chunk) for chunk in base_chunks]
    matched: list[Sequence[tuple[str, tuple]]] = [recordings[0]]
    for recording in recordings[1:]:
        chunks = _op_contours(recording)
        if len(chunks) != count:
            # Let the structural checks report the mismatch.
            return list(recordings)
        keys = [_chunk_key(chunk) for chunk in chunks]
        order = _best_permutation(reference, keys)
        matched.append(
            [operation for index in order for operation in chunks[index]]
        )
        reference = [keys[index] for index in order]
    return matched


def _draw_compatible(recordings: Sequence[Sequence[tuple[str, tuple]]], glyph_name: str) -> list:
    recordings = _match_contour_order(recordings)
    def convert(compatible: Sequence[Sequence[tuple[str, tuple]]]) -> list:
        # Drop a closing point that coincides with the start. This also removes
        # the explicit closing line that ReverseContourPen emits when reversing
        # a CFF contour whose close was implicit, keeping all masters aligned.
        pens = [TTGlyphPen(None, outputImpliedClosingLine=False) for _ in compatible]
        # Glyphs' OTF export uses PostScript winding. Reverse every contour
        # while converting to glyf so the VF follows the TrueType convention
        # and matches the approved native-Glyphs static TTFs.
        pen = Cu2QuMultiPen(pens, max_err=1.0, reverse_direction=True)
        for operations in zip(*compatible):
            names = {operation for operation, _ in operations}
            if len(names) != 1:
                raise ValueError(f"operation mismatch after normalization: {names}")
            operation = operations[0][0]
            arguments = [args for _, args in operations]
            if operation == "moveTo":
                pen.moveTo(arguments)
            elif operation == "lineTo":
                pen.lineTo(arguments)
            elif operation == "curveTo":
                pen.curveTo(arguments)
            elif operation == "closePath":
                pen.closePath()
            else:
                raise ValueError(operation)
        return [output.glyph() for output in pens]

    def topology(glyph) -> tuple:
        return tuple(glyph.endPtsOfContours), tuple(flag & 1 for flag in glyph.flags)

    signatures = {_signature(recording) for recording in recordings}
    compatible = list(recordings) if len(signatures) == 1 else _normalize_recordings(recordings, glyph_name)
    glyphs = convert(compatible)
    if len({topology(glyph) for glyph in glyphs}) != 1:
        # Reversing exposes implicit closing lines that can differ between
        # otherwise signature-compatible CFF masters. Normalization makes the
        # exact closing segment explicit in every master before retrying.
        glyphs = convert(_normalize_recordings(recordings, glyph_name))
    if len({topology(glyph) for glyph in glyphs}) != 1:
        raise ValueError(f"incompatible TrueType topology for {glyph_name}")
    return glyphs


def _subset_parked(font: TTFont) -> None:
    meta = font["meta"] if "meta" in font else None
    if meta is not None:
        del font["meta"]
    keep = [name for name in font.getGlyphOrder() if name not in PARKED_GLYPHS]
    options = Options()
    options.layout_features = ["*"]
    options.name_IDs = ["*"]
    options.name_languages = ["*"]
    options.glyph_names = True
    options.notdef_glyph = True
    options.notdef_outline = True
    subsetter = Subsetter(options=options)
    subsetter.populate(glyphs=keep)
    subsetter.subset(font)
    if meta is not None:
        font["meta"] = meta


def _master_paths(export_dir: Path, static_dir: Path, italic: bool) -> tuple[list[Path], list[Path]]:
    otfs, ttfs = [], []
    for base, _ in WEIGHTS:
        style = file_style(base, italic)
        otf = export_dir / "otf" / f"{FAMILY_PS}-{style}.otf"
        ttf = static_dir / "ttf" / f"{FAMILY_PS}-{style}.ttf"
        if not otf.is_file():
            raise FileNotFoundError(f"missing compatible Glyphs export: {otf}")
        if not ttf.is_file():
            raise FileNotFoundError(f"missing release static: {ttf}")
        otfs.append(otf)
        ttfs.append(ttf)
    return otfs, ttfs


def _build_masters(export_dir: Path, static_dir: Path, work_dir: Path, italic: bool) -> list[Path]:
    otf_paths, template_paths = _master_paths(export_dir, static_dir, italic)
    outlines = [TTFont(path, recalcTimestamp=False) for path in otf_paths]
    templates = [TTFont(path, recalcTimestamp=False) for path in template_paths]
    orders = [font.getGlyphOrder() for font in outlines]
    if any(order != orders[0] for order in orders[1:]):
        raise ValueError("Glyphs exports do not share a glyph order")
    if any(template.getGlyphOrder() != orders[0] for template in templates):
        raise ValueError("compatible exports and release statics do not share a glyph order")

    retained = [name for name in orders[0] if name not in PARKED_GLYPHS]
    for glyph_name in retained:
        recordings = [_recording(font, glyph_name) for font in outlines]
        glyphs = _draw_compatible(recordings, glyph_name)
        for index, glyph in enumerate(glyphs):
            templates[index]["glyf"][glyph_name] = glyph
            templates[index]["hmtx"][glyph_name] = outlines[index]["hmtx"][glyph_name]

    output_paths = []
    for (base, _), font in zip(WEIGHTS, templates):
        for tag in ("fpgm", "prep", "cvt "):
            if tag in font:
                del font[tag]
        _subset_parked(font)
        path = work_dir / f"{FAMILY_PS}-{file_style(base, italic)}.ttf"
        font.save(path, reorderTables=False)
        output_paths.append(path)
    return output_paths


def _designspace(master_paths: Sequence[Path], italic: bool) -> DesignSpaceDocument:
    document = DesignSpaceDocument()
    axis = AxisDescriptor()
    axis.name = "Weight"
    axis.tag = "wght"
    axis.minimum = 100
    axis.default = 400
    axis.maximum = 900
    document.addAxis(axis)
    for (base, weight), path in zip(WEIGHTS, master_paths):
        style = display_style(base, italic)
        source = SourceDescriptor()
        source.name = style
        source.path = str(path.resolve())
        source.familyName = FAMILY
        source.styleName = style
        source.location = {"Weight": weight}
        if weight == 400:
            source.copyInfo = True
            source.copyLib = True
            source.copyFeatures = True
            source.copyGroups = True
        document.addSource(source)
        instance = InstanceDescriptor()
        instance.name = style
        instance.familyName = FAMILY
        instance.styleName = style
        instance.location = {"Weight": weight}
        document.addInstance(instance)
    return document


def _set_variable_metadata(font: TTFont, italic: bool) -> None:
    names = font["name"]
    subfamily = "Italic" if italic else "Regular"
    postscript = f"{FAMILY_PS}-{subfamily}"
    variations_prefix = f"{FAMILY_PS}Italic" if italic else FAMILY_PS
    for platform_id, encoding_id, language_id in ((3, 1, 0x409), (1, 0, 0)):
        names.setName(FAMILY, 1, platform_id, encoding_id, language_id)
        names.setName(subfamily, 2, platform_id, encoding_id, language_id)
        names.setName(f"{FAMILY} {subfamily}", 4, platform_id, encoding_id, language_id)
        names.setName(postscript, 6, platform_id, encoding_id, language_id)
        names.setName(variations_prefix, 25, platform_id, encoding_id, language_id)
    names.removeNames(nameID=16)
    names.removeNames(nameID=17)
    for instance, (base, _) in zip(font["fvar"].instances, WEIGHTS):
        instance.postscriptNameID = names.addMultilingualName(
            {"en": f"{FAMILY_PS}-{file_style(base, italic)}"},
            windows=True,
            mac=True,
            minNameID=256,
        )
    # The wght values carry the bare weight names and the ital axis carries the
    # Roman/Italic value, matching the Geist variable pair on Google Fonts.
    ital_values = (
        [{"name": "Italic", "value": 1}]
        if italic
        else [{"name": "Roman", "value": 0, "flags": 2, "linkedValue": 1}]
    )
    buildStatTable(
        font,
        [
            {
                "tag": "wght",
                "name": "Weight",
                "values": [
                    {
                        "name": style,
                        "value": weight,
                        **({"flags": 2, "linkedValue": 700} if weight == 400 else {}),
                    }
                    for style, weight in WEIGHTS
                ],
            },
            {"tag": "ital", "name": "Italic", "values": ital_values},
        ],
    )


def _glyf_contour_keys(font: TTFont, glyph_name: str) -> list[ContourKey]:
    glyph = font["glyf"][glyph_name]
    if glyph.numberOfContours <= 0:
        return []
    coordinates, ends, _ = glyph.getCoordinates(font["glyf"])
    keys: list[ContourKey] = []
    start = 0
    for end in ends:
        keys.append(_points_key(list(coordinates[start : end + 1])))
        start = end + 1
    return keys


def assert_contour_correspondence(first: TTFont, second: TTFont, context: str) -> None:
    """Reject master pairs whose same-index contours are not the same contour.

    Interpolating contour i of one master into contour j of the next renders
    correctly at every master and destroys the glyph in between, so this is
    checked geometrically: pairing by index must cost no more than the best
    area/centroid assignment.
    """
    for glyph_name in first.getGlyphOrder():
        a = _glyf_contour_keys(first, glyph_name)
        b = _glyf_contour_keys(second, glyph_name)
        if len(a) < 2 or len(a) != len(b):
            continue
        identity = sum(
            _assignment_cost(a[index], b[index]) for index in range(len(a))
        )
        order = _best_permutation(a, b)
        best = sum(
            _assignment_cost(a[index], b[order[index]]) for index in range(len(a))
        )
        if identity > best + 1.0:
            raise ValueError(
                f"{context}: contour order of {glyph_name} does not correspond "
                f"between adjacent masters (index pairing costs {identity:.1f}, "
                f"best assignment {best:.1f})"
            )


def _validate(font: TTFont, master_paths: Sequence[Path]) -> None:
    previous: TTFont | None = None
    for master_path in master_paths:
        master = TTFont(master_path, recalcTimestamp=False)
        if previous is not None:
            assert_contour_correspondence(previous, master, str(master_path))
        previous = master
    if set(font.getGlyphOrder()) & PARKED_GLYPHS:
        raise ValueError("parked glyphs leaked into the variable font")
    axes = {axis.axisTag: axis for axis in font["fvar"].axes}
    weight = axes.get("wght")
    if weight is None or (weight.minValue, weight.defaultValue, weight.maxValue) != (100, 400, 900):
        raise ValueError("unexpected wght axis")
    if len(font["fvar"].instances) != len(WEIGHTS):
        raise ValueError("expected nine named instances")
    for (_, value), master_path in zip(WEIGHTS, master_paths):
        instance = instantiateVariableFont(font, {"wght": value}, inplace=False, optimize=False)
        master = TTFont(master_path, recalcTimestamp=False)
        if instance.getGlyphOrder() != master.getGlyphOrder():
            raise ValueError(f"glyph order mismatch at wght={value}")
        for glyph_name in master.getGlyphOrder():
            instance_metrics = instance["hmtx"][glyph_name]
            master_metrics = master["hmtx"][glyph_name]
            if any(abs(a - b) > 1 for a, b in zip(instance_metrics, master_metrics)):
                raise ValueError(f"advance mismatch for {glyph_name} at wght={value}")
            instance_coordinates, instance_ends, instance_flags = instance["glyf"][glyph_name].getCoordinates(instance["glyf"])
            master_coordinates, master_ends, master_flags = master["glyf"][glyph_name].getCoordinates(master["glyf"])
            instance_on_curves = [flag & 1 for flag in instance_flags]
            master_on_curves = [flag & 1 for flag in master_flags]
            if instance_ends != master_ends or instance_on_curves != master_on_curves or len(instance_coordinates) != len(master_coordinates):
                raise ValueError(f"outline structure mismatch for {glyph_name} at wght={value}")
            # gvar stores integer deltas.  At intermediate supports this can
            # introduce the normal sub-two-unit quantization seen in TrueType
            # variable fonts; anything larger indicates a real shape mismatch.
            if any(abs(a - b) > 1.5 for point_a, point_b in zip(instance_coordinates, master_coordinates) for a, b in zip(point_a, point_b)):
                raise ValueError(f"outline mismatch for {glyph_name} at wght={value}")


def build(export_dir: Path, static_dir: Path, output_dir: Path, italic: bool = False) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="namche-shadow-vf-") as temporary:
        master_paths = _build_masters(export_dir, static_dir, Path(temporary), italic)
        variable, _, _ = build_variable(_designspace(master_paths, italic), optimize=True)
        _set_variable_metadata(variable, italic)
        _validate(variable, master_paths)
        # Preserve the default master's source timestamp so repeated builds are
        # byte-for-byte reproducible instead of recording the wall-clock time.
        variable.recalcTimestamp = False
        stem = f"{FAMILY_PS}-Italic[wght]" if italic else f"{FAMILY_PS}[wght]"
        ttf_path = output_dir / "variable" / f"{stem}.ttf"
        woff2_path = output_dir / "webfonts" / f"{stem}.woff2"
        ttf_path.parent.mkdir(parents=True, exist_ok=True)
        woff2_path.parent.mkdir(parents=True, exist_ok=True)
        variable.save(ttf_path, reorderTables=False)
        webfont = TTFont(ttf_path, recalcTimestamp=False)
        webfont.flavor = "woff2"
        webfont.save(woff2_path, reorderTables=False)
    return ttf_path, woff2_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--glyphs-export", type=Path, required=True, help="directory containing compatible otf/ exports")
    parser.add_argument("--statics", type=Path, default=Path("fonts/NamcheShadowSans"))
    parser.add_argument("--output", type=Path, default=Path("fonts/NamcheShadowSans"))
    parser.add_argument("--italic", action="store_true", help="build the italic variable font from the italic masters")
    args = parser.parse_args()
    ttf, woff2 = build(args.glyphs_export, args.statics, args.output, italic=args.italic)
    print(f"Built {ttf}")
    print(f"Built {woff2}")


if __name__ == "__main__":
    main()
