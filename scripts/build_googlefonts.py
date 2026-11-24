#!/usr/bin/env python3
"""Build reproducible production and Google Fonts candidate ZIPs from text sources."""
from __future__ import annotations
import argparse
from hashlib import sha256
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED
from fontTools.ttLib import TTFont
from build_sans_open import ROOT, SOURCE, ITALIC_SOURCE, build
from latin_core import check_file

CONFIG = ROOT / 'sources/googlefonts'
REPOSITORY = 'https://github.com/NamcheAI/namche-fonts'


def rename_font(source: Path, target: Path, family: str) -> dict:
    """Change names only; verify every other table against the source bytes."""
    font = TTFont(source, recalcTimestamp=False)
    old = 'Namche Shadow Sans'
    compact = family.replace(' ', '')
    for record in font['name'].names:
        value = record.toUnicode().replace(old, family).replace('NamcheShadowSans', compact)
        record.string = value.encode(record.getEncoding())
    for instance in font['fvar'].instances:
        style = font['name'].getDebugName(instance.subfamilyNameID)
        if len(f'{family} {style}') > 32:
            raise ValueError(f'Family and instance exceed 32 characters: {family} {style}')
    font.save(target, reorderTables=False)
    candidate = TTFont(target, recalcTimestamp=False)
    original = TTFont(source, recalcTimestamp=False)
    if set(candidate.reader.keys()) != set(original.reader.keys()):
        raise ValueError('Submission rename changed the table inventory')
    for tag in original.reader.keys():
        if tag == 'name':
            continue
        before, after = original.reader[tag], candidate.reader[tag]
        if tag == 'head':  # Only checkSumAdjustment may differ.
            before, after = before[:8] + before[12:], after[:8] + after[12:]
        if before != after:
            raise ValueError(f'Submission rename modified protected table {tag}')
    return {key: candidate['name'].getDebugName(nid) for key, nid in
            [('post_script_name', 6), ('full_name', 4), ('copyright', 0)]}


def archive(tree: Path, target: Path) -> None:
    with ZipFile(target, 'w', compression=ZIP_DEFLATED, compresslevel=9) as output:
        for path in sorted(tree.rglob('*')):
            if not path.is_file():
                continue
            info = ZipInfo(path.relative_to(tree).as_posix(), (1980, 1, 1, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            info.create_system = 3
            output.writestr(info, path.read_bytes())


def build_package(output: Path, commit: str, config_dir: Path = CONFIG) -> None:
    if not re.fullmatch(r'[0-9a-f]{40}', commit):
        raise ValueError('An exact 40-character source commit is required')
    config = json.loads((config_dir / 'family.json').read_text())
    family = config['name']
    if not re.fullmatch(r'[A-Z][A-Za-z0-9]*(?: [A-Za-z0-9]+)*', family):
        raise ValueError('Family must use ASCII words separated by spaces')
    compact = family.replace(' ', '')
    # Build in scratch space: never read fonts/ or preserve stale package files.
    with tempfile.TemporaryDirectory(prefix='namche-submission-') as tmp:
        tmp = Path(tmp)
        production = tmp / 'production'
        staging = tmp / 'googlefonts'
        dest = staging / 'ofl' / compact.lower()
        dest.mkdir(parents=True)
        entries = []
        hashes = {}
        for source, italic in [(SOURCE, False), (ITALIC_SOURCE, True)]:
            manifest = json.loads((source / 'provenance.json').read_text())
            build(source, production)
            for relative, expected in manifest['outputs'].items():
                actual = sha256((production / relative).read_bytes()).hexdigest()
                if actual != expected:
                    raise ValueError(f'Production source drift: {relative}: {actual}')
                hashes[relative] = actual
            filename = f'{compact}{"-Italic" if italic else ""}[wght].ttf'
            source_font = production / next(p for p in manifest['outputs'] if p.endswith('.ttf'))
            names = rename_font(source_font, dest / filename, family)
            check_file(dest / filename)
            entries.append(dict(name=family, style='italic' if italic else 'normal',
                                weight=400, filename=filename, **names))
        license_text = (ROOT / 'OFL.txt').read_text()
        # Preserve both notices on the copyright line recognized by GF's template.
        lines = license_text.splitlines()
        notices = []
        while lines and lines[0].startswith('Copyright '):
            notices.append(lines.pop(0))
        (dest / 'OFL.txt').write_text('. '.join(notices) + '\n' + '\n'.join(lines) + '\n')
        shutil.copyfile(ROOT / 'OFL.txt', production / 'OFL.txt')
        shutil.copyfile(config_dir / 'DESCRIPTION.en_us.html', dest / 'DESCRIPTION.en_us.html')
        def quote(value):
            return json.dumps(value, ensure_ascii=False)
        metadata = [f'{k}: {quote(config[k])}' for k in ['name', 'designer', 'category', 'date_added']]
        metadata.append('license: "OFL"')
        for entry in entries:
            metadata.append('fonts {\n' + '\n'.join(
                f'  {k}: {v if isinstance(v, int) else quote(v)}' for k, v in entry.items()) + '\n}')
        metadata.extend(f'subsets: {quote(s)}' for s in config['subsets'])
        metadata.extend(['axes { tag: "wght" min_value: 100.0 max_value: 900.0 }',
                         f'primary_script: {quote(config["primary_script"])}', 'stroke: "SANS_SERIF"'])
        mappings = {f'out/googlefonts/ofl/{compact.lower()}/{p.name}': p.name
                    for p in sorted(dest.iterdir())}
        metadata.append('source {\n  repository_url: ' + quote(REPOSITORY) + '\n  commit: ' + quote(commit))
        metadata.extend('  files { source_file: ' + quote(s) + ' dest_file: ' + quote(d) + ' }'
                        for s, d in mappings.items())
        metadata.append('}')
        (dest / 'METADATA.pb').write_text('\n'.join(metadata) + '\n')
        upstream = dict(repository_url=REPOSITORY, branch='main', files=mappings,
                        build='python3 -m venv /tmp/namche-gf-venv && /tmp/namche-gf-venv/bin/pip install -r requirements-open-build.txt && /tmp/namche-gf-venv/bin/python scripts/build_googlefonts.py')
        # JSON is a strict YAML subset, accepted by gftools' YAML reader.
        (dest / 'upstream.yaml').write_text(json.dumps(upstream, indent=2) + '\n')
        inputs = [ROOT / 'requirements-open-build.txt', ROOT / 'OFL.txt',
                  Path(__file__), ROOT / 'scripts/build_sans_open.py', ROOT / 'scripts/latin_core.py', ROOT / 'sources/charsets/GF_Latin_Core.nam']
        inputs += [p for directory in (SOURCE, ITALIC_SOURCE, config_dir)
                   for p in directory.rglob('*') if p.is_file()]
        report = {'source_commit': commit,
                  'source_sha256': {p.relative_to(ROOT).as_posix(): sha256(p.read_bytes()).hexdigest()
                                    for p in sorted(inputs)}, 'family': family, 'status': 'candidate, not accepted by Google Fonts',
                  'character_scope': 'GF Latin Core, 319 encoded characters; no candidate-only additions',
                  'production_sha256': hashes, 'submission_sha256': {
                      p.relative_to(staging).as_posix(): sha256(p.read_bytes()).hexdigest()
                      for p in sorted(dest.iterdir())}}
        (staging / 'BUILD.json').write_text(json.dumps(report, indent=2) + '\n')
        output.mkdir(parents=True, exist_ok=True)
        family_output = output / 'ofl' / compact.lower()
        if family_output.exists():
            shutil.rmtree(family_output)
        shutil.copytree(dest, family_output)
        shutil.copyfile(staging / 'BUILD.json', output / 'BUILD.json')
        archive(staging, output / 'namche-shadow-googlefonts.zip')
        archive(production, output / 'namche-shadow-open-fonts.zip')


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'out/googlefonts')
    parser.add_argument('--check', action='store_true', help='Compare two clean builds, including ZIP bytes')
    args = parser.parse_args()
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    build_package(args.output, commit)
    if args.check:
        with tempfile.TemporaryDirectory(prefix='namche-package-check-') as tmp:
            second = Path(tmp)
            build_package(second, commit)
            for name in ['namche-shadow-googlefonts.zip', 'namche-shadow-open-fonts.zip']:
                if (args.output / name).read_bytes() != (second / name).read_bytes():
                    raise ValueError(f'{name}: repeated builds differ')
                print(f'PASS reproducible {name}')


if __name__ == '__main__':
    main()
