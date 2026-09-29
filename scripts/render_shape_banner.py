#!/usr/bin/env python3
"""Render the Namche Shape README banners from the shipped font files."""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from render_banners import fit_font, read_package_version, render_mark

WIDTH = 2048
HEIGHT = 2208
STYLES = (
    ("METABALL", "Pixels melt, not every connection"),
    ("ORIGIN", "The grid becomes a chessboard"),
    ("SKELETON", "A network as the trace of the pixels"),
)


def draw_banner(font_dir: Path, mark_svg: Path, output: Path, dark: bool, version: str) -> None:
    mono_path = Path("fonts/NamcheShadowMono/ttf/NamcheShadowMono-Medium.ttf")
    colors = {
        "background": "#0d1738" if dark else "#f0f2f5",
        "text": "#f0f2f5" if dark else "#262626",
        "muted": "#94c7e6" if dark else "#66666e",
        "line": "#738cd9" if dark else "#bdb5a1",
        "yellow": "#ffd433",
        "purple": "#b88cd1",
        "green": "#0e7a5f",
    }
    image = Image.new("RGB", (WIDTH, HEIGHT), colors["background"])
    draw = ImageDraw.Draw(image)

    draw.rectangle((0, 0, 1365, 560), fill=colors["purple"])
    draw.rectangle((1365, 0, WIDTH, 560), fill=colors["yellow"])
    mark = render_mark(mark_svg, "#262626", 280)
    image.paste(mark, (1560, 140), mark)

    label = ImageFont.truetype(str(mono_path), 30)
    small = ImageFont.truetype(str(mono_path), 26)
    metaball = font_dir / "NamcheShape-Metaball.ttf"
    draw.text((100, 90), "NAMCHE / TYPE SYSTEM 02", font=label, fill="#262626")
    title = fit_font(metaball, "NAMCHE", 1180, 170)
    draw.text((96, 180), "NAMCHE", font=title, fill="#262626")
    sub = fit_font(metaball, "SHAPE", 1180, 170)
    draw.text((96, 350), "SHAPE", font=sub, fill="#262626")

    y = 640
    for style, intention in STYLES:
        path = font_dir / f"NamcheShape-{style.title()}.ttf"
        draw.text((96, y), f"{style} / {intention.upper()}", font=label, fill=colors["muted"])
        big = fit_font(path, "Aa Bb Rr Gg 0123", 1856, 200)
        draw.text((96, y + 60), "Aa Bb Rr Gg 0123", font=big, fill=colors["text"])
        line = fit_font(path, "abcdefghijklmnopqrstuvwxyz", 1856, 96)
        draw.text((96, y + 300), "abcdefghijklmnopqrstuvwxyz", font=line, fill=colors["text"])
        y += 440
        draw.line((96, y - 30, 1952, y - 30), fill=colors["line"], width=3)

    draw.text((96, 2040), "OWNED BY BTLG HOLDING GMBH / GRID FROM GEIST PIXEL", font=small, fill=colors["muted"])
    draw.text((96, 2085), "DESIGNED BY MICHAEL MARTE FOR RUHM ETC.", font=small, fill=colors["muted"])
    draw.text((1475, 2085), f"OFL-1.1 / v{version}", font=small, fill=colors["muted"])
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output, optimize=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=Path(".docs/img"))
    args = parser.parse_args()
    version = read_package_version()
    font_dir = Path("fonts/NamcheShape/ttf")
    mark_svg = Path(".docs/img/namche-mark.svg")
    for dark in (False, True):
        suffix = "dark" if dark else "light"
        draw_banner(font_dir, mark_svg, args.output_dir / f"namche-shape-banner--{suffix}.png", dark, version)


if __name__ == "__main__":
    main()
