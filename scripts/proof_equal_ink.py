#!/usr/bin/env python3
"""Render paired release snapshots, without changing fonts or review decisions.

Produces 18 complete Sans repertoire overview PNGs (one per static style), a targeted
six-style detail PNG, an intermediate-VF panel, and a JSON manifest tying every image to input hashes.
"""
from __future__ import annotations

import argparse
from functools import lru_cache
import hashlib
import json
import math
from pathlib import Path
import unicodedata

from fontTools.ttLib import TTFont
from PIL import Image, ImageDraw, ImageFont

try:
    from .latin_core import SANS_CODEPOINTS as CODEPOINTS
except ImportError:
    from latin_core import SANS_CODEPOINTS as CODEPOINTS

WEIGHTS = ('Thin', 'ExtraLight', 'Light', 'Regular', 'Medium', 'SemiBold',
           'Bold', 'ExtraBold', 'Black')
STYLES = tuple(style for weight in WEIGHTS for style in
               (weight, 'Italic' if weight == 'Regular' else weight+'Italic'))
DETAIL_STYLES = ('Thin', 'Regular', 'Black', 'ThinItalic', 'Italic', 'BlackItalic')
DETAIL_CHARS = ('H', 'E', 'a', 'K', 'n', 'A', 'y', '&', '#', '$', '€', '4', '©', '®', None)
INK = '#151c18'
BEFORE = '#6c5650'
AFTER = '#235e46'
LINE = '#d6ddd8'


def font_path(root: Path, style: str) -> Path:
    name = f'NamcheShadowSans-{style}.ttf'
    candidates = (root/'ttf'/name, root/'NamcheShadowSans/ttf'/name)
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(f'Missing static TTF: {candidates[0]}')


@lru_cache(maxsize=64)
def face(path: str, size: int):
    return ImageFont.truetype(path, size, layout_engine=ImageFont.Layout.RAQM
                              if ImageFont.core.HAVE_RAQM else ImageFont.Layout.BASIC)


def label_font(root: Path, size: int):
    # Labels use the before Regular face, so they need no system font download.
    return face(str(font_path(root, 'Regular')), size)


def sample(character: str | None) -> str:
    if character is None:
        return '\uffff'  # Deliberately unmapped: the selected font's glyph zero.
    return 'n'+character if unicodedata.combining(character) else character


def pair(draw, box, character, before_font, after_font, labels):
    x, y, width, height = box
    text = sample(character)
    title = '.notdef (glyph 0)' if character is None else f'U+{ord(character):04X}'
    draw.text((x+8, y+5), title, font=labels, fill=INK)
    first_baseline = y+28+before_font.size
    second_baseline = y+height-20
    draw.text((x+8, first_baseline), 'B', font=labels, fill=BEFORE, anchor='ls')
    draw.text((x+8, second_baseline), 'A', font=labels, fill=AFTER, anchor='ls')
    # Equal pixel size, fixed baseline and fixed origin for BOTH snapshots.
    # Do not fit each outline to its bounds: that would conceal shape/spacing
    # differences. Columns have deliberately generous space for broad glyphs.
    draw.text((x+30, first_baseline), text, font=before_font, fill=INK, anchor='ls')
    draw.text((x+30, second_baseline), text, font=after_font, fill=INK, anchor='ls')
    draw.line((x, y+height, x+width, y+height), fill=LINE)
    draw.line((x+width, y, x+width, y+height), fill=LINE)


def heading(draw, title, subtitle, label):
    draw.text((24, 14), title, font=label, fill=INK)
    draw.text((24, 51), subtitle, font=label, fill=INK)
    draw.text((24, 87), 'B = before   A = after   •   Same pixel size and baseline; marks shown on n.',
              font=label, fill=INK)


def make_overview(before, after, style, output):
    chars = [chr(cp) for cp in sorted(CODEPOINTS)]
    columns, cell_w, cell_h, header = 16, 130, 192, 140
    image = Image.new('RGB', (columns*cell_w+48,
                              math.ceil(len(chars)/columns)*cell_h+header+24), 'white')
    draw = ImageDraw.Draw(image)
    heading(draw, f'Namche Shadow Sans • {style} • all {len(chars)} encoded characters',
            'Issue #125 review proof • no automatic design approval', label_font(before, 24))
    for index, character in enumerate(chars):
        pair(draw, (24+(index%columns)*cell_w, header+(index//columns)*cell_h,
                    cell_w, cell_h), character, face(str(font_path(before, style)), 62),
             face(str(font_path(after, style)), 62), label_font(before, 15))
    image.save(output)
    return {'file': output.name, 'style': style, 'characters': len(chars),
            'sample_pixels': 62, 'width': image.width, 'height': image.height}


def make_details(before, after, output):
    cell_w, cell_h, header, gutter = 210, 224, 176, 120
    image = Image.new('RGB', (gutter+len(DETAIL_STYLES)*cell_w+24,
                              len(DETAIL_CHARS)*cell_h+header+24), 'white')
    draw = ImageDraw.Draw(image)
    heading(draw, 'Namche Shadow Sans • targeted before / after',
            'Issue #125 • joins, italic slant, counters and compound islands', label_font(before, 22))
    for index, style in enumerate(DETAIL_STYLES):
        x = gutter+index*cell_w
        draw.text((x+8, 140), style, font=label_font(before, 19), fill=INK)
        for row, character in enumerate(DETAIL_CHARS):
            y = header+row*cell_h
            if index == 0:
                draw.text((16, y+48), character or '.notdef', font=label_font(before, 24), fill=INK)
            pair(draw, (x, y, cell_w, cell_h), character,
                 face(str(font_path(before, style)), 78),
                 face(str(font_path(after, style)), 78), label_font(before, 15))
    image.save(output)
    return {'file': output.name, 'styles': DETAIL_STYLES, 'sample_pixels': 78,
            'characters': [character or '.notdef' for character in DETAIL_CHARS],
            'width': image.width, 'height': image.height}


def make_intermediates(before, after, output):
    """Inspect the VF shapes whose non-master fingerprints are pinned in QA."""
    image = Image.new('RGB', (1800, 1600), 'white')
    draw = ImageDraw.Draw(image)
    inputs = {}
    weights = list(range(150, 900, 100))
    for column, suffix in enumerate(('', '-Italic')):
        filename = f'NamcheShadowSans{suffix}[wght].ttf'
        candidates = (after/'variable'/filename, after/'NamcheShadowSans/variable'/filename)
        path = next((p for p in candidates if p.is_file()), None)
        if path is None:
            raise FileNotFoundError(f'Missing candidate VF: {filename}')
        inputs[filename] = hashlib.sha256(path.read_bytes()).hexdigest()
        for row, weight in enumerate(weights):
            variable = ImageFont.truetype(str(path), 105)
            variable.set_variation_by_axes([weight])
            x, y = 30+column*900, 25+row*195
            draw.text((x, y), f'{"Italic" if suffix else "Upright"} wght {weight}',
                      font=label_font(before, 24), fill=INK)
            draw.text((x, y+50), 'ª & @ % " B { }', font=variable, fill=INK)
    image.save(output)
    return {'file':output.name, 'weights':weights, 'sample_pixels':105,
            'candidate_variable_sha256':inputs}


def generate(before: Path, after: Path, output: Path):
    if output.resolve() in (before.resolve(), after.resolve()):
        raise ValueError('Proof output must be separate from font inputs')
    inputs = {}
    for snapshot, root in (('before', before), ('after', after)):
        inputs[snapshot] = {}
        for style in STYLES:
            path = font_path(root, style)
            with TTFont(path) as font:
                cmap = font.getBestCmap()
                if set(cmap) != CODEPOINTS:
                    raise ValueError(f'{path}: expected exact Sans character repertoire')
                if 0xffff in cmap or font.getGlyphOrder()[0] != '.notdef':
                    raise ValueError(f'{path}: cannot prove glyph zero with unmapped U+FFFF')
            inputs[snapshot][style] = {'path': str(path.resolve()),
                                      'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
    output.mkdir(parents=True, exist_ok=True)
    manifest = {'description': 'Before/after visual evidence; no automatic approval',
                'inputs': inputs, 'overviews': [], 'details': None}
    for index, style in enumerate(STYLES, 1):
        target = output/f'{index:02d}-{style}.png'
        manifest['overviews'].append(make_overview(before, after, style, target))
    manifest['details'] = make_details(before, after, output/'00-targeted.png')
    manifest['intermediates'] = make_intermediates(before, after, output/'19-intermediate-vfs.png')
    (output/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--before', required=True, type=Path, help='Release root with ttf/, or fonts root')
    parser.add_argument('--after', required=True, type=Path, help='Candidate release root with ttf/, or fonts root')
    parser.add_argument('--output', required=True, type=Path, help='Directory for PNGs and provenance manifest')
    args = parser.parse_args(argv)
    result = generate(args.before, args.after, args.output)
    print(f"Generated {len(result['overviews'])} full-character pages and targeted/static-variable detail pages in {args.output}")


if __name__ == '__main__':
    main()
