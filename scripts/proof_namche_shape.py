#!/usr/bin/env python3
"""Render Namche Shape proof sheets straight from the generator.

Usage:
    venv/bin/python scripts/proof_namche_shape.py OUT.png [--text "NAMCHE"] [--size 120]
    venv/bin/python scripts/proof_namche_shape.py OUT.png --glyphs A,B,C
"""

from __future__ import annotations

import argparse
import sys

import glyphsLib
import skia

sys.path.insert(0, __file__.rsplit("/", 1)[0])
import namche_shape as ns  # noqa: E402


def glyph_skia_path(outline) -> skia.Path:
    sp = skia.Path()
    for verb, pts in outline:
        if verb == "moveTo":
            sp.moveTo(*pts[0])
        elif verb == "lineTo":
            sp.lineTo(*pts[0])
        elif verb == "curveTo":
            sp.cubicTo(*pts[0], *pts[1], *pts[2])
        elif verb == "qCurveTo":
            sp.quadTo(*pts[0], *pts[1])
        elif verb == "closePath":
            sp.close()
    return sp


def cmap_from_source() -> dict[str, str]:
    font = glyphsLib.GSFont(str(ns.SOURCE))
    cmap = {}
    for glyph in font.glyphs:
        for u in glyph.unicodes or []:
            cmap[chr(int(u, 16))] = glyph.name
    return cmap


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--text", action="append")
    ap.add_argument("--glyphs")
    ap.add_argument("--size", type=float, default=110)
    ap.add_argument("--styles", default=",".join(ns.STYLES))
    args = ap.parse_args()

    grids = ns.load_grids()
    overrides = ns.load_overrides()
    cmap = cmap_from_source()
    styles = args.styles.split(",")
    if args.glyphs:
        lines = [args.glyphs.split(",")]
    else:
        texts = args.text or ["NAMCHE"]
        lines = [[cmap.get(ch, "space") for ch in t] for t in texts]

    scale = args.size / 1000
    line_h = args.size * 1.35
    margin = 40
    widths = [sum(grids[n].width for n in line) * scale for line in lines]
    W = int(max(widths) + 2 * margin + 170)
    H = int(margin * 2 + len(styles) * len(lines) * line_h + len(styles) * 20)
    surface = skia.Surface(W, H)
    canvas = surface.getCanvas()
    canvas.clear(skia.Color(241, 239, 232))
    ink = skia.Paint(Color=skia.Color(17, 17, 17), AntiAlias=True)
    label = skia.Font(skia.Typeface("Helvetica"), 16)
    cache: dict = {}
    y = margin
    for style in styles:
        canvas.drawString(style, margin, y + 18, label, ink)
        for line in lines:
            baseline = y + args.size * 1.0
            x = margin + 150
            for name in line:
                outline = ns.glyph_outline(style, name, grids, overrides, cache)
                rec = skia.Path()
                sp = glyph_skia_path(_record(outline))
                m = skia.Matrix()
                m.setAll(scale, 0, x, 0, -scale, baseline, 0, 0, 1)
                sp.transform(m)
                sp.setFillType(skia.PathFillType.kWinding)
                canvas.drawPath(sp, ink)
                x += grids[name].width * scale
            y += line_h
        y += 20
    surface.makeImageSnapshot().save(args.out, skia.kPNG)
    print(args.out)


def _record(outline):
    from fontTools.pens.recordingPen import RecordingPen

    pen = RecordingPen()
    outline.draw(pen)
    return pen.value


if __name__ == "__main__":
    main()
