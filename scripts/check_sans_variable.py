#!/usr/bin/env python3
"""Validate the committed Namche Shadow Sans variable release files."""

from __future__ import annotations

import argparse
from hashlib import sha256
from pathlib import Path
from struct import pack

import numpy as np
from fontPens.flattenPen import FlattenPen
from fontTools.pens.areaPen import AreaPen
from fontTools.pens.recordingPen import RecordingPen
from check_equal_ink import _filled_path
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

from build_sans_variable import (
    FAMILY,
    PARKED_GLYPHS,
    WEIGHTS,
    assert_contour_correspondence,
    display_style,
    file_style,
)



INTERPOLATION_REVIEW_GLYPHS = ("ordfeminine", "ampersand")
REPRESENTATIVE_GLYPHS = (
    "H",
    "E",
    "a",
    "A",
    "V",
    "M",
    "Z",
    "zero",
    "one",
    "two",
    "nine",
    "Scedilla",
    "Uogonek",
    *INTERPOLATION_REVIEW_GLYPHS,
)
OUTLINE_SAMPLE_LENGTH = 4
STATIC_OUTLINE_TOLERANCE = 7
INTERMEDIATE_OUTLINE_DIGESTS = {150: '584dde494583c43dceb173352d6e50213b1ff794850ffbc2aacbe198198ddd1a', 250: 'c72255f7dddea714c079e5751fa30456317bddfe7bd78f7dd94053d3cbbe20bd', 350: '0413e4c5580775366f48c0b2daf866ab0137f1916caf916bfa4f39716ffc9ded', 450: '265029d9c7348090065f649460aba3b708f842dc29a45d7ea3f93efd900f2b22', 550: 'c72e729aeebf0e46912cde758d4a27780c45440d7f9d0b87698574f3facaf108', 650: '578623fd34ba1327d3482a78a6f396dd574e743596a92d987e990d3b6e18a45c', 750: '97197a245b5b6edfad000eb40dc34daf246a14e45f107a9180b74412ca7423d5', 850: '508f853004616f713dcf4e54a188ff3485b27972af531c2282bc0f6157d9aea5'}
ITALIC_INTERMEDIATE_OUTLINE_DIGESTS = {150: '1dd626124c5295e3b31ccd8cac997d8ece3f427800b285e238c5620ef5bc2c48', 250: '7606c4c23395c64ea81b583684a76af89f2861c89993620bcc04e5a7b4ee948b', 350: '3c9ffc19a0a5a239e0af025899580f569e69e58d4302151623b33c6f55adccff', 450: '1beb1bced93c6d2040f5711ef6e8bd7bf14bf8f26b91fa867dd973ab04c19def', 550: '00b1cdd5c2248fa342d94c19991fcff39e75e458df955d819543dc844485d036', 650: '10027d6e77e988c605da4d20330885ddc7bea3ca81a96a0c9c87396d91f8c085', 750: '7dac6179f7ce7b8f4566857361fdec561bd6fdecedab918c1f939e026dd33c87', 850: 'fe86ec88aae0c77dbe0e0bbebd7e3ed7c7ef6d91ca05e965988b6440f9e393fa'}
NPM_ENTRYPOINTS = ("font.js", "sans.js")
NPM_UPRIGHT_STYLES = (
    "Thin",
    "UltraLight",
    "Light",
    "Regular",
    "Medium",
    "SemiBold",
    "Bold",
    "Black",
    "UltraBlack",
)


def _glyph_area(font: TTFont, glyph_name: str) -> float:
    glyph_set = font.getGlyphSet()
    pen = AreaPen(glyph_set)
    glyph_set[glyph_name].draw(pen)
    return pen.value


def _outline_points(font: TTFont, glyph_name: str) -> np.ndarray:
    """Flatten an outline so visually equivalent, differently segmented curves compare."""

    glyph_set = font.getGlyphSet()
    # Compare visible boundaries after decomposing components and resolving
    # any overlaps at the handful of variable-font corner guards.
    filled = _filled_path(glyph_set, glyph_name)
    recording = RecordingPen()
    flattening = FlattenPen(
        recording,
        approximateSegmentLength=OUTLINE_SAMPLE_LENGTH,
        segmentLines=True,
    )
    filled.draw(flattening)
    return np.asarray(
        [
            arguments[0]
            for command, arguments in recording.value
            if command in {"moveTo", "lineTo"}
        ],
        dtype=float,
    )


def _directed_outline_distance(source: np.ndarray, target: np.ndarray) -> float:
    maximum = 0.0
    for start in range(0, len(source), 1024):
        batch = source[start : start + 1024]
        distances = np.linalg.norm(batch[:, None, :] - target[None, :, :], axis=2)
        maximum = max(maximum, float(distances.min(axis=1).max()))
    return maximum


def _outline_distance(first: np.ndarray, second: np.ndarray) -> float:
    """Return the symmetric sampled-outline distance in font units."""

    return max(
        _directed_outline_distance(first, second),
        _directed_outline_distance(second, first),
    )


def _intermediate_outline_digest(font: TTFont) -> str:
    """Fingerprint reviewed intermediate geometry at 1/64-font-unit precision."""

    digest = sha256()
    for glyph_name in INTERPOLATION_REVIEW_GLYPHS:
        glyph = font["glyf"][glyph_name]
        coordinates, ends, flags = glyph.getCoordinates(font["glyf"])
        digest.update(glyph_name.encode("ascii") + b"\0")
        digest.update(pack(">I", len(coordinates)))
        for x, y in coordinates:
            digest.update(pack(">ii", round(x * 64), round(y * 64)))
        digest.update(pack(">I", len(ends)))
        for end in ends:
            digest.update(pack(">I", end))
        digest.update(bytes(flags))
    return digest.hexdigest()


def check_variable(root: Path, italic: bool, digests: dict[int, str]) -> tuple[Path, Path]:
    stem = "NamcheShadowSans-Italic[wght]" if italic else "NamcheShadowSans[wght]"
    variable_path = root / "variable" / f"{stem}.ttf"
    webfont_path = root / "webfonts" / f"{stem}.woff2"
    variable = TTFont(variable_path, recalcTimestamp=False)
    webfont = TTFont(webfont_path, recalcTimestamp=False)

    glyphs = set(variable.getGlyphOrder())
    if glyphs & PARKED_GLYPHS:
        raise ValueError(f"parked glyphs present in VF: {sorted(glyphs & PARKED_GLYPHS)}")
    if variable.getGlyphOrder() != webfont.getGlyphOrder() or "fvar" not in webfont:
        raise ValueError("TTF and WOFF2 variable releases do not match")

    axis = variable["fvar"].axes
    if len(axis) != 1 or (axis[0].axisTag, axis[0].minValue, axis[0].defaultValue, axis[0].maxValue) != (
        "wght",
        100,
        400,
        900,
    ):
        raise ValueError("unexpected variable axes")
    instance_weights = [instance.coordinates["wght"] for instance in variable["fvar"].instances]
    if instance_weights != [weight for _, weight in WEIGHTS]:
        raise ValueError(f"unexpected named instances: {instance_weights}")

    family_name = variable["name"].getDebugName(1)
    subfamily_name = variable["name"].getDebugName(2)
    credits = "\n".join(
        name.toUnicode()
        for name in variable["name"].names
        if name.nameID in {0, 8, 9}
    )
    if family_name != FAMILY:
        raise ValueError(f"unexpected family name: {family_name}")
    if subfamily_name != ("Italic" if italic else "Regular"):
        raise ValueError(f"unexpected subfamily name: {subfamily_name}")
    expected_instances = [display_style(base, italic) for base, _ in WEIGHTS]
    instance_names = [
        variable["name"].getDebugName(instance.subfamilyNameID)
        for instance in variable["fvar"].instances
    ]
    if instance_names != expected_instances:
        raise ValueError(f"unexpected instance names: {instance_names}")
    for credit in ("The Geist Project Authors", "Vercel", "BTLG Holding GmbH", "Michael Marte", "Ruhm"):
        if credit not in credits:
            raise ValueError(f"missing binary credit: {credit}")

    previous_instance = None
    for base, weight in WEIGHTS:
        style = file_style(base, italic)
        static = TTFont(root / "ttf" / f"NamcheShadowSans-{style}.ttf", recalcTimestamp=False)
        # Compare the visible VF boundary with independently compiled CFF
        # statics, including glyphs with local interpolation guards.
        otf_static = TTFont(root / "otf" / f"NamcheShadowSans-{style}.otf", recalcTimestamp=False)
        if "fvar" in static:
            raise ValueError(f"static unexpectedly contains fvar: {style}")
        if PARKED_GLYPHS & set(static.getGlyphOrder()):
            raise ValueError(f"{style} static contains out-of-scope parked glyphs")
        instance = instantiateVariableFont(variable, {"wght": weight}, inplace=False, optimize=False)
        if previous_instance is not None:
            assert_contour_correspondence(
                previous_instance, instance, f"{variable_path} wght={weight}"
            )
        previous_instance = instance
        variable_area = _glyph_area(instance, "O")
        static_area = _glyph_area(static, "O")
        if not variable_area or not static_area or variable_area * static_area <= 0:
            raise ValueError(f"VF contour direction does not match the {style} static")
        for glyph_name in INTERPOLATION_REVIEW_GLYPHS:
            distance = _outline_distance(
                _outline_points(instance, glyph_name),
                _outline_points(otf_static, glyph_name),
            )
            if distance > STATIC_OUTLINE_TOLERANCE:
                raise ValueError(
                    f"VF {glyph_name} at wght={weight} differs from the {style} static "
                    f"by {distance:.2f} units (limit {STATIC_OUTLINE_TOLERANCE})"
                )

    for weight in range(150, 900, 100):
        instance = instantiateVariableFont(variable, {"wght": weight}, inplace=False, optimize=False)
        for glyph_name in REPRESENTATIVE_GLYPHS:
            glyph = instance["glyf"][glyph_name]
            coordinates, ends, _ = glyph.getCoordinates(instance["glyf"])
            if not coordinates or not ends:
                raise ValueError(f"empty representative glyph {glyph_name} at wght={weight}")
        actual_digest = _intermediate_outline_digest(instance)
        expected_digest = digests[weight]
        if actual_digest != expected_digest:
            raise ValueError(
                f"reviewed interpolation outlines changed at wght={weight}: "
                f"expected {expected_digest}, got {actual_digest}"
            )
    return variable_path, webfont_path


def check(root: Path) -> None:
    upright = check_variable(root, italic=False, digests=INTERMEDIATE_OUTLINE_DIGESTS)
    italic = check_variable(root, italic=True, digests=ITALIC_INTERMEDIATE_OUTLINE_DIGESTS)

    npm_dist = Path(__file__).resolve().parent.parent / "packages" / "next" / "dist"
    required_faces_by_entrypoint = {
        **{
            entrypoint: {
                "NamcheShadowSans-Variable.woff2",
                "NamcheShadowSans-Italic[wght].woff2",
                *(f"NamcheShadowSans-{style}.woff2" for style in NPM_UPRIGHT_STYLES),
            }
            for entrypoint in NPM_ENTRYPOINTS
        },
        "sans-latin.js": {
            "NamcheShadowSans-Variable-latin.woff2",
            "NamcheShadowSans-Italic[wght]-latin.woff2",
        },
    }
    for entrypoint, required_faces in required_faces_by_entrypoint.items():
        source = (npm_dist / entrypoint).read_text()
        missing = sorted(name for name in required_faces if name not in source)
        if missing:
            raise ValueError(
                f"{entrypoint} is missing the VF/static fallback coverage: {missing}"
            )

    for paths in (upright, italic):
        print(f"Validated rounded Sans VF: {paths[0]} and {paths[1]}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", type=Path, default=Path("fonts/NamcheShadowSans"))
    args = parser.parse_args()
    check(args.root)


if __name__ == "__main__":
    main()
