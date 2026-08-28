#!/usr/bin/env python3
"""Render visual proof panels for reviewed Fontspector maintenance issues."""

from __future__ import annotations

from pathlib import Path

from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.recordingPen import DecomposingRecordingPen
from fontTools.ttLib import TTFont
from PIL import Image, ImageChops, ImageDraw, ImageFont, features


WIDTH = 1600
BACKGROUND = "#f0f2f5"
TEXT = "#262626"
MUTED = "#66666e"
LINE = "#bdb5a1"
YELLOW = "#ffd433"
BLUE = "#94c7e6"
PURPLE = "#b88cd1"
RED = "#e03847"
GREEN = "#0e7a5f"

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "documentation" / "proofs" / "issues"
SANS_DIR = ROOT / "fonts" / "NamcheShadowSans" / "ttf"
MONO_DIR = ROOT / "fonts" / "NamcheShadowMono" / "ttf"
PIXEL_DIR = ROOT / "fonts" / "NamcheShadowPixel" / "ttf"
SANS_VF = ROOT / "fonts" / "NamcheShadowSans" / "variable" / "NamcheShadowSans[wght].ttf"
MONO_ITALIC_VF = (
    ROOT
    / "fonts"
    / "NamcheShadowMono"
    / "variable"
    / "NamcheShadowMono-Italic[wght].ttf"
)
REFERENCE_FONT_CANDIDATES = (
    Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf"),
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
)


def reference_font() -> Path:
    for path in REFERENCE_FONT_CANDIDATES:
        if path.is_file():
            return path
    raise FileNotFoundError("no Unicode reference font found for issue proofs")


def font(path: Path, size: int, weight: int | None = None) -> ImageFont.FreeTypeFont:
    kwargs = {}
    if features.check_feature("raqm"):
        kwargs["layout_engine"] = ImageFont.Layout.RAQM
    result = ImageFont.truetype(path, size, **kwargs)
    if weight is not None:
        result.set_variation_by_axes([weight])
    return result


def fit(path: Path, text: str, max_width: int, size: int) -> ImageFont.FreeTypeFont:
    while size > 22:
        candidate = font(path, size)
        if candidate.getlength(text) <= max_width:
            return candidate
        size -= 2
    return font(path, size)


def canvas(issue: int, title: str, subtitle: str, height: int) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    image = Image.new("RGB", (WIDTH, height), BACKGROUND)
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, 1060, 235), fill=YELLOW)
    draw.rectangle((1060, 0, WIDTH, 118), fill=BLUE)
    draw.rectangle((1060, 118, WIDTH, 235), fill=PURPLE)
    label = font(MONO_DIR / "NamcheShadowMono-Medium.ttf", 28)
    draw.text((72, 42), f"NAMCHE SHADOW / ISSUE #{issue}", font=label, fill=TEXT)
    draw.text(
        (68, 102),
        title,
        font=fit(SANS_DIR / "NamcheShadowSans-Black.ttf", title, 920, 76),
        fill=TEXT,
    )
    subtitle_font = fit(
        MONO_DIR / "NamcheShadowMono-Regular.ttf", subtitle, WIDTH - 144, 28
    )
    draw.text((72, 267), subtitle, font=subtitle_font, fill=MUTED)
    return image, draw


def section(draw: ImageDraw.ImageDraw, y: int, title: str, color: str = TEXT) -> None:
    label = font(MONO_DIR / "NamcheShadowMono-Medium.ttf", 25)
    draw.text((72, y), title.upper(), font=label, fill=color)
    draw.line((72, y + 42, WIDTH - 72, y + 42), fill=LINE, width=2)


def footer(draw: ImageDraw.ImageDraw, height: int, source: str) -> None:
    label = font(MONO_DIR / "NamcheShadowMono-Regular.ttf", 20)
    draw.line((72, height - 72, WIDTH - 72, height - 72), fill=LINE, width=2)
    draw.text((72, height - 52), f"SOURCE  {source}", font=label, fill=MUTED)


def name(font_file: Path, name_id: int) -> str:
    ttfont = TTFont(font_file, lazy=True)
    value = ttfont["name"].getDebugName(name_id) or ""
    ttfont.close()
    return value


def render_issue_20() -> None:
    image, draw = canvas(
        20,
        "LEGACY NAME LENGTH",
        "Variable aliases now fit; public family and STAT names stay complete.",
        1250,
    )
    section(draw, 340, "Variable italic aliases · family + style ≤ 32")
    ttfont = TTFont(MONO_ITALIC_VF, lazy=True)
    family = ttfont["name"].getBestFamilyName() or "Namche Shadow Mono"
    variable_names = []
    for instance in ttfont["fvar"].instances:
        style = ttfont["name"].getDebugName(instance.subfamilyNameID) or ""
        if style in {"XLight Italic", "SemiBd Italic", "XBold Italic"}:
            variable_names.append(f"{family} {style}")
    ttfont.close()
    specimen = MONO_DIR / "NamcheShadowMono-Italic.ttf"
    label = font(MONO_DIR / "NamcheShadowMono-Regular.ttf", 22)
    for index, value in enumerate(variable_names):
        y = 410 + index * 105
        draw.text((72, y), value, font=fit(specimen, value, 1220, 52), fill=TEXT)
        draw.text((1325, y + 15), f"{len(value)} / 32", font=label, fill=GREEN)

    section(draw, 750, "Static PostScript names · legal ≤ 63; guidance ≤ 27")
    samples = []
    for directory in (SANS_DIR, MONO_DIR):
        for path in sorted(directory.glob("*Italic.ttf")):
            value = name(path, 6)
            if len(value) > 27:
                samples.append(value)
    for index, value in enumerate(samples[:4]):
        y = 820 + index * 72
        draw.text((72, y), value, font=fit(specimen, value, 1190, 42), fill=TEXT)
        draw.text((1325, y + 8), f"{len(value)} / 63", font=label, fill=GREEN)
    draw.text(
        (72, 1120),
        "Kept canonical: shortening only name ID 6 creates hard Google-profile failures.",
        font=label,
        fill=MUTED,
    )
    footer(draw, image.height, "Mono italic VF and Sans/Mono italic statics")
    image.save(OUTPUT / "issue-20-name-length.png", optimize=True)


def draw_shaping_row(
    draw: ImageDraw.ImageDraw,
    y: int,
    title: str,
    sample: str,
    path: Path,
) -> None:
    label = font(MONO_DIR / "NamcheShadowMono-Regular.ttf", 22)
    draw.text((72, y), title, font=label, fill=MUTED)
    draw.text((72, y + 42), sample, font=fit(path, sample, 1440, 82), fill=TEXT)


def render_issue_21() -> None:
    image, draw = canvas(
        21,
        "LANGUAGE SHAPING",
        "Fixed in Sans + Mono; retained warnings are documented optional characters only.",
        1500,
    )
    sans = SANS_DIR / "NamcheShadowSans-Regular.ttf"
    mono = MONO_DIR / "NamcheShadowMono-Regular.ttf"
    section(draw, 340, "Fixed · Cyrillic mark attachment", GREEN)
    draw_shaping_row(draw, 405, "SANS · circumflex, grave, acute", "а̂ е̂ и̂ о̂ у̂    а̀ о̀ у̀ ъ̀ ю̀ я̀    і́ ї́ ы́ э́ ю́", sans)
    draw_shaping_row(draw, 555, "MONO · circumflex, grave, acute", "а̂ е̂ и̂ о̂ у̂    а̀ о̀ у̀ ъ̀ ю̀ я̀    і́ ї́ ы́ э́ ю́", mono)
    section(draw, 730, "Fixed · soft-dotted behavior", GREEN)
    draw_shaping_row(draw, 795, "SANS · the base dot disappears below each top mark", "і́   ј́   į̄ į̌ į̂ į̀ į̃ į́   ị̄ ị̂", sans)
    draw_shaping_row(draw, 945, "MONO · the base dot disappears below each top mark", "і́   ј́   į̄ į̌ į̂ į̀ į̃ į́   ị̄ ị̂", mono)
    section(draw, 1120, "Documented · optional auxiliary omissions", MUTED)
    draw_shaping_row(
        draw,
        1185,
        "REFERENCE RENDERING · deliberately not claimed as supported",
        "Ǿ ǿ   Ĕ ĕ Ĭ ĭ Ŀ ŀ Ŏ ŏ   Ĳ ĳ   Ȟ ȟ Ʒ ʒ Ǯ ǯ   Ǔ ǔ ſ ʻ",
        reference_font(),
    )
    footer(draw, image.height, "Namche Shadow Sans + Mono Regular · Unicode combining sequences")
    image.save(OUTPUT / "issue-21-language-shaping.png", optimize=True)


def render_issue_22() -> None:
    image, draw = canvas(
        22,
        "VARIABLE INTERPOLATION",
        "Blue = VF only; red = static only; dark areas overlap.",
        1500,
    )
    glyphs = [
        ("ţ", "uni0163"),
        ("ª", "ordfeminine"),
        ("Ѳ", "uni0472"),
        ("ө", "uni04E9"),
        ("&", "ampersand"),
    ]
    weights = [
        (100, "Thin"),
        (200, "ExtraLight"),
        (300, "Light"),
        (400, "Regular"),
        (500, "Medium"),
        (600, "SemiBold"),
        (700, "Bold"),
        (800, "ExtraBold"),
        (900, "Black"),
    ]
    label = font(MONO_DIR / "NamcheShadowMono-Regular.ttf", 20)
    cell_width = 137
    cell_height = 150
    grid_x = 275
    for column, (weight, _) in enumerate(weights):
        x = grid_x + column * cell_width
        draw.text((x + 48, 355), str(weight), font=label, fill=MUTED)
    for row, (character, glyph_name) in enumerate(glyphs):
        y = 405 + row * 185
        draw.text((72, y + 60), glyph_name, font=label, fill=MUTED)
        for column, (weight, style) in enumerate(weights):
            variable_mask = Image.new("L", (cell_width, cell_height))
            static_mask = Image.new("L", (cell_width, cell_height))
            variable = font(SANS_VF, 112, weight)
            static = font(SANS_DIR / f"NamcheShadowSans-{style}.ttf", 112)
            ImageDraw.Draw(variable_mask).text(
                (cell_width / 2, cell_height / 2),
                character,
                font=variable,
                fill=255,
                anchor="mm",
            )
            ImageDraw.Draw(static_mask).text(
                (cell_width / 2, cell_height / 2),
                character,
                font=static,
                fill=255,
                anchor="mm",
            )
            overlap = ImageChops.darker(variable_mask, static_mask)
            variable_only = ImageChops.subtract(variable_mask, static_mask)
            static_only = ImageChops.subtract(static_mask, variable_mask)
            cell = Image.new("RGB", (cell_width, cell_height), BACKGROUND)
            cell.paste(TEXT, mask=overlap)
            cell.paste(BLUE, mask=variable_only)
            cell.paste(RED, mask=static_only)
            image.paste(cell, (grid_x + column * cell_width, y))
    footer(
        draw,
        image.height,
        "Sans VF versus all nine approved upright statics · 1000 units per em",
    )
    image.save(OUTPUT / "issue-22-variable-interpolation.png", optimize=True)


def render_issue_23() -> None:
    image, draw = canvas(
        23,
        "OUTLINE & METRICS TRIAGE",
        "Math widths stay intentional; missing Pixel features have focused follow-ups.",
        1360,
    )
    label = font(MONO_DIR / "NamcheShadowMono-Regular.ttf", 22)
    section(draw, 340, "Math-sign widths")
    draw.text((72, 410), "SANS", font=label, fill=MUTED)
    draw.text((250, 385), "− + × ÷ = ≠ ± ≈ < >", font=font(SANS_DIR / "NamcheShadowSans-Regular.ttf", 82), fill=TEXT)
    draw.text((72, 520), "MONO", font=label, fill=MUTED)
    draw.text((250, 495), "− + × ÷ = ≠ ± ≈ < >", font=font(MONO_DIR / "NamcheShadowMono-Regular.ttf", 82), fill=TEXT)
    section(draw, 650, "Pixel coverage / feature warnings")
    pixel_samples = [
        ("CIRCLE", PIXEL_DIR / "NamcheShadowPixel-Circle.ttf"),
        ("GRID", PIXEL_DIR / "NamcheShadowPixel-Grid.ttf"),
        ("LINE", PIXEL_DIR / "NamcheShadowPixel-Line.ttf"),
    ]
    for index, (style, path) in enumerate(pixel_samples):
        y = 720 + index * 120
        draw.text((72, y + 22), style, font=label, fill=MUTED)
        draw.text((300, y), "◌ · ₹ ﬁ ﬂ ‐", font=font(path, 72), fill=TEXT)
    draw.text(
        (72, 1110),
        "A box or fallback shape makes a missing glyph immediately visible.",
        font=label,
        fill=MUTED,
    )
    followups = (
        "#32 separators · #33 Mono hhea · #34 ₹ · #35 WWS · "
        "#36 dotted circle / į́ · #37 fi/fl carets"
    )
    draw.text(
        (72, 1160),
        followups,
        font=fit(MONO_DIR / "NamcheShadowMono-Regular.ttf", followups, 1456, 22),
        fill=MUTED,
    )
    footer(draw, image.height, "Sans/Mono Regular and Pixel Circle/Grid/Line statics")
    image.save(OUTPUT / "issue-23-outline-metrics.png", optimize=True)


def render_issue_23_outlines() -> None:
    image, draw = canvas(
        23,
        "OUTLINE HEURISTICS",
        "Characters flagged by alignment, jaggy, short-segment, contour, or overlap checks.",
        1900,
    )
    label = font(MONO_DIR / "NamcheShadowMono-Regular.ttf", 21)

    def specimen_row(
        y: int, style: str, sample: str, path: Path, size: int = 78
    ) -> None:
        draw.text((72, y + 30), style, font=label, fill=MUTED)
        draw.text((280, y), sample, font=fit(path, sample, 1240, size), fill=TEXT)

    section(draw, 340, "Sans · rounded/source heuristics")
    specimen_row(405, "THIN", "M a Ư Ẫ ฿ в Ç", SANS_DIR / "NamcheShadowSans-Thin.ttf")
    specimen_row(535, "REGULAR", "M a Ư Ẫ ฿ в Ç", SANS_DIR / "NamcheShadowSans-Regular.ttf")
    specimen_row(665, "BLACK", "M a Ư Ẫ ฿ в Ç", SANS_DIR / "NamcheShadowSans-Black.ttf")

    section(draw, 820, "Mono · inherited outline heuristics")
    specimen_row(885, "THIN", "M W G Ư Ŋ f m", MONO_DIR / "NamcheShadowMono-Thin.ttf")
    specimen_row(1015, "REGULAR", "M W G Ư Ŋ f m", MONO_DIR / "NamcheShadowMono-Regular.ttf")
    specimen_row(1145, "BLACK", "M W G Ư Ŋ f m", MONO_DIR / "NamcheShadowMono-Black.ttf")

    section(draw, 1300, "Pixel · grid and component heuristics")
    specimen_row(1365, "CIRCLE", "ą ő ű æ ﬁ ﬂ", PIXEL_DIR / "NamcheShadowPixel-Circle.ttf", 70)
    specimen_row(1495, "GRID", "ą ő ű æ ﬁ ﬂ", PIXEL_DIR / "NamcheShadowPixel-Grid.ttf", 70)
    specimen_row(1625, "LINE", "ą ő ű æ ﬁ ﬂ", PIXEL_DIR / "NamcheShadowPixel-Line.ttf", 70)

    footer(
        draw,
        image.height,
        "Representative flagged glyphs · visual baseline only; no bulk outline changes",
    )
    image.save(OUTPUT / "issue-23-outline-heuristics.png", optimize=True)


def render_issue_24() -> None:
    image, draw = canvas(
        24,
        "OPENTYPE VENDOR ID",
        "The four-byte OS/2 identifier is consistent in the current Namche binaries.",
        950,
    )
    rows = [
        ("SANS", SANS_DIR / "NamcheShadowSans-Regular.ttf"),
        ("MONO", MONO_DIR / "NamcheShadowMono-Regular.ttf"),
        ("PIXEL", PIXEL_DIR / "NamcheShadowPixel-Circle.ttf"),
    ]
    label = font(MONO_DIR / "NamcheShadowMono-Regular.ttf", 24)
    for index, (family, path) in enumerate(rows):
        ttfont = TTFont(path, lazy=True)
        vendor = ttfont["OS/2"].achVendID
        ttfont.close()
        y = 365 + index * 155
        draw.text((72, y + 46), family, font=label, fill=MUTED)
        draw.text((310, y), vendor, font=fit(path, vendor, 700, 112), fill=TEXT)
        draw.text((1080, y + 46), "UNREGISTERED", font=label, fill=RED)
    footer(draw, image.height, "OS/2.achVendID · registration remains an administrative follow-up")
    image.save(OUTPUT / "issue-24-vendor-id.png", optimize=True)


def render_issue_25() -> None:
    image, draw = canvas(
        25,
        "PIXEL METADATA",
        "Every product style now carries the same Namche vendor and Latin language declarations.",
        1170,
    )
    label = font(MONO_DIR / "NamcheShadowMono-Regular.ttf", 21)
    styles = ["Circle", "Grid", "Line", "Square", "Triangle"]
    for index, style in enumerate(styles):
        path = PIXEL_DIR / f"NamcheShadowPixel-{style}.ttf"
        ttfont = TTFont(path, lazy=True)
        vendor = ttfont["OS/2"].achVendID
        language = ttfont["meta"].data
        ttfont.close()
        y = 350 + index * 145
        draw.text((72, y + 38), style.upper(), font=label, fill=MUTED)
        draw.text((320, y), "Aa 0123", font=font(path, 72), fill=TEXT)
        draw.rounded_rectangle((835, y + 10, 1005, y + 72), 14, fill=BLUE)
        draw.rounded_rectangle((1025, y + 10, 1205, y + 72), 14, fill=YELLOW)
        draw.rounded_rectangle((1225, y + 10, 1485, y + 72), 14, fill=PURPLE)
        draw.text((875, y + 27), vendor, font=label, fill=TEXT)
        draw.text((1060, y + 27), f"dlng {language.get('dlng')}", font=label, fill=TEXT)
        draw.text((1265, y + 27), f"slng {language.get('slng')}", font=label, fill=TEXT)
    footer(draw, image.height, "Pixel TTF statics · OS/2 and meta tables")
    image.save(OUTPUT / "issue-25-pixel-metadata.png", optimize=True)


def render_issue_32() -> None:
    image, draw = canvas(
        32,
        "INVISIBLE SEPARATORS",
        "The two encoded glyphs have a 600-unit advance and deliberately contain no ink.",
        1320,
    )
    label = font(MONO_DIR / "NamcheShadowMono-Regular.ttf", 20)
    headings = ((0x2028, "LINE SEPARATOR"), (0x2029, "PARAGRAPH SEPARATOR"))
    for column, (codepoint, title) in enumerate(headings):
        x = 310 + column * 620
        draw.text((x, 350), f"U+{codepoint:04X}  {title}", font=label, fill=MUTED)

    for row, style in enumerate(("Circle", "Grid", "Line", "Square", "Triangle")):
        path = PIXEL_DIR / f"NamcheShadowPixel-{style}.ttf"
        ttfont = TTFont(path, recalcTimestamp=False)
        cmap = ttfont.getBestCmap() or {}
        y = 415 + row * 155
        draw.text((72, y + 48), style.upper(), font=label, fill=MUTED)
        for column, (codepoint, _) in enumerate(headings):
            glyph_name = cmap[codepoint]
            width, left_sidebearing = ttfont["hmtx"][glyph_name]
            pen = BoundsPen(ttfont.getGlyphSet())
            ttfont.getGlyphSet()[glyph_name].draw(pen)
            x = 310 + column * 620
            draw.rounded_rectangle((x, y, x + 520, y + 112), 14, outline=BLUE, width=4)
            draw.line((x + 20, y + 78, x + 500, y + 78), fill=LINE, width=2)
            draw.text((x + 24, y + 18), glyph_name, font=label, fill=TEXT)
            status = f"advance {width} · lsb {left_sidebearing} · {'NO INK' if pen.bounds is None else 'HAS INK'}"
            draw.text((x + 24, y + 82), status, font=label, fill=GREEN if pen.bounds is None else RED)
        ttfont.close()

    draw.text(
        (72, 1210),
        "The blue frames visualize each otherwise invisible character cell.",
        font=label,
        fill=MUTED,
    )
    footer(draw, image.height, "All five Namche Shadow Pixel TTF statics · U+2028 / U+2029")
    image.save(OUTPUT / "issue-32-pixel-separators.png", optimize=True)


def render_issue_33() -> None:
    image, draw = canvas(
        33,
        "MONO HORIZONTAL METRICS",
        "Current hmtx values are minimal without changing glyph order or mark advances.",
        1450,
    )
    label = font(MONO_DIR / "NamcheShadowMono-Regular.ttf", 21)
    regular = MONO_DIR / "NamcheShadowMono-Regular.ttf"
    italic = MONO_DIR / "NamcheShadowMono-Italic.ttf"

    def metric_summary(path: Path) -> tuple[int, int, int, int]:
        ttfont = TTFont(path, recalcTimestamp=False)
        order = ttfont.getGlyphOrder()
        widths = [ttfont["hmtx"][name][0] for name in order]
        result = (
            ttfont["hmtx"][".notdef"][0],
            widths.count(0),
            widths.count(600),
            ttfont["hhea"].numberOfHMetrics,
        )
        ttfont.close()
        return result

    section(draw, 340, "Rendered advances remain intentional")
    draw.text((72, 410), "UPRIGHT", font=label, fill=MUTED)
    draw.text((300, 385), "M W i m 0   á í į̌", font=font(regular, 78), fill=TEXT)
    draw.text((72, 535), "ITALIC", font=label, fill=MUTED)
    draw.text((300, 510), "M W i m 0   á í į̌", font=font(italic, 78), fill=TEXT)

    section(draw, 670, "Why the compact value cannot be 3")
    rows = (("UPRIGHT", metric_summary(regular)), ("ITALIC", metric_summary(italic)))
    for index, (style, metrics) in enumerate(rows):
        notdef_width, mark_count, common_count, current = metrics
        y = 745 + index * 175
        draw.text((72, y + 42), style, font=label, fill=MUTED)
        draw.rounded_rectangle((280, y, 520, y + 105), 14, fill=YELLOW)
        draw.rounded_rectangle((540, y, 840, y + 105), 14, fill=PURPLE)
        draw.rounded_rectangle((860, y, 1180, y + 105), 14, fill=BLUE)
        draw.text((315, y + 39), f".notdef {notdef_width}", font=label, fill=TEXT)
        draw.text((580, y + 39), f"{mark_count} marks × 0", font=label, fill=TEXT)
        draw.text((900, y + 39), f"{common_count} × 600", font=label, fill=TEXT)
        draw.text((1240, y + 25), str(current), font=font(regular, 46), fill=GREEN)
        draw.text((1240, y + 78), "MIN", font=label, fill=MUTED)

    section(draw, 1110, "Decision", GREEN)
    decision = "3 would change mark advances. 41 requires glyph reorder and still warns."
    draw.text((72, 1180), decision, font=fit(regular, decision, 1456, 42), fill=TEXT)
    draw.text(
        (72, 1260),
        "Retain the exact metrics, outlines, shaping, and glyph order; classify the WARN.",
        font=label,
        fill=MUTED,
    )
    footer(draw, image.height, "Mono Regular + Italic TTF · hhea.numberOfHMetrics / hmtx")
    image.save(OUTPUT / "issue-33-mono-hmetrics.png", optimize=True)


def render_issue_34() -> None:
    image, draw = canvas(
        34,
        "INDIAN RUPEE",
        "One Geist-inspired construction, expressed through all five Pixel element shapes.",
        1440,
    )
    label = font(MONO_DIR / "NamcheShadowMono-Regular.ttf", 20)
    styles = ("Square", "Circle", "Grid", "Triangle", "Line")
    section(draw, 340, "₹ · five element shapes · one 38-unit grid")
    for column, style in enumerate(styles):
        path = PIXEL_DIR / f"NamcheShadowPixel-{style}.ttf"
        x = 65 + column * 300
        draw.text((x, 405), "₹", font=font(path, 225), fill=TEXT)
        draw.text((x + 12, 690), style.upper(), font=label, fill=MUTED)

    section(draw, 785, "Currency and figure context")
    for row, style in enumerate(styles):
        path = PIXEL_DIR / f"NamcheShadowPixel-{style}.ttf"
        y = 855 + row * 92
        draw.text((72, y + 22), style.upper(), font=label, fill=MUTED)
        draw.text((300, y), "₹123   € $ £ ¥", font=font(path, 60), fill=TEXT)
        draw.text((1260, y + 22), "U+20B9", font=label, fill=GREEN)

    footer(
        draw,
        image.height,
        "Pixel TTF statics · Geist Sans rupee structure translated to 109 pixel components",
    )
    image.save(OUTPUT / "issue-34-pixel-rupee.png", optimize=True)


def render_issue_35() -> None:
    image, draw = canvas(
        35,
        "WWS FAMILY METADATA",
        "Public typographic names stay unchanged; every binary now carries spec-correct WWS metadata.",
        1320,
    )
    label = font(MONO_DIR / "NamcheShadowMono-Regular.ttf", 21)
    rows = [
        ("SANS REGULAR", SANS_DIR / "NamcheShadowSans-Regular.ttf", "Aa 0123"),
        ("SANS BOLD ITALIC", SANS_DIR / "NamcheShadowSans-BoldItalic.ttf", "Aa 0123"),
        ("MONO REGULAR", MONO_DIR / "NamcheShadowMono-Regular.ttf", "Aa 0123"),
        ("MONO BOLD ITALIC", MONO_DIR / "NamcheShadowMono-BoldItalic.ttf", "Aa 0123"),
        ("PIXEL CIRCLE", PIXEL_DIR / "NamcheShadowPixel-Circle.ttf", "Aa 0123"),
    ]
    for index, (title, path, sample) in enumerate(rows):
        ttfont = TTFont(path, lazy=True)
        family = ttfont["name"].getDebugName(16) or ttfont["name"].getDebugName(1) or ""
        style = ttfont["name"].getDebugName(17) or ttfont["name"].getDebugName(2) or ""
        wws = bool(ttfont["OS/2"].fsSelection & (1 << 8))
        wws_names = {record.nameID for record in ttfont["name"].names} & {21, 22}
        ttfont.close()
        y = 350 + index * 165
        draw.text((72, y + 44), title, font=label, fill=MUTED)
        draw.text((365, y), sample, font=font(path, 64), fill=TEXT)
        draw.text((750, y + 8), family, font=fit(path, family, 520, 34), fill=TEXT)
        draw.text((750, y + 61), style, font=fit(path, style, 520, 30), fill=MUTED)
        pixel = path.parent.parent.name == "NamcheShadowPixel"
        valid = (not wws and wws_names == {21, 22}) if pixel else (wws and not wws_names)
        status = "NAMES 21/22 · BIT 8 CLEAR" if pixel else "BIT 8 · NAMES 21/22 ABSENT"
        draw.text((1240, y + 42), status if valid else "INVALID WWS", font=label, fill=GREEN if valid else RED)
    footer(draw, image.height, "Representative Sans, Mono, and Pixel TTF statics · OS/2 + name")
    image.save(OUTPUT / "issue-35-wws-metadata.png", optimize=True)


def render_issue_37() -> None:
    image, draw = canvas(
        37,
        "PIXEL LIGATURE CARETS",
        "The green insertion line follows the source caret_1 anchor inside both ligatures.",
        1320,
    )
    label = font(MONO_DIR / "NamcheShadowMono-Regular.ttf", 21)
    for row, style in enumerate(("Circle", "Grid", "Line", "Square", "Triangle")):
        path = PIXEL_DIR / f"NamcheShadowPixel-{style}.ttf"
        ttfont = TTFont(path, lazy=True)
        caret_list = ttfont["GDEF"].table.LigCaretList
        values = {}
        for glyph_name in ("fi", "fl"):
            index = caret_list.Coverage.glyphs.index(glyph_name)
            values[glyph_name] = caret_list.LigGlyph[index].CaretValue[0].Coordinate
        advance = ttfont["hmtx"].metrics["fi"][0]
        units_per_em = ttfont["head"].unitsPerEm
        ttfont.close()

        y = 350 + row * 170
        draw.text((72, y + 65), style.upper(), font=label, fill=MUTED)
        specimen = font(path, 150)
        scale = 150 / units_per_em
        for column, (glyph, glyph_name) in enumerate((("ﬁ", "fi"), ("ﬂ", "fl"))):
            x = 340 + column * 310
            draw.text((x, y), glyph, font=specimen, fill=TEXT)
            caret_x = round(x + values[glyph_name] * scale)
            draw.line((caret_x, y + 10, caret_x, y + 145), fill=GREEN, width=4)
            draw.text(
                (x + 145, y + 66),
                f"{glyph_name}  {values[glyph_name]} / {advance}",
                font=label,
                fill=GREEN,
            )
        draw.text((1240, y + 65), "GDEF", font=label, fill=GREEN)

    footer(
        draw,
        image.height,
        "All five Namche Shadow Pixel TTF statics · GDEF LigCaretList",
    )
    image.save(OUTPUT / "issue-37-pixel-ligature-carets.png", optimize=True)


def render_issue_36() -> None:
    image, draw = canvas(
        36,
        "PIXEL MARK SHAPING",
        "The dotted circle receives every mark; į loses its base dot before top marks.",
        1370,
    )
    label = font(MONO_DIR / "NamcheShadowMono-Regular.ttf", 20)
    draw.text((270, 350), "DOTTED CIRCLE", font=label, fill=MUTED)
    draw.text((650, 350), "REQUIRED", font=label, fill=MUTED)
    draw.text((1110, 350), "OPTIONAL", font=label, fill=MUTED)
    for row, style in enumerate(("Circle", "Grid", "Line", "Square", "Triangle")):
        path = PIXEL_DIR / f"NamcheShadowPixel-{style}.ttf"
        y = 405 + row * 175
        draw.text((72, y + 50), style.upper(), font=label, fill=MUTED)
        draw.text((270, y), "◌́ ◌̧ ◌̨", font=font(path, 80), fill=TEXT)
        draw.text((650, y + 9), "į́ į̌ į̀ į̃ į̄ į̂", font=font(path, 62), fill=TEXT)
        draw.text((1110, y + 14), "į̆ į̈ į̊ į̒ į̋ į̇", font=font(path, 54), fill=TEXT)
        draw.text((1510, y + 48), "PASS", font=label, fill=GREEN, anchor="ra")

    footer(
        draw,
        image.height,
        "All five Namche Shadow Pixel TTF statics · U+25CC + ccmp/mark/mkmk",
    )
    image.save(OUTPUT / "issue-36-pixel-shaping.png", optimize=True)


SANS_WEIGHTS = (
    "Thin",
    "ExtraLight",
    "Light",
    "Regular",
    "Medium",
    "SemiBold",
    "Bold",
    "ExtraBold",
    "Black",
)


def sans_static(weight: str, italic: bool) -> Path:
    if not italic:
        return SANS_DIR / f"NamcheShadowSans-{weight}.ttf"
    if weight == "Regular":
        return SANS_DIR / "NamcheShadowSans-Italic.ttf"
    return SANS_DIR / f"NamcheShadowSans-{weight}Italic.ttf"


def contour_count(font_file: Path, glyph_name: str) -> int:
    ttfont = TTFont(font_file, lazy=True)
    try:
        glyph_set = ttfont.getGlyphSet()
        pen = DecomposingRecordingPen(glyph_set)
        glyph_set[glyph_name].draw(pen)
        return sum(1 for operator, _ in pen.value if operator == "moveTo")
    finally:
        ttfont.close()


def render_issue_78() -> None:
    image, draw = canvas(
        78,
        "ITALIC A COUNTER",
        "Every italic weight carries the A counter as its own contour, rounded like the upright.",
        1230,
    )
    label = font(MONO_DIR / "NamcheShadowMono-Regular.ttf", 19)

    section(draw, 340, "Sans italic · A · nine statics · 2 contours each")
    for column, weight in enumerate(SANS_WEIGHTS):
        path = sans_static(weight, italic=True)
        x = 78 + column * 162
        draw.text((x, 400), "A", font=font(path, 150), fill=TEXT)
        draw.text((x, 570), weight.upper(), font=label, fill=MUTED)
        contours = contour_count(path, "A")
        draw.text(
            (x, 598),
            f"{contours} CONTOURS",
            font=label,
            fill=GREEN if contours == 2 else RED,
        )

    section(draw, 665, "Upright reference · unchanged")
    for column, weight in enumerate(SANS_WEIGHTS):
        path = sans_static(weight, italic=False)
        x = 78 + column * 162
        draw.text((x, 725), "A", font=font(path, 150), fill=TEXT)
        draw.text((x, 895), weight.upper(), font=label, fill=MUTED)

    section(draw, 950, "Specimen line that first exposed the collapsed counter")
    draw.text(
        (72, 1010),
        "A change of pace",
        font=font(sans_static("Medium", italic=True), 78),
        fill=TEXT,
    )

    footer(
        draw,
        image.height,
        "fonts/NamcheShadowSans/ttf · glyph A · scripts/check_sans_counters.py",
    )
    image.save(OUTPUT / "issue-78-italic-a-counter.png", optimize=True)


def main() -> None:
    if not features.check_feature("raqm"):
        raise SystemExit(
            "Pillow must be built with RAQM support to render reliable shaping proofs."
        )
    OUTPUT.mkdir(parents=True, exist_ok=True)
    render_issue_20()
    render_issue_21()
    render_issue_22()
    render_issue_23()
    render_issue_23_outlines()
    render_issue_24()
    render_issue_25()
    render_issue_32()
    render_issue_33()
    render_issue_34()
    render_issue_35()
    render_issue_36()
    render_issue_37()
    render_issue_78()
    for path in sorted(OUTPUT.glob("issue-*.png")):
        print(f"Wrote {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
