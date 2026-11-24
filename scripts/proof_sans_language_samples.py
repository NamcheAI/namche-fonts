#!/usr/bin/env python3
"""Render the issue #135 language proof from the built Google Fonts package."""
import argparse
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, features

from check_sans_language_samples import SAMPLES

LANGUAGES = {
    'amr': 'Amarakaeri', 'ote': 'Mezquital Otomi', 'sey': 'Secoya',
    'kek': 'Qʼeqchiʼ', 'yap': 'Yapese', 'yua': 'Yucateco',
    'tsz': 'Purepecha', 'cic': 'Chickasaw', 'snn': 'Siona',
}


@lru_cache
def face(path, size, weight):
    font = ImageFont.truetype(path, size, layout_engine=ImageFont.Layout.RAQM)
    font.set_variation_by_axes([weight])
    return font


def proof(family, output):
    if not features.check('raqm'):
        raise RuntimeError('This proof requires Pillow with RAQM for HarfBuzz shaping')
    upright = family / 'NamcheShadow[wght].ttf'
    italic = family / 'NamcheShadow-Italic[wght].ttf'
    columns = [(287, upright), (709, italic)]
    end_samples = 165 + 46 * len(SAMPLES)
    image = Image.new('RGB', (1170, end_samples + 358), '#faf9f5')
    draw = ImageDraw.Draw(image)
    ink, secondary, line = '#191c22', '#535b64', '#c9cbc4'

    def label(x, y, text, size=16, weight=400):
        draw.text((x, y), text, font=face(upright, size, weight),
                  anchor='la', fill=secondary if size <= 14 else ink)

    def specimen(x, baseline, text, path, size, weight, language='en'):
        draw.text((x, baseline), text, font=face(path, size, weight),
                  anchor='ls', language=language, fill=ink)

    label(36, 22, 'Namche Shadow', 38, 700)
    label(36, 77, 'Google Fonts language specimens', 21)
    label(36, 124, 'LANGUAGE', 13, 700)
    for (x, _), heading in zip(columns, ('UPRIGHT  ·  400', 'ITALIC  ·  400')):
        label(x, 124, heading, 13, 700)
    draw.line((36, 149, 1134, 149), fill=line)
    for row, (language, text) in enumerate(SAMPLES.items()):
        baseline = 191 + row * 46
        label(36, baseline - 16, LANGUAGES[language])
        for x, path in columns:
            specimen(x, baseline, text, path, 34, 400, language)

    draw.line((36, end_samples, 1134, end_samples), fill=line)
    label(36, end_samples + 20, 'Weight and mark stacking', 19, 700)
    for row, weight in enumerate((100, 400, 900)):
        baseline = end_samples + 80 + row * 43
        label(36, baseline - 16, str(weight))
        for x, path in columns:
            specimen(x, baseline, 'NŊ nŋ    ʼ    o̱   o̱̱    u̱   u̱̱', path, 31, weight)

    draw.line((36, end_samples + 185, 1134, end_samples + 185), fill=line)
    label(36, end_samples + 203, 'Native pixel sizes', 19, 700)
    for index, size in enumerate(range(11, 17)):
        x = 36 + index * 184
        label(x, end_samples + 248, f'{size} px', 14, 700)
        for row, path in enumerate((upright, italic)):
            specimen(x, end_samples + 288 + 26 * row, 'ko̱nigti   xloqʼal   ŋ', path, size, 400)
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output, optimize=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--family', type=Path, default=Path('out/googlefonts/ofl/namcheshadow'))
    parser.add_argument('--output', type=Path, default=Path('documentation/proofs/issues/issue-135-language-samples.png'))
    args = parser.parse_args()
    proof(args.family, args.output)
