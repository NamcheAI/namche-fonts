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
from fontTools.pens.recordingPen import DecomposingRecordingPen, RecordingPen
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



INTERPOLATION_REVIEW_GLYPHS = (
    "uni0163",
    "ordfeminine",
    "uni0472",
    "uni04E9",
    "ampersand",
)
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
INTERMEDIATE_OUTLINE_DIGESTS = {
    150: "158bfe31f4ded1b8585d9453223dbda3468428af886455c41d44b9e84a6c2d66",
    250: "fe61899d9e46d201b010655deb1d4f5c51bbf04520f5605e44de2ed0e5a2fc78",
    350: "068258cb28e1db0c7bc63848090bd2870a30e67ff87f1bc927a19bd934e8dc4c",
    450: "816f2942427fee10256ad222ba915e42635a0ee210fdd38d0be09a2bef2b18f6",
    550: "d30a74651bb77777b97edd774fcc3cbf1a21d64bf1278d9c641c450100ee59ff",
    650: "9db82c5dc2e95a36e012b66d9ae1576c258df5415559c5a9827715ab938920ec",
    750: "5ed9e91d3e243b4d3c7644fc5c2b7adbbd3b2ecbfeeed9a883ce9579cd7535c6",
    850: "d5690b1d3906d9be354f1ad14c1ee000e1db8919f62d7bf42dfcfdf64853618e",
}
ITALIC_INTERMEDIATE_OUTLINE_DIGESTS = {
    150: "c095880c313270af04fd593ebb838017cdfaa28ced310ec3a4f81ea22f8578a0",
    250: "2373622b8c9e88b560bc26087412afeaa224f3f2a9681f670e12b75c3966104d",
    350: "da96b5a335657c9308efe9a4961feaee8b59715251a926c4564338f16052939c",
    450: "05722529b9e558494db11b92bf6075b56b6041dc91dcface3caa49a5e59754b7",
    550: "0d81a736d5db3cd78a45cd54d38be65b2dfc801388b66dc07af6a2c15e2fc750",
    650: "de74cbce1d069785735ce5cc3595a1e5a108ecb13d839bf0949a99e8bde42190",
    750: "dce939878d43a2629cffa3f24ac4ae744e39cfdbfd7b9e4c234acc6ba5592704",
    850: "d473f6ea96ba11018db1e2c5f4c2ff909c65cf8a28990ea159c4cf34c237f4c3",
}
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
    # FlattenPen drops components, so decompose composite glyphs before
    # sampling.
    decomposed = DecomposingRecordingPen(glyph_set)
    glyph_set[glyph_name].draw(decomposed)
    recording = RecordingPen()
    flattening = FlattenPen(
        recording,
        approximateSegmentLength=OUTLINE_SAMPLE_LENGTH,
        segmentLines=True,
    )
    decomposed.replay(flattening)
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
        # The italic TTF statics keep overlapping composites; sampling them
        # directly would measure overlap depth instead of shape difference,
        # so outline distances compare against the union'd OTF statics.
        otf_static = TTFont(root / "otf" / f"NamcheShadowSans-{style}.otf", recalcTimestamp=False)
        if "fvar" in static:
            raise ValueError(f"static unexpectedly contains fvar: {style}")
        missing = PARKED_GLYPHS - set(static.getGlyphOrder())
        if missing:
            raise ValueError(f"{style} static is missing parked VF glyphs: {sorted(missing)}")
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
