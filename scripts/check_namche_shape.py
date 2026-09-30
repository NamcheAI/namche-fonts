#!/usr/bin/env python3
"""Block Namche Shape release regressions.

Checks every committed release and npm binary against the grid source:

- all three styles ship as OTF, TTF, and WOFF2, plus the npm WOFF2 copies
- glyph set, Unicode map, and advance widths match the source
- U+2028/U+2029 stay inkless at 600 units; the zero-width soft hyphen stays
- source-defined ligature carets (including fi and fl) survive
- U+20B9 ₹ and U+25CC ◌ carry ink; every combining mark attaches to ◌ and
  į + a top mark shapes to dotless i + ogonek + mark
- every glyph but marks has seeded `.shapeN` alternates with the same width,
  and `calt` gives four repeated letters four different variants
- with --reproducible, every outline equals a fresh generator build, so the
  committed fonts cannot drift from scripts/namche_shape.py and its overrides
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from functools import lru_cache
from io import BytesIO
from pathlib import Path

import glyphsLib
import uharfbuzz as hb
from fontTools.pens.areaPen import AreaPen
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.recordingPen import DecomposingRecordingPen
from fontTools.ttLib import TTFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
import namche_shape as ns  # noqa: E402

STYLES = ns.STYLES
SEPARATORS = (0x2028, 0x2029)
SEPARATOR_WIDTH = 600
RUPEE = 0x20B9
DOTTED_CIRCLE = 0x25CC
REQUIRED_MARKS = (0x0301, 0x0302, 0x030C, 0x0304, 0x0303, 0x0300)
OPTIONAL_MARKS = (0x030B, 0x0307, 0x0306, 0x0308, 0x0312, 0x030A)
IOGONEK_RULE = "sub iogonek' @CombiningTopAccents by idotless ogonekcomb;"


def expected_fonts(root: Path) -> list[Path]:
    release = root / "fonts" / "NamcheShape"
    paths = [
        release / directory / f"NamcheShape-{style}.{suffix}"
        for directory, suffix in (("otf", "otf"), ("ttf", "ttf"), ("webfonts", "woff2"))
        for style in STYLES
    ]
    npm = root / "packages" / "next" / "dist" / "fonts" / "namche-shape"
    paths.extend(npm / f"NamcheShape-{style}.woff2" for style in STYLES)
    return paths


@lru_cache(maxsize=1)
def source_expectations():
    font = glyphsLib.GSFont(str(ns.SOURCE))
    master = font.masters[0].id
    widths, cmap, carets = {}, {}, {}
    for glyph in font.glyphs:
        if not glyph.export:
            continue
        layer = glyph.layers[master]
        widths[glyph.name] = round(layer.width)
        for value in glyph.unicodes or []:
            cmap[int(value, 16)] = glyph.name
        anchors = sorted(
            (int(a.name.removeprefix("caret_")), round(a.position.x))
            for a in layer.anchors
            if a.name.startswith("caret_")
        )
        if anchors:
            carets[glyph.name] = tuple(x for _, x in anchors)
    fontinfo = (ns.SOURCE / "fontinfo.plist").read_text()
    return widths, cmap, carets, fontinfo


def ligature_carets(font: TTFont, glyph_name: str) -> tuple[int, ...]:
    if "GDEF" not in font or font["GDEF"].table.LigCaretList is None:
        return ()
    caret_list = font["GDEF"].table.LigCaretList
    if glyph_name not in caret_list.Coverage.glyphs:
        return ()
    index = caret_list.Coverage.glyphs.index(glyph_name)
    return tuple(c.Coordinate for c in caret_list.LigGlyph[index].CaretValue)


def has_ink(font: TTFont, glyph_name: str) -> bool:
    pen = BoundsPen(font.getGlyphSet())
    font.getGlyphSet()[glyph_name].draw(pen)
    return pen.bounds is not None


@lru_cache(maxsize=None)
def sfnt_bytes(path: Path) -> bytes:
    if path.suffix.lower() != ".woff2":
        return path.read_bytes()
    font = TTFont(path, recalcTimestamp=False)
    font.flavor = None
    output = BytesIO()
    font.save(output, reorderTables=False)
    return output.getvalue()


def shape(path: Path, text: str):
    font = hb.Font(hb.Face(sfnt_bytes(path)))
    buffer = hb.Buffer()
    buffer.add_str(text)
    buffer.guess_segment_properties()
    hb.shape(font, buffer)
    return list(buffer.glyph_infos), list(buffer.glyph_positions)


def validate_shaping(path: Path, font: TTFont) -> list[str]:
    errors = []
    order = font.getGlyphOrder()
    cmap = font.getBestCmap() or {}
    dotted = order.index(cmap[DOTTED_CIRCLE])
    idotless = order.index(cmap[0x0131])
    ogonek = order.index(cmap[0x0328])
    for mark in sorted(c for c in cmap if 0x0300 <= c <= 0x036F):
        infos, positions = shape(path, chr(DOTTED_CIRCLE) + chr(mark))
        if len(infos) != 2 or infos[0].codepoint != dotted:
            errors.append(f"{path}: U+25CC failed to retain U+{mark:04X}")
        elif positions[1].x_advance != 0 or (
            positions[1].x_offset == 0 and positions[1].y_offset == 0
        ):
            errors.append(f"{path}: U+{mark:04X} did not attach to U+25CC")
    for mark in REQUIRED_MARKS + OPTIONAL_MARKS:
        infos, _ = shape(path, "į" + chr(mark))
        got = [i.codepoint for i in infos]
        want = [idotless, ogonek, order.index(cmap[mark])]
        if got != want:
            errors.append(f"{path}: į + U+{mark:04X} shaped to {got}, expected {want}")
    return errors


ALT_SUFFIX = ".shape"
ALTERNATE_SAMPLES = ("aaaa", "llll", "0000", "ﬁﬁﬁﬁ", "ąąąą", "AAAA")


def glyph_area(glyphs, name: str) -> float:
    pen = AreaPen(glyphs)
    glyphs[name].draw(pen)
    return abs(pen.value)


def validate_alternates(path: Path, font: TTFont) -> list[str]:
    """Every alternate keeps its default's width; calt rotates repeats."""
    errors = []
    order = font.getGlyphOrder()
    names = set(order)
    hmtx = font["hmtx"]
    alternates = [n for n in order if ALT_SUFFIX in n]
    glyphs = font.getGlyphSet()
    if not alternates:
        return [f"{path}: no {ALT_SUFFIX}N contextual alternates"]
    for name in alternates:
        base = name.rsplit(ALT_SUFFIX, 1)[0]
        if base not in names:
            errors.append(f"{path}: alternate {name} has no default glyph")
        elif hmtx[name][0] != hmtx[base][0]:
            errors.append(f"{path}: {name} width {hmtx[name][0]} != {base} {hmtx[base][0]}")
        else:
            # A variant redraws the same cells, so its ink stays close to the
            # default's; a lost component drops most of the glyph.
            ink, base_ink = glyph_area(glyphs, name), glyph_area(glyphs, base)
            if base_ink and not 0.6 < ink / base_ink < 1.6:
                errors.append(f"{path}: {name} ink {ink:.0f} is far from {base} {base_ink:.0f}")
    features = {r.FeatureTag for r in font["GSUB"].table.FeatureList.FeatureRecord}
    if "calt" not in features:
        errors.append(f"{path}: missing calt feature")
        return errors
    for text in ALTERNATE_SAMPLES:
        infos, _ = shape(path, text)
        glyphs = [order[i.codepoint] for i in infos]
        if len(set(glyphs)) != len(glyphs):
            errors.append(f"{path}: calt repeats a variant in {text!r}: {glyphs}")
    return errors


def validate_font(path: Path) -> list[str]:
    widths, cmap, carets, _ = source_expectations()
    errors: list[str] = []
    font = TTFont(path, recalcTimestamp=False)
    try:
        if "fvar" in font:
            errors.append(f"{path}: Namche Shape statics must not contain fvar")
        actual_cmap = font.getBestCmap() or {}
        expected_cmap = dict(cmap)
        expected_cmap[0x00AD] = "uni00AD"
        if set(actual_cmap) != set(expected_cmap):
            missing = sorted(set(expected_cmap) - set(actual_cmap))
            extra = sorted(set(actual_cmap) - set(expected_cmap))
            errors.append(f"{path}: cmap differs; missing={missing}, extra={extra}")
        classes = {}
        if "GDEF" in font and font["GDEF"].table.GlyphClassDef:
            classes = font["GDEF"].table.GlyphClassDef.classDefs
        for codepoint, source_name in cmap.items():
            glyph_name = actual_cmap.get(codepoint)
            if glyph_name is None:
                continue
            width = font["hmtx"][glyph_name][0]
            if classes.get(glyph_name) == 3:
                # ufo2ft zeroes the advance of combining marks, as the
                # Glyphs export did for the released Pixel statics.
                if width != 0:
                    errors.append(f"{path}: mark U+{codepoint:04X} has width {width}")
            elif width != widths[source_name]:
                errors.append(
                    f"{path}: U+{codepoint:04X} width {width}, source {widths[source_name]}"
                )
        soft = actual_cmap.get(0x00AD)
        if soft is None or font["hmtx"][soft][0] != 0 or has_ink(font, soft):
            errors.append(f"{path}: U+00AD must be an inkless zero-width glyph")
        for codepoint in SEPARATORS:
            glyph_name = actual_cmap.get(codepoint)
            if glyph_name is None:
                errors.append(f"{path}: missing U+{codepoint:04X}")
                continue
            if font["hmtx"][glyph_name] != (SEPARATOR_WIDTH, 0):
                errors.append(f"{path}: U+{codepoint:04X} metrics {font['hmtx'][glyph_name]}")
            if has_ink(font, glyph_name):
                errors.append(f"{path}: U+{codepoint:04X} must remain inkless")
        for glyph_name, coordinates in carets.items():
            if glyph_name not in font.getGlyphOrder():
                errors.append(f"{path}: missing {glyph_name} ligature glyph")
            elif ligature_carets(font, glyph_name) != coordinates:
                errors.append(
                    f"{path}: {glyph_name} carets {ligature_carets(font, glyph_name)!r}, "
                    f"expected {coordinates!r}"
                )
        for codepoint in (RUPEE, DOTTED_CIRCLE):
            glyph_name = actual_cmap.get(codepoint)
            if glyph_name is None or not has_ink(font, glyph_name):
                errors.append(f"{path}: U+{codepoint:04X} must be present with ink")
        if not errors:
            errors.extend(validate_shaping(path, font))
            errors.extend(validate_alternates(path, font))
    finally:
        font.close()
    return errors


def validate_source() -> list[str]:
    _, cmap, carets, fontinfo = source_expectations()
    errors = []
    for codepoint in (RUPEE, DOTTED_CIRCLE):
        if codepoint not in cmap:
            errors.append(f"{ns.SOURCE}: missing U+{codepoint:04X}")
    for required in ("fi", "fl"):
        if required not in carets:
            errors.append(f"{ns.SOURCE}: missing {required} caret anchors")
    if IOGONEK_RULE not in fontinfo:
        errors.append(f"{ns.SOURCE}: missing reviewed iogonek ccmp rule")
    return errors


def outline_recordings(path: Path) -> dict[str, list]:
    font = TTFont(path, recalcTimestamp=False)
    glyphs = font.getGlyphSet()
    result = {}
    for name in font.getGlyphOrder():
        pen = DecomposingRecordingPen(glyphs)
        glyphs[name].draw(pen)
        result[name] = pen.value
    font.close()
    return result


# Boolean operations run in floating point. At exact tangencies (touching
# circles, coincident stroke edges) x86 and Apple Silicon can return the same
# shape with a different contour order or segmentation. Outlines therefore
# match when the area where they disagree (their XOR) is negligible.
XOR_AREA_TOLERANCE = 2.0  # square font units


def _path(recording: list) -> "pathops.Path":
    import pathops
    from fontTools.pens.recordingPen import RecordingPen

    path = pathops.Path()
    pen = RecordingPen()
    pen.value = recording
    pen.replay(path.getPen())
    return path


def outline_difference(a: list, b: list) -> str | None:
    import pathops

    if not a and not b:
        return None
    result = pathops.Path()
    pathops.xor([_path(a)], [_path(b)], result.getPen())
    area = abs(result.area)
    if area > XOR_AREA_TOLERANCE:
        return f"outlines disagree over {area:.1f} square units"
    return None


def validate_reproducible(root: Path) -> list[str]:
    import build_namche_shape

    errors = []
    grids = ns.load_grids()
    overrides = ns.load_overrides()
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "NamcheShape"
        for style in STYLES:
            build_namche_shape.build_style(style, grids, overrides, out)
            for sub, suffix in (("otf", "otf"), ("ttf", "ttf")):
                committed = root / "fonts" / "NamcheShape" / sub / f"NamcheShape-{style}.{suffix}"
                fresh = out / sub / f"NamcheShape-{style}.{suffix}"
                if not committed.is_file():
                    continue
                a, b = outline_recordings(committed), outline_recordings(fresh)
                changed = {}
                for name in sorted(a.keys() | b.keys()):
                    if name not in a or name not in b:
                        changed[name] = "glyph missing"
                        continue
                    problem = outline_difference(a[name], b[name])
                    if problem:
                        changed[name] = problem
                if changed:
                    sample = ", ".join(f"{n} ({why})" for n, why in list(changed.items())[:6])
                    errors.append(
                        f"{committed}: {len(changed)} outlines differ from the generator: "
                        f"{sample}; run make build-shape"
                    )
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ns.ROOT)
    parser.add_argument("--reproducible", action="store_true")
    parser.add_argument(
        "--release-only",
        action="store_true",
        help="skip the npm copies (before make copy-npm-fonts has run)",
    )
    args = parser.parse_args()
    root = args.root.resolve()
    errors = validate_source()
    for path in expected_fonts(root):
        if args.release_only and "packages" in path.parts:
            continue
        if not path.is_file():
            errors.append(f"missing expected Namche Shape font: {path}")
            continue
        errors.extend(validate_font(path))
    if args.reproducible:
        errors.extend(validate_reproducible(root))
    if errors:
        print("Namche Shape validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print(
        "Verified Namche Shape glyph set, metrics, separators, carets, ₹, ◌, "
        "į shaping, and calt alternates"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
