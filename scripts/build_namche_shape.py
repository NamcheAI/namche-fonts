#!/usr/bin/env python3
"""Build the Namche Shape static fonts (Metaball, Origin, Skeleton).

The Glyphs source supplies the pixel grid, metrics, kerning, anchors, and
OpenType features. For each style this script converts the source to a UFO,
replaces every `pixel` component with the generated outline from
`scripts/namche_shape.py`, and compiles OTF, TTF, and WOFF2 with ufo2ft.
Accented glyphs keep their components, so a base-glyph refinement reaches all
of its composites.

Usage:
    venv/bin/python scripts/build_namche_shape.py [--output fonts/NamcheShape]
"""

from __future__ import annotations

import argparse
import copy
import logging
import sys
from pathlib import Path

import glyphsLib
import ufo2ft
from fontTools.pens.pointPen import SegmentToPointPen
from fontTools.ttLib import TTFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
import namche_shape as ns  # noqa: E402
import rename_font_metadata  # noqa: E402

FAMILY = "Namche Shape"
COMPACT = "NamcheShape"
VERSION = (1, 0)


def base_ufo():
    # Background layers are drawing references; their decomposition notices
    # are noise for this build.
    logging.getLogger("glyphsLib").setLevel(logging.ERROR)
    font = glyphsLib.GSFont(str(ns.SOURCE))
    # The Element Shape axis and its virtual master only drive the Geist
    # component swap; Namche Shape draws its own outlines per style.
    font.axes = []
    font.customParameters = [
        p for p in font.customParameters if p.name != "Virtual Master"
    ]
    for glyph in font.glyphs:
        master_layers = [l for l in glyph.layers if l.layerId == l.associatedMasterId]
        for layer in list(glyph.layers):
            if layer not in master_layers:
                del glyph.layers[layer.layerId]
    font.instances = []
    designspace = glyphsLib.to_designspace(font, minimize_glyphs_diffs=True)
    ufo = designspace.sources[0].font
    ufo.lib["public.skipExportGlyphs"] = [g.name for g in font.glyphs if not g.export]
    return ufo


def build_style(style: str, grids, overrides, output: Path) -> list[Path]:
    ufo = copy.deepcopy(base_ufo_cached())
    info = ufo.info
    info.familyName = FAMILY
    info.styleName = style
    info.styleMapFamilyName = f"{FAMILY} {style}"
    info.styleMapStyleName = "regular"
    info.openTypeNamePreferredFamilyName = FAMILY
    info.openTypeNamePreferredSubfamilyName = style
    info.postscriptFontName = f"{COMPACT}-{style}"
    info.postscriptFullName = f"{FAMILY} {style}"
    info.openTypeNameUniqueID = f"{VERSION[0]}.{VERSION[1]:03d};NMCH;{COMPACT}-{style}"
    info.versionMajor, info.versionMinor = VERSION
    info.openTypeNameVersion = f"Version {VERSION[0]}.{VERSION[1]:03d}"
    info.openTypeOS2WeightClass = 400
    info.openTypeOS2VendorID = "NMCH"

    # Base glyphs get their generated outline. Accented glyphs keep their
    # components unless the parts overlap (ogonek, cedilla, and similar marks
    # touch their base by design); those are decomposed into one union.
    cache: dict = {}
    for glyph in ufo:
        grid = grids.get(glyph.name)
        if grid is None or not (grid.cells or grid.components):
            continue
        if grid.cells and not grid.components:
            outline = ns.base_outline(style, grid, overrides)
        elif ns.parts_overlap(style, glyph.name, grids, overrides, cache):
            outline = ns.glyph_outline(style, glyph.name, grids, overrides, cache)
        else:
            # Keep the accent components; draw any own pixels (for example
            # the bar of Eth) as contours beside them.
            keep = [c for c in glyph.components if c.baseGlyph != "pixel"]
            glyph.clearContours()
            glyph.clearComponents()
            if grid.cells:
                ns.base_outline(style, grid, overrides).draw(
                    SegmentToPointPen(glyph.getPointPen())
                )
            for component in keep:
                glyph.components.append(component)
            continue
        glyph.clearContours()
        glyph.clearComponents()
        outline.draw(SegmentToPointPen(glyph.getPointPen()))
    for name in [n for n in ufo.keys() if n == "pixel" or n.startswith("pixel.")]:
        del ufo[name]
    skip = ufo.lib.get("public.skipExportGlyphs", [])
    ufo.lib["public.skipExportGlyphs"] = [
        n for n in skip if n in ufo and not (n == "pixel" or n.startswith("pixel."))
    ]
    # Glyphs.app adds an inkless, zero-width soft hyphen on export; the
    # released Pixel statics carry it, so keep it for parity.
    if "uni00AD" not in ufo:
        soft = ufo.newGlyph("uni00AD")
        soft.width = 0
        soft.unicodes = [0x00AD]
    order = ufo.lib.get("public.glyphOrder")
    if order:
        order = [n for n in order if n in ufo]
        if "uni00AD" not in order:
            order.insert(order.index("hyphen") + 1, "uni00AD")
        ufo.lib["public.glyphOrder"] = order
    skip_export = list(ufo.lib["public.skipExportGlyphs"])

    stem = f"{COMPACT}-{style}"
    written = []
    for kind, compile_fn, sub, suffix in (
        ("otf", ufo2ft.compileOTF, "otf", ".otf"),
        ("ttf", ufo2ft.compileTTF, "ttf", ".ttf"),
    ):
        options = dict(
            removeOverlaps=False,
            useProductionNames=True,
            skipExportGlyphs=skip_export,
        )
        if kind == "otf":
            options["optimizeCFF"] = ufo2ft.CFFOptimization.SUBROUTINIZE
        else:
            options["reverseDirection"] = True
            options["flattenComponents"] = True
        font = compile_fn(ufo, **options)
        finalize(font, style)
        path = output / sub / f"{stem}{suffix}"
        path.parent.mkdir(parents=True, exist_ok=True)
        font.save(path)
        rename_font_metadata.rewrite(path)
        written.append(path)
        if kind == "ttf":
            web = output / "webfonts" / f"{stem}.woff2"
            web.parent.mkdir(parents=True, exist_ok=True)
            woff = TTFont(path)
            woff.flavor = "woff2"
            woff.save(web)
            written.append(web)
    return written


def finalize(font: TTFont, style: str) -> None:
    if "glyf" in font:
        # Unhinted outlines: smooth and grid-fit at every size, as the
        # released Pixel statics did.
        from fontTools.ttLib import newTable
        from fontTools.ttLib.tables._g_a_s_p import GASP_SYMMETRIC_GRIDFIT, GASP_SYMMETRIC_SMOOTHING, GASP_DOGRAY, GASP_GRIDFIT

        gasp = newTable("gasp")
        gasp.version = 1
        gasp.gaspRange = {
            0xFFFF: GASP_GRIDFIT | GASP_DOGRAY | GASP_SYMMETRIC_GRIDFIT | GASP_SYMMETRIC_SMOOTHING
        }
        font["gasp"] = gasp
    os2 = font["OS/2"]
    if os2.version < 4:
        os2.version = 4
    head = font["head"]
    head.fontRevision = VERSION[0] + VERSION[1] / 1000


_BASE = None


def base_ufo_cached():
    global _BASE
    if _BASE is None:
        _BASE = base_ufo()
    return _BASE


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", type=Path, default=ns.ROOT / "fonts" / "NamcheShape")
    ap.add_argument("--styles", default=",".join(ns.STYLES))
    args = ap.parse_args()
    grids = ns.load_grids()
    overrides = ns.load_overrides()
    for style in args.styles.split(","):
        for path in build_style(style, grids, overrides, args.output):
            print(path.relative_to(ns.ROOT) if path.is_relative_to(ns.ROOT) else path)


if __name__ == "__main__":
    main()
