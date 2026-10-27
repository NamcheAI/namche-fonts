"""The pinned public character contract for all Namche families (not Geist)."""
from pathlib import Path
from fontTools.subset import Options, Subsetter
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parents[1]
CHARSET = ROOT / 'sources/charsets/GF_Latin_Core.nam'
CODEPOINTS = frozenset(int(line.split()[0], 16) for line in CHARSET.read_text().splitlines()
                      if line.startswith('0x'))


def normalize_info(info, keep):
    """Retain filter order/radii, restricting only their named glyph lists."""
    if isinstance(info, dict):
        if 'customParameters' in info:
            parameters = []
            for parameter in info['customParameters']:
                if parameter.get('name') == 'Remove Glyphs':
                    continue
                if parameter.get('name') == 'meta Table':
                    for value in parameter['value']:
                        if value.get('tag') in ('slng', 'dlng'):
                            value['data'] = 'Latn'
                value = parameter.get('value')
                if parameter.get('name') == 'Filter' and isinstance(value, str):
                    for marker in ('include:', 'exclude:'):
                        if marker in value:
                            before, names = value.split(marker, 1)
                            retained = [n.strip() for n in names.split(',') if n.strip() in keep]
                            if marker == 'include:' and not retained:
                                break
                            parameter['value'] = before + marker + ','.join(retained)
                    else:
                        parameters.append(parameter)
                        continue
                    # An empty include tier must never become a global filter.
                    continue
                parameters.append(parameter)
            info['customParameters'] = parameters
        for value in info.values():
            normalize_info(value, keep)
    elif isinstance(info, list):
        for value in info:
            normalize_info(value, keep)


def restrict_font(font):
    missing = CODEPOINTS - set(font.getBestCmap())
    if missing:
        raise ValueError(f'Missing Latin Core characters: {sorted(missing)}')
    options = Options()
    options.layout_features = ['*']
    options.name_IDs = ['*']
    options.name_languages = ['*']
    options.name_legacy = True
    options.notdef_outline = True
    options.glyph_names = True
    options.harfbuzz_repacker = False
    options.recalc_timestamp = False
    options.no_subset_tables += ['meta']
    subsetter = Subsetter(options=options)
    subsetter.populate(unicodes=CODEPOINTS)
    subsetter.subset(font)
    if 'meta' in font:
        font['meta'].data['dlng'] = 'Latn'
        font['meta'].data['slng'] = 'Latn'
    if set(font.getBestCmap()) != CODEPOINTS:
        raise ValueError('Subsetting did not produce exactly GF Latin Core')
    return font


def restrict_file(path):
    font = TTFont(path, recalcTimestamp=False)
    restrict_font(font)
    font.save(path, reorderTables=False)
    font.close()


def check_file(path):
    with TTFont(path) as font:
        actual = set(font.getBestCmap())
        if actual != CODEPOINTS:
            raise ValueError(f'{path}: missing={sorted(CODEPOINTS-actual)}, extra={sorted(actual-CODEPOINTS)}')


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('paths', nargs='+', type=Path)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    count = 0
    for root in args.paths:
        for path in ([root] if root.is_file() else sorted(root.rglob('*'))):
            if path.suffix in ('.ttf', '.otf', '.woff2') and 'subsets' not in path.parts:
                (check_file if args.check else restrict_file)(path)
                count += 1
    print(f'{"Checked" if args.check else "Restricted"} {count} fonts to {len(CODEPOINTS)} GF Latin Core characters')
