#!/usr/bin/env python3
"""Finalize freshly compiled issue #125 outlines from source metadata fixtures.

One-time migration:
  python scripts/finalize_equal_ink.py --capture-metadata fonts/NamcheShadowSans
Normal source-only builds (no old release binaries are read):
  python scripts/finalize_equal_ink.py --compiled out/equal-ink/fonts --output out/finalized

Fixtures retain public naming, attribution, menu identity and glyph-name-based
layout. Compiled geometry, metrics and variation tables remain new. All hints
are discarded so no program can refer to the previous point topology.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
import shutil
from types import SimpleNamespace
import tempfile

from fontTools.ttLib import TTFont
from fontTools.subset import Options, Subsetter
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.pens.recordingPen import RecordingPen
from fontTools.pens.t2CharStringPen import T2CharStringPen

try:
    from .latin_core import CODEPOINTS
    from .refresh_sans_italic_outlines import CFF_IDENTITY_KEYS, preserve_cff_identity
except ImportError:
    from latin_core import CODEPOINTS
    from refresh_sans_italic_outlines import CFF_IDENTITY_KEYS, preserve_cff_identity

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RELEASE = ROOT / 'fonts/NamcheShadowSans'
DEFAULT_METADATA = ROOT / 'sources/equal-ink/release-metadata'
WEIGHTS = ('Thin', 'ExtraLight', 'Light', 'Regular', 'Medium', 'SemiBold', 'Bold', 'ExtraBold', 'Black')
# maxp/hmtx and all geometry/variation data deliberately come from compilation.
PRESERVE_TAGS = ('GlyphOrder', 'head', 'hhea', 'OS/2', 'name', 'post', 'cmap',
                 'GDEF', 'GPOS', 'GSUB', 'STAT', 'fvar', 'gasp', 'meta', 'kern')
HINT_TABLES = ('cvt ', 'fpgm', 'prep', 'cvar', 'hdmx', 'LTSH', 'VDMX', 'DSIG')


def expected_paths():
    paths = []
    for weight in WEIGHTS:
        for style in (weight, 'Italic' if weight == 'Regular' else weight+'Italic'):
            for extension in ('otf', 'ttf'):
                paths.append(f'{extension}/NamcheShadowSans-{style}.{extension}')
    paths.extend(('variable/NamcheShadowSans[wght].ttf',
                  'variable/NamcheShadowSans-Italic[wght].ttf'))
    return sorted(paths)


def check_core(font, label):
    actual = {cp for table in font['cmap'].tables if table.isUnicode() for cp in table.cmap}
    if actual != CODEPOINTS:
        raise ValueError(f'{label}: cmap must contain exactly the {len(CODEPOINTS)} Latin Core characters')


def _decompile(font):
    font.ensureDecompiled()
    # Capture the order now, before imported tables can resolve any glyph IDs.
    font.getGlyphOrder()


def capture_font(release_path: Path, ttx_path: Path):
    """Capture one font's non-outline contract; helper also used in tests."""
    with TTFont(release_path, recalcTimestamp=False) as font:
        check_core(font, release_path)
        _decompile(font)
        tags = [tag for tag in PRESERVE_TAGS if tag in font]
        ttx_path.parent.mkdir(parents=True, exist_ok=True)
        font.saveXML(ttx_path, tables=tags, newlinestr='\n')
        identity = None
        if 'CFF ' in font:
            cff = font['CFF '].cff
            top = cff[cff.fontNames[0]]
            identity = {'font_names': cff.fontNames,
                        'attributes': {key: getattr(top, key) for key in CFF_IDENTITY_KEYS if hasattr(top, key)}}
        record = {'schema': 1, 'tables': tags,
                  'advances': {name: font['hmtx'][name][0] for name in font.getGlyphOrder()},
                  'cff_identity': identity}
        ttx_path.with_suffix('.json').write_text(json.dumps(record, indent=2, sort_keys=True)+'\n')
        return record


def capture_metadata(release: Path, metadata: Path):
    """Explicit one-time action; refuse to overwrite already pinned fixtures."""
    files = expected_paths()
    missing = [rel for rel in files if not (release/rel).is_file()]
    if missing:
        raise FileNotFoundError(f'incomplete release metadata input: {missing}')
    if metadata.exists() and any(metadata.iterdir()):
        raise ValueError(f'metadata fixtures already exist: {metadata}')
    metadata.mkdir(parents=True, exist_ok=True)
    for rel in files:
        capture_font(release/rel, metadata/(rel+'.ttx'))
    (metadata/'manifest.json').write_text(json.dumps({'schema': 1, 'fonts': files}, indent=2)+'\n')


class _IdentityCFF:
    def __init__(self, identity):
        self.fontNames = identity['font_names']
        self.top = SimpleNamespace(**identity['attributes'])

    def __getitem__(self, key):
        return self.top


def _apply_cff_identity(font, identity):
    if identity is None:
        raise ValueError('CFF font has no captured identity')
    top = font['CFF '].cff.topDictIndex[0]
    # Full metadata restoration preserves absence as well as presence. The
    # outline-only refresh helper deliberately refuses new identity fields;
    # remove those fields explicitly before applying its existing contract.
    for key in CFF_IDENTITY_KEYS:
        if key not in identity['attributes']:
            top.rawDict.pop(key, None)
            top.__dict__.pop(key, None)
    carrier = {'CFF ': SimpleNamespace(cff=_IdentityCFF(identity))}
    # Use the existing maintained identity contract without bootstrapping from
    # any previous outline table or binary.
    return preserve_cff_identity(carrier, font)


def _strip_hints(font):
    removed = [tag for tag in HINT_TABLES if tag in font]
    for tag in removed:
        del font[tag]
    if 'glyf' in font:
        for name in font.getGlyphOrder():
            font['glyf'][name].removeHinting()
        maxp = font['maxp']
        for field, value in (('maxZones', 1), ('maxTwilightPoints', 0), ('maxStorage', 0),
                             ('maxFunctionDefs', 0), ('maxInstructionDefs', 0),
                             ('maxStackElements', 0), ('maxSizeOfInstructions', 0)):
            setattr(maxp, field, value)
    if 'CFF ' in font:
        font['CFF '].cff.remove_hints()
    return removed


def _axis_contract(font):
    if 'fvar' not in font:
        return None
    return [(a.axisTag, a.minValue, a.defaultValue, a.maxValue) for a in font['fvar'].axes]


def _collinear(points):
    if not points:
        return True
    origin = points[0]
    direction = next(((p[0]-origin[0], p[1]-origin[1]) for p in points if p != origin), None)
    return direction is None or all(direction[0]*(p[1]-origin[1])-direction[1]*(p[0]-origin[0]) == 0
                                    for p in points)


def _clean_recording(commands):
    """Remove only exact zero geometry, retaining unrounded control points."""
    contours, current = [], []
    for command in commands:
        if command[0] == 'moveTo' and current:
            contours.append(current)
            current = []
        current.append(command)
        if command[0] in ('closePath', 'endPath', 'addComponent'):
            contours.append(current)
            current = []
    if current:
        contours.append(current)
    result, removed_contours, removed_segments = [], 0, 0
    for contour in contours:
        if any(op == 'addComponent' for op, _ in contour):
            result.extend(contour)
            continue
        points = [p for op, args in contour for p in args if p is not None]
        if _collinear(points):
            removed_contours += 1
            continue
        position = None
        for op, args in contour:
            if op == 'moveTo':
                position = args[0]
            elif op == 'lineTo':
                if args[0] == position:
                    removed_segments += 1
                    continue
                position = args[0]
            elif op == 'curveTo':
                if all(p == position for p in args):
                    removed_segments += 1
                    continue
                position = args[-1]
            elif op == 'qCurveTo':
                if args[-1] is not None:
                    controls, end = list(args[:-1]), args[-1]
                    while len(controls) > 1 and controls[0] == controls[1] == position:
                        controls.pop(0)
                        removed_segments += 1
                    while len(controls) > 1 and controls[-1] == controls[-2] == end:
                        controls.pop()
                        removed_segments += 1
                    compressed = []
                    for point in controls:
                        if len(compressed) >= 2 and compressed[-1] == compressed[-2] == point:
                            removed_segments += 1
                        else:
                            compressed.append(point)
                    args = tuple(compressed)+(end,)
                    if all(p == position for p in args):
                        removed_segments += 1
                        continue
                    position = end
                else:
                    position = None
            result.append((op, args))
    return result, removed_contours, removed_segments


def _cleanup_static_geometry(font):
    """Remove exact degenerate contours/segments only in static outputs."""
    if 'fvar' in font:
        return {}
    changes = {}
    glyph_set = font.getGlyphSet()
    for name in font.getGlyphOrder():
        if 'glyf' in font and font['glyf'][name].isComposite():
            continue
        recording = RecordingPen()
        glyph_set[name].draw(recording)
        commands, contours, segments = _clean_recording(recording.value)
        if not contours and not segments:
            continue
        filtered = RecordingPen()
        filtered.value = commands
        if 'glyf' in font:
            pen = TTGlyphPen(glyph_set)
            filtered.replay(pen)
            replacement = pen.glyph()
            font['glyf'][name] = replacement
        else:
            cff = font['CFF '].cff
            top = cff.topDictIndex[0]
            old = top.CharStrings[name]
            pen = T2CharStringPen(font['hmtx'][name][0]-old.private.nominalWidthX,
                                  glyph_set, roundTolerance=0)
            filtered.replay(pen)
            top.CharStrings[name] = pen.getCharString(private=old.private, globalSubrs=cff.GlobalSubrs)
        changes[name] = dict(removed_collinear_contours=contours, removed_zero_length_segments=segments)
    return changes


def _prune_unreachable_extras(font, old_order):
    """Prune only glyphs unreachable after the captured release layout is applied."""
    options = Options()
    options.layout_features = ['*']
    options.name_IDs = ['*']
    options.name_languages = ['*']
    options.name_legacy = True
    options.notdef_outline = True
    options.glyph_names = True
    options.recalc_timestamp = False
    options.harfbuzz_repacker = False
    options.no_subset_tables += ['meta']
    before = font.getGlyphOrder()
    # Subsetting a variable font must only remove whole unused glyphs. Preserve
    # every retained outline's point order and every variation's indexed deltas.
    snapshots = {}
    if 'fvar' in font:
        glyf = font['glyf']
        for name in before:
            coordinates, ends, flags = glyf[name].getCoordinates(glyf)
            variations = tuple((tuple(sorted(v.axes.items())), tuple(v.coordinates))
                               for v in font['gvar'].variations.get(name, []))
            snapshots[name] = (tuple(coordinates), tuple(ends), bytes(flags), variations)
    subsetter = Subsetter(options=options)
    subsetter.populate(glyphs=old_order)
    subsetter.subset(font)
    retained = font.getGlyphOrder()
    if not set(old_order) <= set(retained):
        raise ValueError('reachability pruning removed a captured release glyph')
    if snapshots:
        glyf = font['glyf']
        for name in retained:
            coordinates, ends, flags = glyf[name].getCoordinates(glyf)
            variations = tuple((tuple(sorted(v.axes.items())), tuple(v.coordinates))
                               for v in font['gvar'].variations.get(name, []))
            after = (tuple(coordinates), tuple(ends), bytes(flags), variations)
            if snapshots[name] != after:
                raise ValueError(f'{name}: reachability pruning changed VF point topology or deltas')
    return sorted(set(before)-set(retained))


def _compress_variable_deltas_losslessly(font):
    """Compress full gvar tuples without the compiler's half-unit IUP loss."""
    if 'gvar' not in font or 'glyf' not in font:
        return {}
    glyf = font['glyf']
    changed, retained = 0, 0
    for name, variations in font['gvar'].variations.items():
        coordinates, controls = glyf._getCoordinatesAndControls(
            name, font['hmtx'].metrics, getattr(font.get('vmtx'), 'metrics', None))
        for variation in variations:
            original = deepcopy(variation)
            original.calcInferredDeltas(coordinates, controls.endPts)
            variation.coordinates = list(original.coordinates)
            variation.optimize(coordinates, controls.endPts, tolerance=0.0,
                               isComposite=glyf[name].isComposite())
            expanded = deepcopy(variation)
            expanded.calcInferredDeltas(coordinates, controls.endPts)
            if expanded.coordinates != original.coordinates:
                # Keep the full tuple if a serializer/platform calculation is
                # not exactly reversible; geometry outranks byte savings.
                variation.coordinates = list(original.coordinates)
                retained += 1
            elif None in variation.coordinates:
                changed += 1
    return dict(losslessly_compressed_tuples=changed,
                retained_full_tuples_after_precision_check=retained)


def _mark_variable_overlaps(font):
    """Tell rasterizers that compatible VF contours intentionally overlap.

    Static exports have already unioned their overlaps. Variable contours must
    keep their point correspondence, so mark the first point/component using
    fontTools' standard OpenType overlap handling instead of removing contours.
    """
    if 'fvar' not in font or 'glyf' not in font:
        return 0
    from fontTools.varLib.instancer import setMacOverlapFlags
    glyf = font['glyf']
    setMacOverlapFlags(glyf)
    return sum(glyf[name].numberOfContours != 0 for name in font.getGlyphOrder())


def finalize_font(compiled_path: Path, ttx_path: Path, output_path: Path,
                  normalize_unencoded_advances: bool = False):
    """Finalize one new font, remapping captured layout by glyph name."""
    record = json.loads(ttx_path.with_suffix('.json').read_text())
    metadata = TTFont(recalcTimestamp=False)
    metadata.importXML(ttx_path)
    unexpected = set(metadata.keys()) - set(PRESERVE_TAGS)
    if unexpected:
        raise ValueError(f'{ttx_path}: prohibited fixture tables: {sorted(unexpected)}')
    with TTFont(compiled_path, recalcTimestamp=False) as font:
        check_core(font, compiled_path)
        _decompile(font)
        check_core(metadata, ttx_path)
        new_order = font.getGlyphOrder()
        old_order = metadata.getGlyphOrder()
        missing = set(old_order) - set(new_order)
        if missing:
            raise ValueError(f'{compiled_path}: missing release glyph names: {sorted(missing)}')
        if _axis_contract(font) != _axis_contract(metadata):
            raise ValueError(f'{compiled_path}: variation axis contract differs from metadata')
        if font['head'].unitsPerEm != metadata['head'].unitsPerEm:
            raise ValueError(f'{compiled_path}: unitsPerEm differs from metadata')
        differences = {name: [width, font['hmtx'][name][0]]
                       for name, width in record['advances'].items()
                       if width != font['hmtx'][name][0]}
        encoded = {name for table in metadata['cmap'].tables if table.isUnicode()
                   for name in table.cmap.values()}
        unacceptable = {n: values for n, values in differences.items()
                        if not normalize_unencoded_advances or 'fvar' in font
                        or n in encoded or abs(values[0]-values[1]) > 1}
        if unacceptable:
            example = dict(list(unacceptable.items())[:12])
            raise ValueError(f'{compiled_path}: {len(unacceptable)} advance widths changed: {example}')
        # Both sides are fully decompiled while they still have their own
        # original orders. Imported coverage/class/lookup tables now contain
        # names, and fontTools compiles them to the NEW outline glyph IDs.
        _decompile(metadata)
        for tag in PRESERVE_TAGS:
            if tag == 'GlyphOrder':
                continue
            if tag in metadata:
                font[tag] = deepcopy(metadata[tag])
            elif tag in font:
                del font[tag]
        font.setGlyphOrder(new_order)
        if font['post'].formatType == 2.0:
            # Name every compiled glyph, including new unencoded mark helpers.
            font['post'].mapping = {}
            font['post'].extraNames = []
        identity_keys = _apply_cff_identity(font, record['cff_identity']) if 'CFF ' in font else []
        removed_hints = _strip_hints(font)
        pruned_glyphs = _prune_unreachable_extras(font, old_order)
        new_order = font.getGlyphOrder()
        cleaned_static_geometry = _cleanup_static_geometry(font)
        marked_variable_overlaps = _mark_variable_overlaps(font)
        lossless_variation_compression = _compress_variable_deltas_losslessly(font)
        # Native Glyphs statics and fresh interpolation differ by one unit for
        # a few unencoded fi/fl ligatures. An explicit policy preserves their
        # declared release advances while retaining new LSBs and outlines.
        for name, (old_width, _new_width) in differences.items():
            _advance, lsb = font['hmtx'][name]
            font['hmtx'][name] = old_width, lsb
            if 'CFF ' in font:
                cff = font['CFF '].cff
                top = cff.topDictIndex[0]
                charstring = top.CharStrings[name]
                before = RecordingPen()
                charstring.draw(before)
                pen = T2CharStringPen(old_width-charstring.private.nominalWidthX,
                                      font.getGlyphSet(), roundTolerance=0)
                before.replay(pen)
                replacement = pen.getCharString(private=charstring.private,
                                               globalSubrs=cff.GlobalSubrs)
                after = RecordingPen()
                replacement.draw(after)
                if before.value != after.value:
                    raise ValueError(f'{name}: advance normalization changed CFF outlines')
                if replacement.width != old_width:
                    raise ValueError(f'{name}: CFF and hmtx advance disagree')
                top.CharStrings[name] = replacement
        font.recalcTimestamp = False
        font.recalcBBoxes = True
        check_core(font, output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        font.save(output_path, reorderTables=False)
    metadata.close()
    with TTFont(output_path, recalcTimestamp=False) as saved:
        check_core(saved, output_path)
        if saved.getGlyphOrder() != new_order:
            raise ValueError(f'{output_path}: finalized glyph names/order changed')
        changed_widths = {name: [width, saved['hmtx'][name][0]]
                          for name, width in record['advances'].items()
                          if width != saved['hmtx'][name][0]}
        if changed_widths:
            raise ValueError(f'{output_path}: final advances violate metadata contract: {changed_widths}')
        if any(tag in saved for tag in HINT_TABLES):
            raise ValueError(f'{output_path}: a hinting table survived finalization')
        if 'glyf' in saved and any(getattr(saved['glyf'][n], 'program', None) and
                                  saved['glyf'][n].program.getBytecode() for n in new_order):
            raise ValueError(f'{output_path}: a glyph instruction survived finalization')
    return {'glyphs': len(new_order), 'new_unencoded_glyphs': sorted(set(new_order)-set(old_order)),
            'advance_differences': differences, 'normalized_unencoded_advances': differences,
            'removed_hint_tables': removed_hints,
            'pruned_unreachable_glyphs': pruned_glyphs,
            'cleaned_static_geometry': cleaned_static_geometry,
            'marked_variable_overlaps': marked_variable_overlaps,
            'lossless_variation_compression': lossless_variation_compression,
            'preserved_cff_identity': identity_keys}


def finalize_tree(compiled: Path, metadata: Path, output: Path, normalize_unencoded_advances=False):
    if output.resolve() in (DEFAULT_RELEASE.resolve(), compiled.resolve(), metadata.resolve()):
        raise ValueError('output must be isolated from the release, compiled inputs and metadata fixtures')
    if output.exists() and any(output.iterdir()):
        raise ValueError(f'output must be empty: {output}')
    manifest = json.loads((metadata/'manifest.json').read_text())
    if manifest != {'schema': 1, 'fonts': expected_paths()}:
        raise ValueError('metadata manifest does not describe the complete 38-font Sans family')
    for rel in manifest['fonts']:
        for path in (compiled/rel, metadata/(rel+'.ttx'), (metadata/(rel+'.ttx')).with_suffix('.json')):
            if not path.is_file():
                raise FileNotFoundError(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    report = {}
    with tempfile.TemporaryDirectory(prefix='namche-equal-ink-finalize-', dir=output.parent) as tmp:
        stage = Path(tmp)
        for rel in manifest['fonts']:
            final_path = stage/rel
            report[rel] = finalize_font(compiled/rel, metadata/(rel+'.ttx'), final_path, normalize_unencoded_advances)
            if final_path.suffix == '.ttf':
                woff = stage/'webfonts'/final_path.with_suffix('.woff2').name
                with TTFont(final_path, recalcTimestamp=False) as font:
                    font.flavor = 'woff2'
                    woff.parent.mkdir(parents=True, exist_ok=True)
                    font.save(woff, reorderTables=False)
        (stage/'finalization-report.json').write_text(json.dumps(report, indent=2, sort_keys=True)+'\n')
        shutil.copytree(stage, output, dirs_exist_ok=True)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capture-metadata', type=Path, nargs='?', const=DEFAULT_RELEASE,
                        help='one-time capture from existing release; never part of a source build')
    parser.add_argument('--metadata', type=Path, default=DEFAULT_METADATA)
    parser.add_argument('--compiled', type=Path, help='fresh gftools output with otf/, ttf/ and variable/')
    parser.add_argument('--output', type=Path, help='isolated output directory; must be empty')
    parser.add_argument('--normalize-unencoded-advances', action='store_true',
                        help='restore and report only static unencoded advance differences of at most one unit')
    args = parser.parse_args(argv)
    if args.capture_metadata:
        if args.compiled or args.output:
            parser.error('capture metadata separately from finalization')
        capture_metadata(args.capture_metadata, args.metadata)
        print(f'Captured source metadata fixtures for {len(expected_paths())} fonts')
    else:
        if args.compiled is None or args.output is None:
            parser.error('--compiled and --output are required for source-only finalization')
        report = finalize_tree(args.compiled, args.metadata, args.output, args.normalize_unencoded_advances)
        print(f'Finalized {len(report)} fonts from source metadata fixtures: {args.output}')


if __name__ == '__main__':
    main()
