#!/usr/bin/env python3
"""Validate the minimum safe Mono hmtx encoding for the approved glyph order."""

from __future__ import annotations

import argparse
from itertools import product
from pathlib import Path

from fontTools.ttLib import TTFont


EXPECTED_ZERO_WIDTH_GLYPHS = {
    "acutecomb",
    "dotbelowcomb",
    "dotbelowcomb.ss08",
    "gravecomb",
    "hookabovecomb",
    "tildecomb",
    "uni0302",
    "uni03020300",
    "uni03020301",
    "uni03020303",
    "uni03020309",
    "uni0304",
    "uni0306",
    "uni03060300",
    "uni03060301",
    "uni03060303",
    "uni03060309",
    "uni0306.cy",
    "uni0307",
    "uni0307.ss08",
    "uni0308",
    "uni0308.ss08",
    "uni030A",
    "uni030B",
    "uni030C",
    "uni030C.alt",
    "uni0312",
    "uni031B",
    "uni0326",
    "uni0326.loclMAH",
    "uni0327",
    "uni0328",
    "uni0335",
    "uni0335.case",
    "uni0336",
    "uni0337",
    "uni0337.case",
    "uni0338",
    "uni0338.case",
}
EXPECTED_EXCEPTIONAL_ADVANCES = {".notdef": 500} | {
    name: 0 for name in EXPECTED_ZERO_WIDTH_GLYPHS
}
EXPECTED_FILE_COUNT = 80


def minimum_metric_count(widths: list[int]) -> int:
    if not widths:
        raise ValueError("font has no horizontal metrics")
    last_advance = widths[-1]
    count = len(widths)
    while count > 1 and widths[count - 2] == last_advance:
        count -= 1
    return count


def variable_locations(font: TTFont) -> list[dict[str, float]]:
    if "fvar" not in font:
        return []
    axes = font["fvar"].axes
    defaults = {axis.axisTag: axis.defaultValue for axis in axes}
    locations = [{axis.axisTag: 0.0 for axis in axes}]
    for axis in font["fvar"].axes:
        for value in (axis.minValue, axis.maxValue):
            locations.append(font.normalizeLocation(defaults | {axis.axisTag: value}))
    locations.extend(
        font.normalizeLocation(instance.coordinates)
        for instance in font["fvar"].instances
    )
    if "HVAR" in font:
        regions = font["HVAR"].table.VarStore.VarRegionList.Region
        for region in regions:
            breakpoints = [
                {axis.StartCoord, axis.PeakCoord, axis.EndCoord}
                for axis in region.VarRegionAxis
            ]
            locations.extend(
                dict(zip((axis.axisTag for axis in axes), coordinates, strict=True))
                for coordinates in product(*breakpoints)
            )
    return list({tuple(sorted(location.items())): location for location in locations}.values())


def exceptional_advances(
    font: TTFont, order: list[str], location: dict[str, float] | None = None
) -> dict[str, int | float]:
    if location is None:
        widths = (font["hmtx"][name][0] for name in order)
    else:
        glyph_set = font.getGlyphSet(
            location=location, normalized=True, recalcBounds=False
        )
        widths = (glyph_set[name].width for name in order)
    return {
        name: width
        for name, width in zip(order, widths, strict=True)
        if width != 600
    }


def validate_font(path: Path) -> list[str]:
    errors: list[str] = []
    font = TTFont(path, recalcTimestamp=False)
    try:
        order = font.getGlyphOrder()
        widths = [font["hmtx"][name][0] for name in order]
        actual = font["hhea"].numberOfHMetrics
        minimum = minimum_metric_count(widths)
        if actual != minimum:
            errors.append(
                f"{path}: numberOfHMetrics {actual} is not the safe minimum {minimum}"
            )
        expected_advances = {name: value for name, value in EXPECTED_EXCEPTIONAL_ADVANCES.items() if name in order}
        default_advances = exceptional_advances(font, order)
        if default_advances != expected_advances:
            errors.append(
                f"{path}: glyph-specific non-600 advances differ from the "
                "reviewed baseline"
            )
        for location in variable_locations(font):
            instance_advances = exceptional_advances(font, order, location)
            if instance_advances != expected_advances:
                errors.append(
                    f"{path}: HVAR-adjusted advances at normalized location "
                    f"{location} differ from "
                    "the reviewed glyph-specific baseline"
                )
    finally:
        font.close()
    return errors


def mono_fonts(root: Path) -> list[Path]:
    release = root / "fonts" / "NamcheShadowMono"
    package = (
        root
        / "packages"
        / "next"
        / "dist"
        / "fonts"
        / "namche-shadow-mono"
    )
    paths = [
        path
        for directory in (release / "ttf", release / "variable", release / "webfonts", package)
        for path in directory.glob("*")
        if path.suffix.lower() in {".ttf", ".woff2"}
    ]
    return sorted(paths)


def validate_release(root: Path) -> list[str]:
    paths = mono_fonts(root)
    errors: list[str] = []
    if len(paths) != EXPECTED_FILE_COUNT:
        errors.append(
            f"expected {EXPECTED_FILE_COUNT} Mono TrueType release/npm fonts; "
            f"found {len(paths)}"
        )
    for path in paths:
        errors.extend(validate_font(path))
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent)
    args = parser.parse_args()
    errors = validate_release(args.root.resolve())
    if errors:
        print("Mono horizontal-metric validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print(
        "Verified minimum safe numberOfHMetrics in 80 Mono release/npm fonts "
        "with the retained Latin Core glyph order"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
