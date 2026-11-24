#!/usr/bin/env python3
"""Shape the issue #135 language samples at all named weights and between every pair of source masters."""
import argparse
from pathlib import Path

import uharfbuzz as hb


# Words from specimen_16 and the two affected poster samples in the language data used by Fontspector
# 1.9.0 (google-fonts-languages 0.7.11). Preserve its combining sequences.
SAMPLES = {
    'amr': "ko̱nigti opudo̱mey",
    'ote': 'mu̱i ra zoo',
    'sey': 'ko̱kaijë',
    'kek': 'juntaqʼeet wankil',
    'yap': 'mattʼawen',
    'yua': 'chíimpoltaʼal',
    'tsz': 'kueraaŋasondikso',
    'cic': 'Nanna mó̱maka̱',  # poster_md
    'snn': "Sia'bai̱",  # poster_lg
}
MARK = '\u0331'


def shape(font, text, language, features=None):
    buffer = hb.Buffer()
    buffer.add_str(text)
    buffer.guess_segment_properties()
    buffer.language = language
    hb.shape(font, buffer, features)
    return list(zip(buffer.glyph_infos, buffer.glyph_positions, strict=True))


def check(font_path):
    face = hb.Face(font_path.read_bytes())
    if not any(a.tag == 'wght' and a.min_value == 100 and a.max_value == 900 for a in face.axis_infos):
        raise ValueError(f'{font_path}: expected a 100–900 variable weight axis')
    font = hb.Font(face)
    mark = font.get_nominal_glyph(ord(MARK))
    for weight in range(100, 901, 25):
        font.set_variations({'wght': weight})
        label = f'{font_path.name} weight {weight}'
        for char in ('Ŋ', 'ŋ', 'ʼ', MARK):
            glyph = font.get_nominal_glyph(ord(char))
            box = None if glyph is None else font.get_glyph_extents(glyph)
            if box is None or not box.width or not box.height:
                raise ValueError(f'{label}: empty or absent {char!r}')
            advance = font.get_glyph_h_advance(glyph)
            if (char == MARK and advance != 0) or (char != MARK and advance <= 0):
                raise ValueError(f'{label}: unexpected advance {advance} for {char!r}')
        for language, text in SAMPLES.items():
            run = shape(font, text, language)
            if any(info.codepoint == 0 for info, _ in run):
                raise ValueError(f'{label}: missing glyph in {language} {text!r}')
            positions = [pos for info, pos in run if info.codepoint == mark]
            if len(positions) != text.count(MARK) or any(pos.x_advance or pos.y_advance for pos in positions):
                raise ValueError(f'{label}: missing or spacing mark in {language} {text!r}')
            if positions and sum(pos.x_advance for _, pos in run) != sum(
                    pos.x_advance for _, pos in shape(font, text.replace(MARK, ''), language)):
                raise ValueError(f'{label}: mark changed advance of {text!r}')
        for base in 'aoeiuŊŋ':
            stack = base + MARK * 2
            enabled = shape(font, stack, 'amr')
            disabled = shape(font, stack, 'amr', {'mark': False, 'mkmk': False})
            positions = [p for info, p in enabled if info.codepoint == mark]
            if len(positions) != 2 or positions[0].x_offset == disabled[1][1].x_offset:
                raise ValueError(f'{label}: missing base attachment in {stack!r}')
            without_stacking = shape(font, stack, 'amr', {'mkmk': False})
            if positions[1].y_offset == without_stacking[-1][1].y_offset:
                raise ValueError(f'{label}: missing mark-to-mark positioning in {stack!r}')
            extent = font.get_glyph_extents(mark)
            lower_top = positions[1].y_offset + extent.y_bearing
            upper_bottom = positions[0].y_offset + extent.y_bearing + extent.height
            if lower_top >= upper_bottom:
                raise ValueError(f'{label}: stacked marks overlap in {stack!r}')
    print(f'PASS {font_path.name}: {len(SAMPLES)} language excerpts and below-mark stacking at 33 weights')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('fonts', nargs='+', type=Path)
    for path in parser.parse_args().fonts:
        check(path)
