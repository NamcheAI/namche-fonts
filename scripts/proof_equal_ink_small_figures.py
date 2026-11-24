#!/usr/bin/env python3
"""Proof and measure all four sets of small figures in the compiled release."""
import argparse
import csv
from hashlib import sha256
import json
from pathlib import Path
import sys

from PIL import Image, ImageChops, ImageDraw, features
from fontTools.pens.recordingPen import RecordingPen
from fontTools.ttLib import TTFont
import skia
import uharfbuzz as hb

ROOT = Path(__file__).resolve().parents[1]
if __package__ in ('', None):
    sys.path.insert(0, str(ROOT))

from scripts.check_equal_ink import VF_FILENAMES, WEIGHT_STYLES, _filled_geos, _geos_counters
from scripts.measure_lowercase_joins import CoveragePen, GEIST_VF
from scripts.proof_equal_ink import INK, LINE, label_font
from scripts.proof_equal_ink_review import SIZES, comparison_faces, rendering_rows, snapshot_paths, text_panel, write_rows

DIGITS = 'zero one two three four five six seven eight nine'.split()
ROLES = {
    'numerator': [name + '.numr' for name in DIGITS],
    'denominator': [name + '.dnom' for name in DIGITS],
    'superior': ['uni2070', 'uni00B9', 'uni00B2', 'uni00B3', *(f'uni207{i}' for i in range(4, 10))],
    'inferior': [f'uni208{i}' for i in range(10)],
}
REVIEWED = set().union(*ROLES.values())
WEIGHTS = tuple(range(100, 901, 25))
AREA_TOLERANCE = .01  # Max distance from each Bezier to its flattened chord, in font units.
FF = ('vf', 'static-ttf', 'static-otf')
PIN = '6ab84d8510fb87efd1ebe7e196c6d8983ef1e853'


def label(draw, x, y, text, root, size, **kw):
    draw.text((x, y), text, font=label_font(root, size), fill=INK, **kw)


def part_path(root, slope, fmt, w):
    if fmt == 'vf':
        return root / 'variable' / VF_FILENAMES[slope]
    ext = fmt.split('-')[1]
    style = WEIGHT_STYLES[w][int(slope == 'italic')]
    return root / ext / f'NamcheShadowSans-{style}.{ext}'


def outline_areas(glyphs, name):
    ink, _ = _filled_geos(glyphs, name, AREA_TOLERANCE)
    holes = sorted(_geos_counters(ink), key=lambda hole: hole.centroid.y)
    return [hole.area for hole in holes]


def rendered_strip(glyphs, names, size, origin, scale):
    surface = skia.Surface(*size)
    c = surface.getCanvas()
    c.clear(skia.ColorWHITE)
    c.translate(*origin)
    c.scale(scale, -scale)
    paint = skia.Paint(Color=skia.ColorBLACK, AntiAlias=True)
    for name in names:
        pen = CoveragePen(glyphs)
        glyphs[name].draw(pen)
        c.drawPath(pen.path, paint)
        c.translate(glyphs[name].width, 0)
    return Image.fromarray(surface.makeImageSnapshot().toarray()[:, :, 0]).convert('RGB')


def four_sheet(geist, before, after, root, slope, ratios, path):
    cell_w, cell_h, x0, y0 = 145, 230, 137, 148
    page = Image.new('RGB', (x0 + 9*cell_w + 22, y0 + 4*cell_h + 28), 'white')
    draw = ImageDraw.Draw(page)
    label(draw, 22, 13, f'Small 4 · {slope}', root, 31)
    label(draw, 22, 56, 'Variable outlines at a common scale. Percentages show triangular counter area relative to Geist.', root, 19)
    for i, w in enumerate((400, 700, 900)):
        x = x0 + 3*i*cell_w
        label(draw, x, 90, f'{WEIGHT_STYLES[w][0]}  {w}', root, 21)
        for j, lab in enumerate(('Geist', '6ab84d8', 'Revision')):
            label(draw, x + j*cell_w, 122, lab, root, 16)
        gs = [f.getGlyphSet(location={'wght': w}) for f in (geist, before, after)]
        for role_no, (role, names) in enumerate(ROLES.items()):
            name = names[4]
            top = y0 + role_no*cell_h
            if i == 0:
                label(draw, 16, top+12, role.capitalize(), root, 19)
                label(draw, 16, top+42, {'numerator': 'numr', 'denominator': 'dnom', 'superior': 'sups', 'inferior': 'subs / sinf'}[role], root, 16)
                draw.line((16, top, page.width-16, top), fill=LINE)
            # Each triplet uses Geist's bounds and the same 0.38 pixels per
            # unit, preserving optical shifts between snapshots without clipping.
            p = CoveragePen(gs[0])
            gs[0][name].draw(p)
            box = p.path.computeTightBounds()
            scale = .38
            origin = (cell_w/2 - scale*(box.left()+box.right())/2,
                      100 + scale*(box.top()+box.bottom())/2)
            for j, glyphs in enumerate(gs):
                col = x + j*cell_w
                page.paste(rendered_strip(glyphs, [name], (cell_w, 192), origin, scale), (col, top+1))
                ratio = (100., *ratios[slope, w, role])[j]
                label(draw, col+cell_w/2, top+202, f'{ratio:.2f}%', root, 18, anchor='mt')
    page.save(path)


def digits_sheet(font, root, slope, path):
    x0, y0, width, height, scale = 132, 126, 492, 144, .12
    page = Image.new('RGB', (x0 + 4*width + 16, y0 + 4*height + 18), 'white')
    draw = ImageDraw.Draw(page)
    label(draw, 20, 12, f'Small figures · {slope}', root, 31)
    label(draw, 20, 57, 'Release VF. Each row uses the same scale and baseline. The line marks the baseline of the normal figures.', root, 19)
    for i, w in enumerate((100, 400, 700, 900)):
        x = x0 + i*width
        label(draw, x, 94, f'{WEIGHT_STYLES[w][0]}  {w}', root, 21)
        glyphs = font.getGlyphSet(location={'wght': w})
        for j, (role, names) in enumerate(ROLES.items()):
            top = y0 + j*height
            baseline = 104
            tile = rendered_strip(glyphs, names, (width, height-2), (4, baseline), scale)
            guide = Image.new('RGB', tile.size, 'white')
            ImageDraw.Draw(guide).line((0, baseline, width-18, baseline), fill='#a4b8bd')
            page.paste(ImageChops.darker(tile, guide), (x, top))
            if i == 0:
                label(draw, 16, top+44, role.capitalize(), root, 19)
    page.save(path)


def feature_sample(font):
    """Shape activated feature runs with HarfBuzz/RAQM and rasterize at native size."""
    mask = Image.new('L', (148, 32), 0)
    draw = ImageDraw.Draw(mask)
    x = 2
    for value, tags in (('3/4  4/9', ['frac']), ('   x', []), ('4', ['sups']),
                        ('   x', []), ('4', ['subs'])):
        draw.text((x, 23), value, fill=255, font=font, anchor='ls', features=tags)
        x += draw.textlength(value, font=font, features=tags)
    if x >= mask.width or not mask.getbbox():
        raise ValueError('small-figure text sample is empty or outside its native-size cell')
    return mask


def feature_text_sheet(before, after, out):
    if not features.check('raqm'):
        raise RuntimeError('Feature-enabled text proofs require Pillow with RAQM')
    x0, y0, cell, row = 84, 150, 148, 38
    page = Image.new('RGB', (x0 + 8*cell + 8, y0 + 2*(6*row + 44) + 12), 'white')
    draw = ImageDraw.Draw(page)
    label(draw, 20, 12, 'Small figures at reading size', before, 31)
    label(draw, 20, 54, 'Native pixels. Each cell shows two fractions, a fourth power and a subscript. View at 100%.', before, 19)
    for j, label_text in enumerate(('6ab84d8 static', '6ab84d8 VF', 'Revision static', 'Revision VF')):
        label(draw, x0 + 2*j*cell, 91, label_text, before, 21)
        for k, weight in enumerate((400, 900)):
            label(draw, x0 + (2*j+k)*cell, 122, f'{WEIGHT_STYLES[weight][0]} {weight}', before, 16)
    measurements = []
    for i, slope in enumerate(VF_FILENAMES):
        top = y0 + i*(6*row + 44)
        draw.line((18, top+1, page.width-18, top+1), fill=LINE)
        label(draw, 18, top+7, slope.capitalize(), before, 20)
        for k, ppem in enumerate(SIZES):
            y = top+41+k*row
            label(draw, 18, y+2, f'{ppem} px', before, 17)
            for weight, styles in WEIGHT_STYLES.items():
                result = {'slope': slope, 'weight': weight, 'ppem': ppem}
                for rev, (key, root) in enumerate((('previous', before), ('candidate', after))):
                    faces = comparison_faces(snapshot_paths(root, slope, styles[i]), weight, ppem)
                    for j, (format_name, font) in enumerate(zip(('static', 'vf'), faces, strict=True)):
                        mask = feature_sample(font)
                        result[key+'_'+format_name] = sum(mask.tobytes())
                        if weight in (400, 900):
                            col = 4*rev + 2*j + int(weight == 900)
                            page.paste('black', (x0 + col*cell, y, x0 + (col+1)*cell, y+32), mask)
                    result[key+'_vf_vs_static_pct'] = round(100*(result[key+'_vf']/result[key+'_static']-1), 4)
                measurements.append(result)
    png, data = out/'small-figures-text.png', out/'small-figure-rendering.csv'
    page.save(png)
    write_rows(data, measurements)
    return png, data


def shape(font, face, text, features, weight):
    shaper = hb.Font(face)
    if 'fvar' in font:
        shaper.set_variations({'wght': weight})
    chars = hb.Buffer()
    chars.add_str(text)
    chars.guess_segment_properties()
    hb.shape(shaper, chars, features)
    return [(font.getGlyphName(i.codepoint), i.cluster, p.x_advance, p.y_advance, p.x_offset, p.y_offset)
            for i, p in zip(chars.glyph_infos, chars.glyph_positions, strict=True)]


def check_shaping(fonts, faces, w):
    cases = [
        ('0123456789', {}, DIGITS),
        ('0123456789', {'numr': True}, ROLES['numerator']),
        ('0123456789', {'dnom': True}, ROLES['denominator']),
        ('0123456789', {'sups': True}, ROLES['superior']),
        ('0123456789', {'subs': True}, ROLES['inferior']),
        ('0123456789', {'sinf': True}, ROLES['inferior']),
        ('0123456789/9876543210', {'frac': True}, ROLES['numerator'] + ['fraction'] + ROLES['denominator'][::-1]),
        ('4/4', {}, ['four', 'slash', 'four']),
    ]
    for text, features, expected in cases:
        shaped = [shape(f, face, text, features, w) for f, face in zip(fonts, faces, strict=True)]
        if shaped[0] != shaped[1] or [g[0] for g in shaped[1]] != expected:
            raise ValueError(f'shaping mismatch at {w}: {text} {features}: {shaped}')
    return len(cases)


def check_scope(fonts):
    old, new = fonts
    if old.getGlyphOrder() != new.getGlyphOrder():
        raise ValueError('glyph order changed')
    for tag in ('cmap', 'GDEF', 'GSUB', 'GPOS', 'kern', 'HVAR', 'MVAR', 'fvar', 'avar', 'STAT', 'name'):
        if (tag in old) != (tag in new) or (tag in old and old.getTableData(tag) != new.getTableData(tag)):
            raise ValueError(f'{new.reader.file.name}: {tag} changed')
    for name in old.getGlyphOrder():
        a, b = old['hmtx'][name], new['hmtx'][name]
        if a[0] != b[0] or (name not in REVIEWED and a != b):
            raise ValueError(f'{name}: horizontal metrics changed')
    if 'glyf' in old:
        a, b = old['glyf'], new['glyf']
        changed = {n for n in old.getGlyphOrder() if a[n].compile(a) != b[n].compile(b)}
        if 'gvar' in old:
            old_vars, new_vars = old['gvar'].variations, new['gvar'].variations
            changed.update(n for n in old.getGlyphOrder() if old_vars.get(n) != new_vars.get(n))
    else:
        changed = set()
        sets = [f.getGlyphSet() for f in fonts]
        for name in old.getGlyphOrder():
            pens = [RecordingPen(), RecordingPen()]
            for gs, pen in zip(sets, pens, strict=True):
                gs[name].draw(pen)
            if pens[0].value != pens[1].value:
                changed.add(name)
    if unexpected := changed - REVIEWED:
        raise ValueError(f'outlines changed outside the 40 small figures: {sorted(unexpected)}')
    return sorted(changed)


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def generate(geist_dir, before, after, out):
    out.mkdir(parents=True, exist_ok=True)
    manifests = {'baseline_commit': PIN, 'geist_package': 'geist@1.7.2', 'vf_weights': WEIGHTS,
                 'static_weights': sorted(WEIGHT_STYLES), 'flatten_tolerance_font_units': AREA_TOLERANCE,
                 'inputs': {}, 'changed_glyphs': {}, 'shaping_cases_checked': 0,
                 'small_figure_observations': 0, 'enclosed_counters_checked': 0}
    rows, ratios, files, rendering = [], {}, [], []
    for slope in VF_FILENAMES:
        gp = geist_dir / GEIST_VF[slope]
        manifests['inputs']['geist/' + gp.name] = digest(gp)
        with TTFont(gp) as geist:
            index = int(slope == 'italic')
            target = out / f'text-{slope}.png'
            text_panel(before, after, slope, index, target)
            files.append(target)
            for w, styles in WEIGHT_STYLES.items():
                paths = {label: snapshot_paths(root, slope, styles[index])
                         for label, root in (('before', before), ('after', after))}
                rendering.extend(rendering_rows(paths, slope, w))
            geist_areas = {}
            for w in WEIGHTS:
                gs = geist.getGlyphSet(location={'wght': w})
                geist_areas[w] = {name: outline_areas(gs, name) for name in REVIEWED}
            for fmt in FF:
                for fw in ((400,) if fmt == 'vf' else WEIGHT_STYLES):
                    paths = [part_path(r, slope, fmt, fw) for r in (before, after)]
                    for p, rev in zip(paths, ('previous', 'candidate'), strict=True):
                        manifests['inputs'][f'{rev}/{p.parent.name}/{p.name}'] = digest(p)
                    with TTFont(paths[0]) as old, TTFont(paths[1]) as new:
                        fonts = (old, new)
                        if any(f['head'].unitsPerEm != 1000 for f in (geist, *fonts)):
                            raise ValueError('expected one shared 1000-unit em')
                        key = f'{paths[0].parent.name}/{paths[0].name}'
                        manifests['changed_glyphs'][key] = check_scope(fonts)
                        faces = [hb.Face(p.read_bytes()) for p in paths]
                        for w in (WEIGHTS if fmt == 'vf' else (fw,)):
                            manifests['shaping_cases_checked'] += check_shaping(fonts, faces, w)
                            sets = [f.getGlyphSet(location={'wght': w} if fmt == 'vf' else None) for f in fonts]
                            for role, names in ROLES.items():
                                for digit, name in enumerate(names):
                                    ref = geist_areas[w][name]
                                    prior, candidate = (outline_areas(gs, name) for gs in sets)
                                    if len(ref) != len(prior) or len(ref) != len(candidate):
                                        raise ValueError(f'counter count mismatch: {slope} {fmt} {w} {name}')
                                    manifests['small_figure_observations'] += 1
                                    manifests['enclosed_counters_checked'] += len(ref)
                                    metrics = zip(ref, prior, candidate, strict=True)
                                    for i, (a, b, c) in enumerate(metrics):
                                        rows.append((slope, fmt, w, role, digit, name, len(ref), i+1,
                                                     round(a, 3), round(b, 3), round(c, 3),
                                                     round(100*b/a, 4), round(100*c/a, 4)))
                                        if digit == 4 and fmt == 'vf':
                                            ratios[slope, w, role] = (100*b/a, 100*c/a)
                                    if not ref:
                                        rows.append((slope, fmt, w, role, digit, name, 0, '', '', '', '', '', ''))
                        if fmt == 'vf':
                            target = out / f'small-four-{slope}.png'
                            four_sheet(geist, old, new, before, slope, ratios, target)
                            files.append(target)
                            target = out / f'small-digits-{slope}.png'
                            digits_sheet(new, before, slope, target)
                            files.append(target)
    csv_path = out / 'small-figure-counters.csv'
    with csv_path.open('w', newline='') as stream:
        writer = csv.writer(stream, lineterminator='\n')
        writer.writerow(('slope', 'format', 'weight', 'role', 'digit', 'glyph', 'counter_count',
                         'counter_bottom_to_top', 'geist_area', 'previous_area', 'candidate_area',
                         'previous_pct_of_geist', 'candidate_pct_of_geist'))
        writer.writerows(rows)
    files.append(csv_path)
    text_data = out / 'rendering.csv'
    write_rows(text_data, rendering)
    files.append(text_data)
    files.extend(feature_text_sheet(before, after, out))
    manifests['feature_text'] = {'features': ['frac', 'sups', 'subs'], 'sample': '3/4  4/9   x⁴   x₄',
                                 'freetype': features.version('freetype2'), 'raqm': features.version('raqm')}
    manifests['outputs'] = {p.name: digest(p) for p in files}
    (out / 'small-figure-manifest.json').write_text(json.dumps(manifests, indent=2, sort_keys=True)+'\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--geist', type=Path, default=ROOT/'fonts/Geist/webfonts')
    parser.add_argument('--before', type=Path, required=True)
    parser.add_argument('--after', type=Path, default=ROOT/'fonts/NamcheShadowSans')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    generate(args.geist, args.before, args.after, args.output)
