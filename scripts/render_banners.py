#!/usr/bin/env python3
"""Render the Namche Shadow repository banners from the shipped font files."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import tempfile

from PIL import Image, ImageDraw, ImageFont


WIDTH = 2048
HEIGHT = 2208


def read_package_version() -> str:
    repo_root = Path(__file__).resolve().parent.parent
    package = json.loads((repo_root / "packages/next/package.json").read_text())
    return package["version"]


def fit_font(path: Path, text: str, max_width: int, size: int) -> ImageFont.FreeTypeFont:
    while size > 20:
        font = ImageFont.truetype(path, size)
        if font.getlength(text) <= max_width:
            return font
        size -= 2
    return ImageFont.truetype(path, size)


def render_mark(mark_svg: Path, color: str, size: int) -> Image.Image:
    with tempfile.TemporaryDirectory() as temp_dir:
        source = Path(temp_dir) / "mark.svg"
        target = Path(temp_dir) / "mark.png"
        svg = mark_svg.read_text().replace("currentColor", color)
        source.write_text(svg)
        subprocess.run(
            ["resvg", "--width", str(size), "--height", str(size), str(source), str(target)],
            check=True,
        )
        return Image.open(target).convert("RGBA")


def draw_banner(font_dir: Path, mark_svg: Path, output: Path, dark: bool, version: str) -> None:
    regular_path = font_dir / "NamcheShadowSans-Regular.ttf"
    black_path = font_dir / "NamcheShadowSans-Black.ttf"
    mono_path = Path("fonts/NamcheShadowMono/ttf/NamcheShadowMono-Medium.ttf")

    colors = {
        "background": "#0d1738" if dark else "#f0f2f5",
        "text": "#f0f2f5" if dark else "#262626",
        "muted": "#94c7e6" if dark else "#66666e",
        "line": "#738cd9" if dark else "#bdb5a1",
        "yellow": "#ffd433",
        "orange": "#eb8a29",
        "purple": "#b88cd1",
        "green": "#0e7a5f",
        "blue": "#94c7e6",
        "red": "#e03847",
    }
    image = Image.new("RGB", (WIDTH, HEIGHT), colors["background"])
    draw = ImageDraw.Draw(image)

    # Brand-system header: strict X/8 modules, high-altitude palette, and the
    # organic Namche mark from the supplied design-system export.
    draw.rectangle((0, 0, 1365, 760), fill=colors["yellow"])
    draw.rectangle((1365, 0, WIDTH, 380), fill=colors["blue"])
    draw.rectangle((1365, 380, WIDTH, 760), fill=colors["purple"])
    mark = render_mark(mark_svg, "#262626", 310)
    image.paste(mark, (1450, 225), mark)

    label = ImageFont.truetype(mono_path, 30)
    draw.text((100, 90), "NAMCHE / TYPE SYSTEM 01", font=label, fill="#262626")
    title = fit_font(black_path, "NAMCHE SHADOW", 1180, 154)
    draw.text((96, 235), "NAMCHE SHADOW", font=title, fill="#262626")
    sans = fit_font(regular_path, "SANS", 720, 218)
    draw.text((96, 405), "SANS", font=sans, fill="#262626")

    # Type specimen.
    draw.text((96, 850), "ROUND INNER CORNERS / CRISP OUTER FORM", font=label, fill=colors["muted"])
    alphabet = fit_font(regular_path, "ABCDEFGHIJKLMNO", 1856, 128)
    draw.text((96, 930), "ABCDEFGHIJKLMNO", font=alphabet, fill=colors["text"])
    draw.text((96, 1075), "PQRSTUVWXYZ", font=alphabet, fill=colors["text"])
    lower = fit_font(regular_path, "abcdefghijklmnopqrstuvwxyz", 1856, 114)
    draw.text((96, 1230), "abcdefghijklmnopqrstuvwxyz", font=lower, fill=colors["text"])
    figures = fit_font(black_path, "0123456789!? &@%{}→", 1856, 112)
    draw.text((96, 1375), "0123456789!? &@%{}→", font=figures, fill=colors["text"])

    draw.line((96, 1550, 1952, 1550), fill=colors["line"], width=3)
    statement = fit_font(black_path, "FUTURE IS A FORM", 1856, 150)
    draw.text((96, 1625), "FUTURE IS A FORM", font=statement, fill=colors["text"])
    draw.text((96, 1785), "WE SHAPE TOGETHER.", font=statement, fill=colors["text"])

    # Ownership and attribution remain legible inside the image wherever it is
    # copied, without using the original authors to endorse the derivative.
    small = ImageFont.truetype(mono_path, 26)
    draw.text((96, 2040), "OWNED BY BTLG HOLDING GMBH", font=small, fill=colors["muted"])
    draw.text((96, 2085), "DESIGNED BY MICHAEL MARTE FOR RUHM ETC.", font=small, fill=colors["muted"])
    draw.text((1475, 2085), f"OFL-1.1 / v{version}", font=small, fill=colors["muted"])

    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output, optimize=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=Path(".docs/img"))
    args = parser.parse_args()
    version = read_package_version()
    font_dir = Path("fonts/NamcheShadowSans/ttf")
    mark_svg = Path(".docs/img/namche-mark.svg")
    draw_banner(
        font_dir,
        mark_svg,
        args.output_dir / "namche-shadow-banner--light.png",
        dark=False,
        version=version,
    )
    draw_banner(
        font_dir,
        mark_svg,
        args.output_dir / "namche-shadow-banner--dark.png",
        dark=True,
        version=version,
    )


if __name__ == "__main__":
    main()
