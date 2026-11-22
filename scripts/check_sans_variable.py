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
INTERMEDIATE_OUTLINE_DIGESTS = {150: '6fd9fe38ec4635aa22b5ca3e0d75210e4f13aac9a7de7b287c5d7a52d65bf876', 250: '4a61d4c2702ce61a7326299928ff45032ae2694fbc542d4442751afd59fedfce', 350: 'b75a963e1c0c6e0492ebc3764a8c92d0bb44293dfddc770a289586df21b6233f', 450: '8913a4e03589c118c6667a10d365f2a0c6d8f3192c00bf33df4ccece613cb75f', 550: '11fb7f86cfdcd351a2aa63b780f4a2a87e838b40cc942bc46a2d88f48d962520', 650: '75991f7b73ed945fbc73fa9d5510162c4a8835fced1539d61e2d6592979cb399', 750: 'ae8dc7ed7374898f6f14ce494dbb5d750092b092299bade540093a18a7eded49', 850: '49ee42acefad64e9f60f8ebc390ad09d8689ccc8375daff4c2f440c20fd18673'}
ITALIC_INTERMEDIATE_OUTLINE_DIGESTS = {150: '06db844705960e210b9954948fe2ea453fb217a08af5c1ba1ced5de7dd73b65d', 250: '014fd4a301409c566ac54727ec69bd89fdcee9eeb702ba1dde0230a4fe871e48', 350: 'fe828da082741733725dc206d7b74ae8e9d41178ba1c266848c55ffd604d0985', 450: 'b9d7b4186901c6d64ba00402a8d9a85f6a65c70e49f638499dd9cb68d198c2cf', 550: '15c628e3845add952576a07ba8f73a39a05b1a75e080afa46fd7e9814ffb2b03', 650: '04b56fd5ac8fe289acca3eb873d61c5e388d81840e15e81006b3a64184a665cb', 750: '8a166e474e700baa3eb1f8ba4e4d8a721a58cfc3e6ad30fa69459eaa1340407d', 850: '986d8ebf3a339bd6a3c6bec81c017d9eac32d8b43bb23041f5b8d4434c5d5b45'}
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
    # Compatible VFs retain overlapping base/fillet contours; statics union
    # them. Compare their visible nonzero-filled boundaries, not hidden backing
    # edges. _filled_path also decomposes components before taking the union.
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
        # statics; the compatible VF retains intentionally overlapping patches.
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
