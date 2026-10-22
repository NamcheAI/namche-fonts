#!/usr/bin/env python3
"""Reproduce intake evidence from the exact subset/language crates in Fontspector 1.9.0.

Download the pinned crates separately; archive hashes are verified before reading. No fonts or metadata are edited.
"""
import argparse
import ast
from hashlib import sha256
import json
from pathlib import Path
import re
import tarfile
import unicodedata
from fontTools.ttLib import TTFont

COMMON = {0x0000, 0x000D, 0x0020, 0x002D, 0x00A0, 0x25CC, 0x200C, 0x200D, 0x0964, 0x0965}
SUBSETS = ('cyrillic', 'cyrillic-ext', 'latin', 'latin-ext', 'vietnamese')
CRATES = {
    'subsets': ('google-fonts-subsets', '0.202602.1', '597758334cd2e74730da9e4c6d970f9d6b32bdb6823b1f9c2272720615f12252'),
    'languages': ('google-fonts-languages', '0.7.11', 'a8066b43e3021c9ba25242b7e2fa57a9f1d1f77fa8ae43936f6946512a3f2376'),
}


def codes(values):
    return [f'U+{cp:04X}' for cp in sorted(values)]


def field(text, name):
    match = re.search(r'^\s*' + name + r': ("(?:[^"\\]|\\.)*")', text, re.M)
    return ast.literal_eval(match[1]) if match else ''


def run(subsets_archive, languages_archive, family):
    inputs = {}
    archives = {'subsets': subsets_archive, 'languages': languages_archive}
    for key, path in archives.items():
        if sha256(path.read_bytes()).hexdigest() != CRATES[key][2]:
            raise ValueError(f'{key}: archive does not match the Fontspector 1.9.0 lock')

    def read(key, relative, label):
        name, version, _ = CRATES[key]
        with tarfile.open(archives[key], 'r:gz') as archive:
            member = archive.extractfile(f'{name}-{version}/{relative}')
            if member is None:
                raise ValueError(f'Missing data file: {relative}')
            data = member.read()
        inputs[label] = sha256(data).hexdigest()
        return data.decode('utf-8')

    subsets = {}
    for name in SUBSETS:
        text = read('subsets', f'Lib/gfsubsets/data/{name}_unique-glyphs.nam', name)
        subsets[name] = {int(line.split()[0], 16) for line in text.splitlines() if line.startswith('0x')}
    languages = {}
    for name in ('ale', 'amr', 'ote', 'sey'):
        identifier = f'{name}_Latn'
        text = read('languages', f'Lib/gflanguages/data/languages/{identifier}.textproto', identifier)
        languages[identifier] = {key: field(text, key) for key in ('name', 'base', 'marks', 'specimen_16')}
    results = {}
    for path in sorted(family.glob('*.ttf')):
        with TTFont(path) as font:
            cp = set(font.getBestCmap())
        support = {}
        for name, subset in subsets.items():
            relevant = subset - COMMON
            other = set().union(*(s for n, s in subsets.items() if n != name))
            support[name] = {'covered': len(cp & relevant), 'total': len(relevant),
                             'percent': round(100 * len(cp & relevant) / len(relevant), 4),
                             'lost_if_removed': codes((cp & subset) - other)}
        language_results = {}
        served = cp & set().union(*subsets.values())
        for name, data in languages.items():
            bases = {ord(c) for c in data['base'] if not c.isspace() and c not in '{}'}
            sample = {ord(c) for c in unicodedata.normalize('NFC', data['specimen_16'].replace('\n', ''))}
            language_results[name] = {
                'name': data['name'], 'base_exemplars_covered': bases <= cp,
                'marks_exemplar': data['marks'], 'sample_missing_in_font': codes(sample - cp),
                'present_but_outside_declared_subsets': codes((sample & cp) - served),
                'sample_u0331_occurrences': data['specimen_16'].count('\u0331'),
            }
        results[path.name] = {'sha256': sha256(path.read_bytes()).hexdigest(),
                              'U+0302_present': 0x302 in cp, 'U+0331_present': 0x331 in cp,
                              'subset_coverage': support, 'languages': language_results}
    if len(results) != 2:
        raise ValueError('Expected exactly two candidate VFs')
    return {'fontspector': '1.9.0', 'fontspector_commit': 'd9d0f7b0b2f158b6950df61be97d3ccff3e1f7e8',
            'data_sources': {key: {'crate': name, 'version': version, 'archive_sha256': digest,
                                  'download': f'https://crates.io/api/v1/crates/{name}/{version}/download'}
                             for key, (name, version, digest) in CRATES.items()},
            'input_sha256': inputs, 'fonts': results,
            'scope': 'Pinned checker-data coverage, not proof of future Google Fonts serving or language acceptance.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--subsets', type=Path, required=True)
    parser.add_argument('--languages', type=Path, required=True)
    parser.add_argument('--family', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(json.dumps(run(args.subsets, args.languages, args.family), ensure_ascii=False, indent=2) + '\n')
