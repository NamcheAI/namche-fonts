#!/usr/bin/env python3
"""Bake issue #125's compatible corner rule and compile review fonts.

Clean outlines are explicit design inputs, never inferred from rounded output.
The maintained Glyphs packages supply naming, metrics, components and layout.
"""
from __future__ import annotations
import argparse
import copy
import uuid
import math
import json
from hashlib import sha256
import shutil
import os
from pathlib import Path
import subprocess
import sys
import unicodedata
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from glyphsLib import GSFont, GSNode, GSPath
from scripts.write_glyphspackage import save_package
from scripts.equal_ink_corners import round_compatible_contours, r90_for_stem, resolve_clean_contours, resolve_compatible_clean_contours

BASE = ROOT / 'sources/equal-ink/clean-outlines.json'
NODE_TYPES = {'line': 'l', 'curve': 'c', 'offcurve': 'o'}
REVERSE_TYPES = {v:k for k,v in NODE_TYPES.items()}


def contours(layer):
    return [[(float(n.position.x), float(n.position.y), NODE_TYPES[n.type])
             for n in p.nodes] for p in layer.paths]


def signature(paths):
    return [[p[2] for p in c] for c in paths]


def set_paths(layer, paths):
    # Components and their attachment metadata remain untouched.
    layer.paths = []
    for contour in paths:
        p = GSPath()
        p.closed = True
        p.nodes = [GSNode((round(x, 6), round(y, 6)), REVERSE_TYPES[t]) for x,y,t in contour]
        layer.paths.append(p)


def canonicalize_component_transforms(font):
    """Match Glyphs 3 component precision before using transforms for interpolation.

    GlyphsLib serializes component scale and position vectors to three decimals
    and component angles to five. If the first build interpolates higher
    precision transforms and then saves a package, a later build would
    interpolate from the rounded package values and can land on a different
    static instance (for example the bullet's medium component). Normalize at
    the interpolation boundary so both builds use the same persisted values.
    """
    for glyph in font.glyphs:
        for layer in glyph.layers:
            for component in layer.components:
                component.rotation = float(f"{component.rotation:.5f}")
                component.position = tuple(
                    float(f"{value:.3f}") for value in component.position
                )
                component.scale = tuple(
                    float(f"{value:.3f}") for value in component.scale
                )


def package(suffix):
    return ROOT / f'sources/NamcheShadowSans{suffix}.glyphspackage'


def initialize():
    """One-time explicit clean source extraction, reviewed with the migration."""
    if BASE.exists():
        raise ValueError('clean source exists; refusing to replace design inputs')
    result = {'source_commit':'bbdc0fd6f436316347e40bc15c243df3fd957a6d', 'design_issue':125, 'styles':{}}
    for suffix in ('', '-Italic'):
        font = GSFont(package(suffix))
        upstream = GSFont(ROOT / f'originals/geist/sources/Geist{suffix}.glyphspackage')
        records = {}
        for glyph in font.glyphs:
            layers = [glyph.layers[m.id] for m in font.masters] + [l for l in glyph.layers if 'coordinates' in l.attributes]
            selected, origin = layers, 'maintained unrounded upright foreground'
            if suffix:
                # Historical italic backgrounds include upright shapes (H),
                # even when all masters are structurally compatible. They are
                # not a trustworthy clean italic source. Use the explicit,
                # immutable italic foreground, retaining maintained metrics,
                # components, anchors and layout in prepare().
                selected = [upstream.glyphs[glyph.name].layers[l.layerId] for l in layers]
                origin = 'immutable Geist italic clean foreground'
            paths, normalization = resolve_compatible_clean_contours([contours(l) if l.paths else [] for l in selected])
            if normalization['method'] == 'authored_overlap_correspondence':
                print(f'Keeping authored compatible overlaps: {suffix or "Upright"}/{glyph.name}', flush=True)
            records[glyph.name] = {'origin':origin, 'topology_normalization':normalization,
                                  'masters':dict(zip([l.layerId for l in layers], paths))}
        result['styles'][suffix or 'Upright'] = records
    BASE.parent.mkdir(parents=True, exist_ok=True)
    BASE.write_text(json.dumps(result, ensure_ascii=False, separators=(',', ':'))+'\n')


def add_intermediate_masters(font):
    """Interpolate CLEAN geometry first, then solve fillets at every QA weight.

    Rounding only the three distant design masters can shave curved flanks
    between them. Use the maintained UFO instantiator, including sparse brace
    layers, to avoid handwritten interpolation of components/anchors/metrics.
    """
    import glyphsLib
    canonicalize_component_transforms(font)
    import ufoLib2
    from fontTools.designspaceLib import InstanceDescriptor
    from ufo2ft.instantiator import Instantiator
    document = glyphsLib.to_designspace(font, propagate_anchors=False,
        ufo_module=ufoLib2, store_editor_state=False, generate_GDEF=False,
        preserve_original=True)
    interpolator = Instantiator.from_designspace(document, round_geometry=False)
    original_masters = list(font.masters)
    existing = {int(master.axes[0]) for master in original_masters}
    for weight in range(100, 901, 50):
        if weight in existing:
            continue
        instance = InstanceDescriptor()
        instance.familyName, instance.styleName = font.familyName, f'Weight {weight}'
        instance.location = {'Weight':weight}
        interpolated = interpolator.generate_instance(instance)
        derived = glyphsLib.to_glyphs([interpolated])
        lower = max((m for m in original_masters if m.axes[0] < weight), key=lambda m:m.axes[0])
        upper = min((m for m in original_masters if m.axes[0] > weight), key=lambda m:m.axes[0])
        fraction = (weight-lower.axes[0])/(upper.axes[0]-lower.axes[0])
        # A one-UFO round trip has a different global metric/stem schema.
        # Retain this font's master schema while interpolating its values.
        master = copy.deepcopy(lower, {id(font):font})
        master.stems = [a+(b-a)*fraction for a,b in zip(lower.stems,upper.stems)]
        for value, a, b in zip(master.metrics,lower.metrics,upper.metrics):
            value.position = a.position+(b.position-a.position)*fraction
            value.overshoot = a.overshoot+(b.overshoot-a.overshoot)*fraction
        master.id = str(uuid.uuid5(uuid.NAMESPACE_URL,
            f'https://github.com/NamcheAI/namche-fonts/125/{font.masters[0].id}/{weight}')).upper()
        master.axes, master.name = [weight], f'Weight {weight}'
        master.customParameters['Axis Location'] = [{'Axis':'Weight','Location':weight}]
        font.masters.append(master)
        if len(master.stems) != len(font.stems):
            raise ValueError(f'{weight}: derived stem schema differs from the font')
        for attribute in ('capHeight','xHeight','ascender','descender'):
            expected = getattr(interpolated.info, attribute)
            if expected is not None and not math.isclose(getattr(master, attribute), expected, abs_tol=1e-6):
                raise ValueError(f'{weight}: derived {attribute} does not match clean interpolation')
        font.kerning[master.id] = copy.deepcopy(derived.kerning.get(derived.masters[0].id, {}))
        for glyph in font.glyphs:
            layer = derived.glyphs[glyph.name].layers[0]
            layer.layerId = layer.associatedMasterId = master.id
            glyph.layers[master.id] = layer
    font.masters = sorted(font.masters, key=lambda m:m.axes[0])


def prepare(output, clean=False, only=None):
    data = json.loads(BASE.read_text())
    report = {}
    for suffix in ('', '-Italic'):
        font = GSFont(package(suffix))
        records = data['styles'][suffix or 'Upright']
        original_ids = set(records['I']['masters'])
        # A checked-in generated package already contains intermediate masters.
        # Always rebuild them from the pinned original clean master model.
        font.masters = [m for m in font.masters if m.id in original_ids]
        for glyph in font.glyphs:
            record = records[glyph.name]['masters']
            glyph.layers = [l for l in glyph.layers if l.layerId in record]
            for mid, paths in record.items():
                set_paths(glyph.layers[mid], paths)
            for layer in glyph.layers:
                layer._background = None
        add_intermediate_masters(font)
        ids = [m.id for m in font.masters]
        stems = []
        for mid in ids:
            points = contours(font.glyphs['I'].layers[mid])[0]
            ys = {}
            for x,y,t in points: ys.setdefault(y, []).append(x)
            stems.append(min(max(xs)-min(xs) for xs in ys.values() if len(xs)>1))
        style_report = {}
        for glyph in font.glyphs:
            layers = [glyph.layers[mid] for mid in ids] + [l for l in glyph.layers if 'coordinates' in l.attributes]
            glyph_ids = [l.layerId for l in layers]
            glyph_stems = [stems[ids.index(mid)] if mid in ids else stems[-1] for mid in glyph_ids]
            paths = [contours(l) for l in layers]
            if not clean and any(paths) and (only is None or glyph.name in only):
                upper = any(unicodedata.category(chr(int(cp,16))) in ('Lu','Nd') for cp in glyph.unicodes)
                if not glyph.unicodes:
                    base = font.glyphs[glyph.name.split('.')[0]]
                    upper = bool(base and any(unicodedata.category(chr(int(cp,16))) in ('Lu','Nd') for cp in base.unicodes))
                try:
                    paths, joins = round_compatible_contours(paths, [r90_for_stem(s,upper) for s in glyph_stems],
                        semantic_b_waist=bool(suffix and glyph.name == 'B'))
                except ValueError as exc:
                    raise ValueError(f'{suffix or "Upright"}/{glyph.name}: {exc}') from exc
                style_report[glyph.name] = joins
            for mid,p in zip(glyph_ids,paths): set_paths(glyph.layers[mid],p)
        # Glyphs' legacy variable export record is parsed as a duplicate
        # Regular static by glyphsLib; keep only the nine single-axis instances.
        font.instances = [i for i in font.instances if len(i.axes) == len(font.axes)]
        for instance in font.instances:
            for p in list(instance.customParameters):
                if p.name == 'Filter' and 'RoundCorner' in str(p.value):
                    del instance.customParameters[p.name]
        target=output/f'NamcheShadowSans{suffix}.glyphspackage'
        save_package(font, target, package(suffix))
        report[suffix or 'Upright']={'stems':stems,'glyphs':style_report}
    (output/'corner-report.json').write_text(json.dumps(report,indent=2)+'\n')


def static_sources(output):
    """Keep only the solved continuous glyph for exact-master static exports.

    The extra clean contour set protects interpolation between VF masters. Each
    public static lies on a solved master, so overlapping that guard again only
    introduces coincident edges during integer conversion. This projection is
    structural: no curves, metrics, components or layout are redrawn.
    """
    records = json.loads(BASE.read_text())['styles']
    directory = output/'static-sources'
    directory.mkdir(parents=True, exist_ok=True)
    paths = []
    for suffix in ('', '-Italic'):
        name = f'NamcheShadowSans{suffix}.glyphspackage'
        font = GSFont(output/name)
        for glyph in font.glyphs:
            counts = {len(contours) for contours in records[suffix or 'Upright'][glyph.name]['masters'].values()}
            if len(counts) != 1:
                raise ValueError(f'{glyph.name}: clean contour count is incompatible')
            count = counts.pop()
            for layer in glyph.layers:
                contours = list(layer.paths)
                if len(contours) == count:
                    continue
                if not count or len(contours) != 2*count:
                    raise ValueError(f'{glyph.name}: unexpected clean/rounded contour structure')
                layer.paths = contours[count:]
        destination = directory/name
        save_package(font, destination, package(suffix))
        paths.append(destination.relative_to(output).as_posix())
    return paths


def compile_fonts(output, clean=False):
    import yaml
    config = {'sources':['NamcheShadowSans.glyphspackage','NamcheShadowSans-Italic.glyphspackage'],
        'outputDir':'fonts','familyName':'Namche Shadow Sans','buildVariable':True,
        'buildStatic':True,'buildTTF':True,'buildOTF':True,'autohintTTF':False,
        'autohintOTF':False,'cleanUp':False,'flattenComponents':True,
        'extraFontmakeArgs':'--conversion-error 0.0001',
        'extraVariableFontmakeArgs':'--filter DecomposeComponentsFilter --no-optimize-gvar'}
    config['stat'] = yaml.safe_load((ROOT/'sources/config-NamcheShadowSans.yaml').read_text())['stat']
    env=dict(os.environ, SOURCE_DATE_EPOCH='1795132800', PATH=str(Path(sys.executable).parent)+os.pathsep+os.environ['PATH'])
    def run(settings, filename):
        config_path=output/filename
        config_path.write_text(yaml.safe_dump(settings,sort_keys=False))
        subprocess.run([str(Path(sys.executable).with_name('gftools')),'builder',str(config_path)],env=env,check=True)
    if clean:
        run(config, 'config.yaml')
    else:
        run(dict(config, buildStatic=False), 'config-variable.yaml')
        run(dict(config, sources=static_sources(output), buildVariable=False), 'config-static.yaml')


def finalize(output):
    """Finalize identities, then synchronize the exact open VF representation."""
    from scripts.finalize_equal_ink import finalize_tree, DEFAULT_METADATA
    from scripts.recover_sans_production_source import recover
    from scripts.build_sans_open import build
    from fontTools.ttLib import TTFont
    final = output/'finalized'
    finalize_tree(output/'fonts', DEFAULT_METADATA, final,
                  normalize_unencoded_advances=True)
    provenance = json.loads(BASE.read_text())
    for suffix, style in [('', 'Upright'), ('-Italic', 'Italic')]:
        stem = f'NamcheShadowSans{suffix}[wght]'
        ttf, woff = final/'variable'/f'{stem}.ttf', final/'webfonts'/f'{stem}.woff2'
        source = output/'production-source'/f'NamcheShadowSans-{style}'
        recover(ttf, woff, source, provenance['source_commit'], bool(suffix))
        rebuilt = output/'open-roundtrip'/style
        build(source, rebuilt)
        # The XML round trip may repack layout, but must preserve all actual
        # geometry, variation, width and identity tables before pinning hashes.
        with TTFont(ttf) as before, TTFont(rebuilt/'variable'/ttf.name) as after:
            for tag in ('glyf','gvar','hmtx','HVAR','MVAR','avar','cmap','name','OS/2','STAT','fvar'):
                if (tag in before) != (tag in after) or (tag in before and before.getTableData(tag) != after.getTableData(tag)):
                    raise ValueError(f'{style}: production source round trip changed {tag}')
        manifest_path = source/'provenance.json'
        manifest = json.loads(manifest_path.read_text())
        manifest['recovered_from'] = f'issue-125 compatible cubic source build: {stem}.ttf'
        manifest['method'] = 'Quadratic production snapshot generated from the equal-ink cubic recipe; editable clean design inputs are sources/equal-ink/clean-outlines.json.'
        manifest['clean_source_sha256'] = sha256(BASE.read_bytes()).hexdigest()
        for rel in manifest['outputs']:
            data = (rebuilt/rel).read_bytes()
            manifest['outputs'][rel] = sha256(data).hexdigest()
            (final/rel).write_bytes(data)
        manifest['sha256'] = manifest['outputs'][f'variable/{ttf.name}']
        manifest_path.write_text(json.dumps(manifest,indent=2)+'\n')
    return final


def promote_release(output):
    """Install generated design sources, snapshots and binaries with rollback."""
    _check_font_inventory(output/'finalized')
    generated = []
    for suffix in ('', '-Italic'):
        name = f'NamcheShadowSans{suffix}.glyphspackage'
        source = output/name
        if not source.is_dir():
            raise ValueError(f'generated source is not a package directory: {source}')
        generated.append((source, ROOT/'sources'/name))
    for style in ('Upright', 'Italic'):
        name = f'NamcheShadowSans-{style}'
        source = output/'production-source'/name
        if not (source/'provenance.json').is_file():
            raise ValueError(f'missing finalized production source: {source}')
        generated.append((source, ROOT/'sources'/name))
    generated.append((output/'finalized', ROOT/'fonts/NamcheShadowSans'))
    _replace_trees(generated, ROOT/'sources')


def _replace_trees(generated, staging_root):
    # Stage every tree before changing any maintained representation. On an
    # installation failure, restore both design sources and release binaries.
    with tempfile.TemporaryDirectory(prefix='.equal-ink-promotion-', dir=staging_root) as directory:
        staged = Path(directory)
        for index, (source, _target) in enumerate(generated):
            shutil.copytree(source, staged/str(index),
                            ignore=shutil.ignore_patterns('finalization-report.json'))
        installed = []
        try:
            for index, (_, target) in enumerate(generated):
                backup = staged/f'previous-{index}' if target.exists() else None
                if backup is not None:
                    os.replace(target, backup)
                installed.append((target, backup))
                target.parent.mkdir(parents=True, exist_ok=True)
                os.replace(staged/str(index), target)
        except Exception:
            for target, backup in reversed(installed):
                if target.exists():
                    shutil.rmtree(target)
                if backup is not None:
                    os.replace(backup, target)
            raise


def _check_font_inventory(root, allow_derived_subsets=False):
    from scripts.finalize_equal_ink import expected_paths
    required = set(expected_paths())
    required.update(f'webfonts/{Path(name).stem}.woff2' for name in expected_paths() if name.endswith('.ttf'))
    actual = {p.relative_to(root).as_posix() for p in root.rglob('*') if p.suffix in ('.ttf','.otf','.woff2')}
    if allow_derived_subsets:
        # make subset-webfonts stages ignored compatibility copies here. They
        # are checked separately and are not part of the 58-file source build.
        actual = {name for name in actual if not name.startswith('webfonts/subsets/')}
    if actual != required:
        raise ValueError(f'incomplete finalized font set in {root}: missing={sorted(required-actual)}, extra={sorted(actual-required)}')
    return required


def check_release(output, release):
    final = output/'finalized'
    required = _check_font_inventory(final)
    _check_font_inventory(release, allow_derived_subsets=True)
    expected = [final/name for name in sorted(required)]
    failures = [str(p.relative_to(final)) for p in expected
                if not (release/p.relative_to(final)).is_file()
                or p.read_bytes() != (release/p.relative_to(final)).read_bytes()]
    if failures:
        raise ValueError(f'compiled Sans files differ from committed release: {failures}')
    import glyphsLib
    for suffix in ('', '-Italic'):
        name = f'NamcheShadowSans{suffix}.glyphspackage'
        if glyphsLib.dumps(GSFont(output/name)) != glyphsLib.dumps(GSFont(package(suffix))):
            raise ValueError(f'generated design source differs from maintained package: {name}')
    print(f'PASS equal-ink recipe: {len(expected)} binaries and both design packages equal committed release')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--initialize',action='store_true')
    p.add_argument('--output',type=Path,default=ROOT/'out/equal-ink')
    p.add_argument('--clean',action='store_true',help='Compile the unrounded baseline for geometry validation')
    p.add_argument('--prepare-only',action='store_true')
    p.add_argument('--glyphs',nargs='+',help='Experimental limited bake, never a release build')
    p.add_argument('--finalize',action='store_true',help='Restore source metadata and produce synchronized open VF sources')
    p.add_argument('--promote',action='store_true',help='Install finalized binaries and both synchronized source representations')
    p.add_argument('--check',action='store_true',help='Finalize and compare every binary with the committed release')
    a=p.parse_args()
    if (a.finalize or a.check) and (a.clean or a.prepare_only or a.glyphs):
        p.error('release finalization requires a complete rounded build')
    if a.promote and (not a.finalize or a.check):
        p.error('--promote requires --finalize and cannot be combined with --check')
    if a.initialize:initialize()
    a.output.mkdir(parents=True,exist_ok=True)
    prepare(a.output,a.clean,a.glyphs)
    if not a.prepare_only:compile_fonts(a.output,a.clean)
    if a.finalize or a.check:finalize(a.output)
    if a.promote:promote_release(a.output)
    if a.check:check_release(a.output,ROOT/'fonts/NamcheShadowSans')

if __name__=='__main__':main()
