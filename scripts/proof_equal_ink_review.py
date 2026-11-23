#!/usr/bin/env python3
"""Render the compiled issue #125 revisions and measure VF darkness at text sizes."""

from __future__ import annotations

import argparse
import csv
from hashlib import sha256
import json
from pathlib import Path

import PIL
import numpy as np
import pathops
from PIL import Image, ImageDraw, ImageFont, features
from fontTools.ttLib import TTFont

try:
    from .check_equal_ink import WEIGHT_STYLES, VF_FILENAMES, _counter_contours, _filled_path
    from .proof_equal_ink import CODEPOINTS, INK, LINE, face, label_font, sample
except ImportError:
    from check_equal_ink import WEIGHT_STYLES, VF_FILENAMES, _counter_contours, _filled_path
    from proof_equal_ink import CODEPOINTS, INK, LINE, face, label_font, sample


SAMPLE = (
    'The rounded inner corners give the sans a printed, slightly soft texture.',
    'A shaded room by the old quay in Vienna costs €45.',
)
LATIN_CORE_LINE = ' '.join(sample(chr(cp)) for cp in sorted(CODEPOINTS))
DETAIL_LINES = (
    (80, 'y ý ÿ ŷ ỳ    A 4 #'),
    (80, 'a b d h m n p q r u'),
    (54, 'H E K Y   & # $ €   ¢ Œ Q'),
)
DETAIL_WEIGHTS = (100, 200, 300, 400, 700, 900)
SIZES = range(11, 17)


def snapshot_paths(root, slope, style):
    return (root / 'ttf' / f'NamcheShadowSans-{style}.ttf',
            root / 'variable' / VF_FILENAMES[slope])


def comparison_faces(paths, weight, size):
    static_path, vf_path = paths
    static = face(str(static_path), size)
    variable = ImageFont.truetype(vf_path, size, layout_engine=static.layout_engine)
    variable.set_variation_by_axes([weight])
    return static, variable


def coverage(font, lines):
    # A tightly bounded mask includes the complete shaped line and its overhangs.
    # Summing its bytes is independent of the extent of the surrounding white.
    return sum(sum(bytes(font.getmask(line, mode='L'))) for line in lines)


def pct_change(before, after):
    return round(100 * (after / before - 1), 4)


def proof_canvas(before, title, subtitle, size, columns):
    image = Image.new('RGB', size, 'white')
    draw = ImageDraw.Draw(image)
    draw.text((24, 16), title, font=label_font(before, 31), fill=INK)
    draw.text((24, 64), subtitle, font=label_font(before, 19), fill=INK)
    for x, text in columns:
        draw.text((x, 115), text, font=label_font(before, 20), fill=INK)
    draw.line((24, 153, size[0] - 24, 153), fill=LINE)
    return image, draw


def outline_panel(before, after, slope, index, output):
    columns = ((132, 'Previous PR'), (868, 'Revision'))
    image, draw = proof_canvas(
        before, f'Namche Shadow Sans · {slope.capitalize()}',
        'Arm and descender, lowercase joins, counters and crossings. Matched static TTFs.',
        (1600, 160 + len(DETAIL_WEIGHTS) * 283), columns)
    for row, weight in enumerate(DETAIL_WEIGHTS):
        y = 165 + row * 283
        draw.text((24, y + 32), str(weight), font=label_font(before, 24), fill=INK)
        style = WEIGHT_STYLES[weight][index]
        for (x, _), root in zip(columns, (before, after)):
            static_path, _ = snapshot_paths(root, slope, style)
            for (size, line), shift in zip(DETAIL_LINES, (72, 170, 247)):
                draw.text((x, y + shift), line, font=face(str(static_path), size),
                          anchor='ls', fill=INK)
        draw.line((24, y + 272, image.width - 24, y + 272), fill=LINE)
    image.save(output)


def text_panel(before, after, slope, index, output):
    columns = ((132, 'Previous PR'), (790, 'Revision'))
    image, draw = proof_canvas(
        before, f'Regular 400 · {slope.capitalize()}',
        'FreeType grayscale at native pixel size. View the PNG at 100%.',
        (1460, 175 + len(SIZES) * 135), columns)
    style = WEIGHT_STYLES[400][index]
    for row, size in enumerate(SIZES):
        y = 161 + row * 135
        draw.text((24, y + 15), f'{size} px', font=label_font(before, 21), fill=INK)
        for (x, _), root in zip(columns, (before, after)):
            fonts = comparison_faces(snapshot_paths(root, slope, style), 400, size)
            for k, (name, font) in enumerate(zip(('Static', 'VF'), fonts)):
                baseline = y + 27 + k * 58
                draw.text((x, baseline), name, font=label_font(before, 15), anchor='ls', fill=INK)
                for n, line in enumerate(SAMPLE):
                    draw.text((x + 57, baseline + n * 22), line, font=font, anchor='ls', fill='black')
        draw.line((24, y + 123, image.width - 24, y + 123), fill=LINE)
    image.save(output)


def overlay_panel(before, after, output):
    samples = (('y', 0), ('y', 1), ('a', 0), ('a', 1), ('n', 1), ('4', 0), ('A', 1))
    weights = (100, 400, 700, 900)
    colors = np.array([(59, 66, 66), (175, 53, 102), (0, 129, 124)])
    columns = [(118 + 260 * i, f'{char} · {("Upright", "Italic")[index]}')
               for i, (char, index) in enumerate(samples)]
    image, draw = proof_canvas(
        before, 'Changes to the compiled contours',
        'Gray is shared. Magenta shows removed ink and teal shows added ink.',
        (130 + 260 * len(samples), 158 + 285 * len(weights)), columns)
    for row, weight in enumerate(weights):
        top = 158 + row * 285
        draw.text((24, top + 76), str(weight), font=label_font(before, 23), fill=INK)
        for (x, _), (char, index) in zip(columns, samples):
            style = WEIGHT_STYLES[weight][index]
            fonts = [face(str(root / 'ttf' / f'NamcheShadowSans-{style}.ttf'), 260)
                     for root in (before, after)]
            # Fix the baseline and match the origins even when widths or ink bounds differ.
            left, _, right, _ = fonts[0].getbbox(char, anchor='ls')
            origin = ((246 - right - left) // 2, 221)
            masks = []
            for font in fonts:
                mask = Image.new('L', (246, 280))
                ImageDraw.Draw(mask).text(origin, char, font=font, anchor='ls', fill=255)
                masks.append(np.asarray(mask))
            prior, revised = masks
            common = np.minimum(prior, revised)
            coverage_masks = np.stack((common, prior - common, revised - common), axis=2)
            rgb = 255 - (coverage_masks @ (255 - colors)) / 255
            image.paste(Image.fromarray(rgb.round().astype('uint8')), (x, top))
        draw.line((24, top + 282, image.width - 24, top + 282), fill=LINE)
    image.save(output)


def rendering_rows(paths, slope, weight):
    for size in SIZES:
        row = {'slope': slope, 'weight': weight, 'ppem': size}
        for name, pair in paths.items():
            static, variable = comparison_faces(pair, weight, size)
            static_ink, vf_ink = coverage(static, SAMPLE), coverage(variable, SAMPLE)
            row.update({f'{name}_static': static_ink, f'{name}_vf': vf_ink,
                        f'{name}_vf_vs_static_pct': pct_change(static_ink, vf_ink)})
            core_static = coverage(static, [LATIN_CORE_LINE])
            core_vf = coverage(variable, [LATIN_CORE_LINE])
            row[f'{name}_latin_core_vf_vs_static_pct'] = pct_change(core_static, core_vf)
        yield row


def counter_rows(paths, slope, weight):
    rows = {c: {'slope': slope, 'weight': weight, 'glyph': c} for c in 'A4#'}
    for snapshot, (static_path, _) in paths.items():
        with TTFont(static_path) as font:
            glyphs, cmap = font.getGlyphSet(), font.getBestCmap()
            for char, row in rows.items():
                counters = _counter_contours(_filled_path(glyphs, cmap[ord(char)]))
                if len(counters) != 1:
                    raise ValueError(f'{static_path.name} {char}: expected one counter, got {len(counters)}')
                row[snapshot] = round(abs(counters[0].area), 3)
    for row in rows.values():
        row['change_pct'] = pct_change(row['before'], row['after'])
        if 'pre_pr' in row:
            row['vs_pre_pr_pct'] = pct_change(row['pre_pr'], row['after'])
        yield row


def y_geometry(font, location=None):
    glyphs, cmap = font.getGlyphSet(location=location), font.getBestCmap()
    if set(cmap) != CODEPOINTS:
        raise ValueError('The proof requires exactly the 319 Latin Core characters')
    y = _filled_path(glyphs, cmap[ord('y')])
    main, = y.contours  # A second contour here could be the prototype's white hole.
    longest_step = 0
    previous = None
    for command, points in main.segments:
        if command == 'lineTo':
            x, level = points[-1]
            # The former ledge crosses this box in both slopes at all weights.
            if (previous and abs(previous[1] - level) < .01 and 0 <= level <= 55
                    and 120 <= min(previous[0], x) <= 300):
                longest_step = max(longest_step, abs(previous[0] - x))
        if points:
            previous = points[-1]
    max_difference = 0
    for char in 'ýÿŷỳ':
        accented = _filled_path(glyphs, cmap[ord(char)])
        base, = [contour for contour in accented.contours if contour.bounds[1] < 0]
        max_difference = max(max_difference, pathops.op(y, base, pathops.PathOp.XOR).area)
    return longest_step, max_difference


def y_sweep(root, slope, index):
    results = []
    for weight, styles in WEIGHT_STYLES.items():
        path, _ = snapshot_paths(root, slope, styles[index])
        with TTFont(path) as font:
            results.append(y_geometry(font))
    with TTFont(root / 'variable' / VF_FILENAMES[slope]) as font:
        for weight in range(100, 901, 25):
            results.append(y_geometry(font, {'wght': weight}))
    steps, differences = zip(*results)
    return {'static_instances': 9, 'vf_instances': 33,
            'min_horizontal_step_units': min(steps), 'max_horizontal_step_units': max(steps),
            'max_accented_base_xor_square_units': max(differences)}


def write_rows(path, rows):
    with path.open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=rows[0], lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)


def generate(before, after, output, counter_reference=None):
    output.mkdir(parents=True, exist_ok=True)
    rendering, counters = [], []
    files = {}
    inputs = {'before': {}, 'after': {}}
    y_checks = {'before': {}, 'after': {}}
    overlay = output / 'changes.png'
    overlay_panel(before, after, overlay)
    files[overlay.name] = sha256(overlay.read_bytes()).hexdigest()
    for index, slope in enumerate(('upright', 'italic')):
        for name, root in (('before', before), ('after', after)):
            y_checks[name][slope] = y_sweep(root, slope, index)
        for kind, renderer in (('outlines', outline_panel), ('text', text_panel)):
            path = output / f'{kind}-{slope}.png'
            renderer(before, after, slope, index, path)
            files[path.name] = sha256(path.read_bytes()).hexdigest()
        for weight, styles in WEIGHT_STYLES.items():
            paths = {}
            for name, root in (('before', before), ('after', after)):
                pair = snapshot_paths(root, slope, styles[index])
                paths[name] = pair
                for path in pair:
                    if path.name not in inputs[name]:
                        inputs[name][path.name] = sha256(path.read_bytes()).hexdigest()
            rendering.extend(rendering_rows(paths, slope, weight))
            if weight >= 700:
                if counter_reference:
                    reference = snapshot_paths(counter_reference, slope, styles[index])
                    paths['pre_pr'] = reference
                    inputs.setdefault('counter_reference', {})[reference[0].name] = sha256(
                        reference[0].read_bytes()).hexdigest()
                counters.extend(counter_rows(paths, slope, weight))
    for filename, rows in (('rendering.csv', rendering), ('counters.csv', counters)):
        target = output / filename
        write_rows(target, rows)
        files[filename] = sha256(target.read_bytes()).hexdigest()
    manifest = {
        'inputs_sha256': inputs, 'proofs_sha256': files, 'text': SAMPLE,
        'pillow': PIL.__version__, 'freetype': features.version_module('freetype2'),
        'layout_engine': label_font(before, 15).layout_engine.name,
        'raqm': features.version_feature('raqm'),
        'harfbuzz': features.version_feature('harfbuzz'),
        'rendering': 'Sum of 8-bit grayscale glyph coverage on both complete shaped lines. '
                     'Each percentage is 100 × (VF / static − 1) within the same snapshot, style, '
                     'weight and integer ppem. Positive values indicate a darker VF. '
                     'The latin_core columns repeat the comparison on all 319 characters in '
                     'codepoint order, space-separated, with combining marks shown on n.',
        'counters': 'Enclosed counter area in square font units, from unioned static TTF outlines.',
        'y_geometry': y_checks,
        'y_method': 'Maximum horizontal line length in the former ledge region '
                    '(left endpoint x 120–300, y 0–55) on the unioned default y. '
                    'Check the default contour against the descender-reaching contour of '
                    'ý ÿ ŷ ỳ at every named static weight and every 25 VF weight units.',
        'overlay': 'Matched static glyphs rendered at 260 ppem on the same baseline and '
                   'origin in both snapshots. Color shows the difference in grayscale coverage.',
        'outlines': {'weights': DETAIL_WEIGHTS, 'samples': DETAIL_LINES},
    }
    (output / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--before', required=True, type=Path, help='Previous Sans family root with ttf/ and variable/')
    parser.add_argument('--after', required=True, type=Path, help='Revised Sans family root with ttf/ and variable/')
    parser.add_argument('--counter-reference', type=Path,
                        help='Optional pre-PR Sans family root for the original heavy counter comparison')
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    generate(args.before, args.after, args.output, args.counter_reference)
