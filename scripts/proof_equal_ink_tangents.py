"""Magnified comparisons of the compiled contours Michael identified in round four."""

from contextlib import ExitStack
import csv
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
import skia
from fontTools.ttLib import TTFont

try:
    from .check_equal_ink import VF_FILENAMES
    from .measure_lowercase_joins import CoveragePen, GEIST_VF, WEIGHTS, filled_areas
    from .measure_y_terminal import SegmentPen, fixed_font, measure as measure_y
    from .proof_equal_ink import INK, LINE, label_font
except ImportError:
    from check_equal_ink import VF_FILENAMES
    from measure_lowercase_joins import CoveragePen, GEIST_VF, WEIGHTS, filled_areas
    from measure_y_terminal import SegmentPen, fixed_font, measure as measure_y
    from proof_equal_ink import INK, LINE, label_font


def crop(font, char, center, scale):
    glyphs = font.getGlyphSet()
    pen = CoveragePen(glyphs)
    glyphs[font.getBestCmap()[ord(char)]].draw(pen)
    width, height = 300, 184
    surface = skia.Surface(width, height)
    canvas = surface.getCanvas()
    canvas.clear(skia.ColorWHITE)
    canvas.translate(width / 2 - scale * center[0], height / 2 + scale * center[1])
    canvas.scale(scale, -scale)
    canvas.drawPath(pen.path, skia.Paint(Color=skia.ColorBLACK, AntiAlias=True))
    return surface.makeImageSnapshot().toarray()[:, :, 0].copy()


def draw_triplet(image, old, new, top):
    x = 156
    for mask in (old, new):
        image.paste(Image.fromarray(mask).convert('RGB'), (x, top))
        x += 314
    # Common ink is pale so the colored edge differences remain visible.
    common = np.minimum(255 - old, 255 - new)
    amounts = np.stack((common, 255 - old - common, 255 - new - common), axis=-1)
    colors = np.array(((182, 183, 180), (176, 43, 97), (0, 115, 110)))
    delta = 255 - amounts @ (255 - colors) / 255
    image.paste(Image.fromarray(delta.round().astype('uint8')), (x, top))


def max_turn_in_crop(font, char, center, scale):
    glyphs = font.getGlyphSet()
    pen = SegmentPen(glyphs)
    glyphs[font.getBestCmap()[ord(char)]].draw(pen)
    angles = []
    for contour in pen.contours:
        for left, right in zip(contour, contour[1:] + contour[:1]):
            x, y = left[-1]
            if (len(left) < 3 or len(right) < 3 or (x, y) != right[0]
                    or abs(x - center[0]) > 150 / scale or abs(y - center[1]) > 92 / scale):
                continue
            # Repeated controls have zero derivative. Take the first distinct
            # coordinate on each side for the limiting tangent direction.
            a = next((p for p in reversed(left[:-1]) if p != (x, y)), None)
            b = next((p for p in right[1:] if p != (x, y)), None)
            if a is not None and b is not None:
                ax, ay = x - a[0], y - a[1]
                bx, by = b[0] - x, b[1] - y
                angles.append(math.degrees(math.atan2(abs(ax*by - ay*bx), ax*bx + ay*by)))
    if not angles:
        raise ValueError(f'No curve-to-curve join in the {char} proof crop')
    return max(angles)


def measure_ink(before, after, output):
    geist = Path(__file__).resolve().parents[1] / 'fonts/Geist/webfonts'
    with output.open('w', newline='') as stream:
        writer = csv.writer(stream, lineterminator='\n')
        writer.writerow(('slope', 'weight', 'before_added_ink', 'after_added_ink'))
        for slope, filename in VF_FILENAMES.items():
            with ExitStack() as stack:
                paths = (geist / GEIST_VF[slope], before / 'variable' / filename,
                         after / 'variable' / filename)
                fonts = [stack.enter_context(TTFont(path)) for path in paths]
                for weight in WEIGHTS:
                    base, old, new = (filled_areas(font, weight)['total'] for font in fonts)
                    writer.writerow((slope, weight, round(old - base, 2), round(new - base, 2)))


def sheet(before, after, slope, samples, title, scale, output, measurements):
    # Each entry can contain several glyphs at the same VF weight. Instantiate
    # once per row group and use identical crop coordinates for the two builds.
    rows = sum(len(chars) for weight, variable, chars in samples)
    image = Image.new('RGB', (1100, 135 + 196 * rows), 'white')
    draw = ImageDraw.Draw(image)
    draw.text((20, 14), title, font=label_font(before, 28), fill=INK)
    subtitle = f'{scale:g} pixels per font unit. Magenta shows removed ink, teal shows added ink.'
    draw.text((20, 56), subtitle, font=label_font(before, 18), fill=INK)
    for i, label in enumerate(('Previous review', 'Revision', 'Difference')):
        draw.text((156 + 314 * i, 92), label, font=label_font(before, 19), fill=INK)
    top = 132
    for weight, variable, chars in samples:
        fmt = 'variable' if variable else 'ttf'
        with fixed_font(before, fmt, weight, slope) as left, fixed_font(after, fmt, weight, slope) as right:
            for char, center in chars:
                draw.line((20, top - 5, 1084, top - 5), fill=LINE)
                draw.text((20, top + 34), f'{char}   {weight}', font=label_font(before, 24), fill=INK)
                draw.text((20, top + 70), 'VF instance' if variable else 'Static',
                          font=label_font(before, 16), fill=INK)
                draw_triplet(image, crop(left, char, center, scale), crop(right, char, center, scale), top)
                values = [max_turn_in_crop(font, char, center, scale) for font in (left, right)]
                measurements.append((slope, char, weight, 'frozen VF' if variable else 'static TTF',
                                     *(round(value, 4) for value in values)))
                top += 196
    image.save(output)


def tangent_panels(before, after, output):
    files, measurements = [], []
    # The joins migrate as the font gets heavier. The endpoints center the
    # crops on the reviewed build at 150 and 300, with room for the bowl.
    for slope, centers in (
            ('upright', (('b', (150, 476), (182, 497)), ('u', (420, 56), (399, 40)))),
            ('italic', (('b', (202, 485), (237, 507)), ('n', (187, 474), (217, 488)),
                        ('p', (191, 473), (221, 491))))):
        name = f'tangent-{slope}.png'
        samples = []
        for weight in (150, 200, 250, 300):
            fraction = (weight - 150) / 150
            chars = [(char, tuple(lo + fraction * (hi - lo) for lo, hi in zip(start, end)))
                     for char, start, end in centers]
            samples.append((weight, True, chars))
        sheet(before, after, slope, samples, f'{slope.capitalize()} · light lowercase joins',
              4., output / name, measurements)
        files.append(name)
    name = 'y-terminal.png'
    samples = [(w, variable, [('y', (126, -57 + (w - 400) * .12))])
               for w, variable in ((400, False), (400, True), (450, True),
                                   (500, False), (500, True))]
    sheet(before, after, 'italic', samples, 'Italic y · transition to the flat terminal',
          4., output / name, measurements)
    with (output / 'tangent-crops.csv').open('w', newline='') as stream:
        writer = csv.writer(stream, lineterminator='\n')
        writer.writerow(('slope', 'glyph', 'weight', 'format', 'before_max_turn_degrees',
                         'after_max_turn_degrees'))
        writer.writerows(measurements)
    measure_y(before, after, output / 'y-terminal.csv')
    measure_ink(before, after, output / 'lowercase-ink.csv')
    return [*files, name, 'tangent-crops.csv', 'y-terminal.csv', 'lowercase-ink.csv']
