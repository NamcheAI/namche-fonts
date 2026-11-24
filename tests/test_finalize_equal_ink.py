"""Source-only metadata finalization, including changed glyph ID ordering."""
from pathlib import Path
import json
import shutil
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont, newTable
from fontTools.ttLib.tables.ttProgram import Program

from scripts import finalize_equal_ink as finalize


def make_font(path, family, extra=False, advance_delta=0, hints=False, advance_name="u0041"):
    names = ['.notdef'] + [f'u{cp:04X}' for cp in sorted(finalize.SANS_CODEPOINTS)] + ['lig.helper']
    if extra:
        names = ['.notdef'] + list(reversed(names[1:])) + ['new.helper']
    builder = FontBuilder(1000, isTTF=True)
    builder.setupGlyphOrder(names)
    builder.setupCharacterMap({cp: f'u{cp:04X}' for cp in finalize.SANS_CODEPOINTS})
    glyphs = {}
    for name in names:
        pen = TTGlyphPen(None)
        pen.moveTo((10, 0))
        pen.lineTo((200 if extra else 100, 0))
        pen.lineTo((100, 300))
        pen.closePath()
        glyphs[name] = pen.glyph()
    if hints:
        glyphs['u0041'].program = Program()
        glyphs['u0041'].program.fromBytecode([0xB0, 1, 0x21])
    builder.setupGlyf(glyphs)
    metrics = {name: (500 + (advance_delta if name == advance_name else 0), 10) for name in names}
    builder.setupHorizontalMetrics(metrics)
    builder.setupHorizontalHeader(ascent=800, descent=-200)
    builder.setupNameTable({'familyName': family, 'styleName': 'Regular',
                            'uniqueFontIdentifier': family+' Regular',
                            'fullName': family+' Regular', 'psName': family+'-Regular',
                            'version': 'Version 1.000'})
    builder.setupOS2(sTypoAscender=800, sTypoDescender=-200, usWinAscent=800, usWinDescent=200,
                     usWeightClass=700 if extra else 400)
    builder.setupPost(keepGlyphNames=True)
    builder.setupMaxp()
    if hints:
        table = newTable('fpgm')
        table.program = Program()
        table.program.fromBytecode([0xB0, 1, 0x21])
        builder.font['fpgm'] = table
    addOpenTypeFeaturesFromString(builder.font, 'feature liga { sub u0041 u0042 by u0043; } liga;')
    builder.font.recalcTimestamp = False
    builder.font['head'].created = builder.font['head'].modified = 3850000000
    builder.save(path)


class EqualInkFinalizerTest(unittest.TestCase):
    def test_lossless_iup_keeps_small_variation_differences(self):
        from copy import deepcopy
        from fontTools.ttLib.tables.TupleVariation import TupleVariation
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'variations.ttf'
            make_font(path, 'PublicNamche')
            with TTFont(path) as font:
                pen = TTGlyphPen(font['glyf'])
                xs = [0, 19]+list(range(40, 201, 20))
                points = [(x, 0) for x in xs]+[(x, 300) for x in reversed(xs)]
                pen.moveTo(points[0])
                for point in points[1:]: pen.lineTo(point)
                pen.closePath()
                font['glyf']['u0041'] = pen.glyph()
                coords, controls = font['glyf']._getCoordinatesAndControls('u0041', font['hmtx'].metrics)
                deltas = [(round(x/20), 0) for x,y in coords[:-4]]+[(0,0)]*4
                variation = TupleVariation({'wght':(0,1,1)}, deltas)
                lossy = deepcopy(variation)
                lossy.optimize(coords, controls.endPts)
                lossy.calcInferredDeltas(coords, controls.endPts)
                self.assertNotEqual(lossy.coordinates, deltas)
                font['gvar'] = newTable('gvar')
                font['gvar'].variations = {'u0041':[variation]}
                report = finalize._compress_variable_deltas_losslessly(font)
                expanded = deepcopy(variation)
                expanded.calcInferredDeltas(coords, controls.endPts)
                self.assertEqual(expanded.coordinates, deltas)
                self.assertGreater(report['losslessly_compressed_tuples'], 0)

    def test_variable_overlap_flags_preserve_coordinates_and_mark_components(self):
        from fontTools.ttLib.tables._g_l_y_f import flagOverlapSimple, OVERLAP_COMPOUND
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'overlaps.ttf'
            make_font(path, 'PublicNamche')
            with TTFont(path) as font:
                self.assertEqual(finalize._mark_variable_overlaps(font), 0)
                pen = TTGlyphPen(font['glyf'])
                pen.addComponent('u0041', (1, 0, 0, 1, 0, 0))
                font['glyf']['u0042'] = pen.glyph()
                font['fvar'] = newTable('fvar')
                original = list(font['glyf']['u0041'].coordinates)
                self.assertEqual(finalize._mark_variable_overlaps(font), len(font.getGlyphOrder()))
                self.assertTrue(font['glyf']['u0041'].flags[0] & flagOverlapSimple)
                self.assertTrue(font['glyf']['u0042'].components[0].flags & OVERLAP_COMPOUND)
                self.assertEqual(list(font['glyf']['u0041'].coordinates), original)

    def test_promotion_rolls_back_sources_and_binaries_after_late_failure(self):
        from scripts.build_sans_equal_ink import _replace_trees
        import os
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            pairs = []
            for name in ('design', 'production', 'binaries'):
                source, target = root/('new-'+name), root/name
                source.mkdir(); target.mkdir()
                (source/'value').write_text('new')
                (target/'value').write_text('old')
                pairs.append((source, target))
            real_replace = os.replace
            def fail_on_last_install(source, target):
                if Path(source).name == '2' and Path(target) == root/'binaries':
                    raise OSError('simulated late installation failure')
                return real_replace(source, target)
            with patch('scripts.build_sans_equal_ink.os.replace', side_effect=fail_on_last_install):
                with self.assertRaisesRegex(OSError, 'simulated late'):
                    _replace_trees(pairs, root)
            self.assertEqual([(target/'value').read_text() for _, target in pairs], ['old']*3)

    def test_promotion_installs_a_missing_release_tree(self):
        from scripts.build_sans_equal_ink import _replace_trees
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source, target = root/'generated', root/'fonts/NamcheShadowSans'
            source.mkdir()
            (source/'value').write_bytes(b'new release')
            _replace_trees([(source, target)], root)
            self.assertEqual((target/'value').read_bytes(), b'new release')
            self.assertEqual((source/'value').read_bytes(), b'new release')

    def test_promotion_rollback_restores_absence_and_existing_trees(self):
        from scripts.build_sans_equal_ink import _replace_trees
        import os
        for missing_index in range(3):
            with self.subTest(missing_index=missing_index), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                pairs = []
                for index in range(3):
                    source, target = root/f'new-{index}', root/f'target-{index}'
                    source.mkdir()
                    (source/'value').write_bytes(b'new')
                    if index != missing_index:
                        target.mkdir()
                        (target/'value').write_bytes(b'old')
                    pairs.append((source, target))
                real_replace = os.replace
                def fail_on_last_install(source, target):
                    if Path(source).name == '2' and Path(target) == pairs[2][1]:
                        raise OSError('simulated late installation failure')
                    return real_replace(source, target)
                with patch('scripts.build_sans_equal_ink.os.replace', side_effect=fail_on_last_install):
                    with self.assertRaisesRegex(OSError, 'simulated late'):
                        _replace_trees(pairs, root)
                for index, (source, target) in enumerate(pairs):
                    self.assertEqual((source/'value').read_bytes(), b'new')
                    if index == missing_index:
                        self.assertFalse(target.exists())
                    else:
                        self.assertEqual((target/'value').read_bytes(), b'old')

    def test_inventory_rejects_extra_release_font_but_allows_derived_subsets(self):
        from scripts.build_sans_equal_ink import _check_font_inventory
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            paths = finalize.expected_paths()
            paths += [f'webfonts/{Path(name).stem}.woff2' for name in paths if name.endswith('.ttf')]
            for name in paths:
                path = root/name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b'fixture')
            derived = root/'webfonts/subsets/derived.woff2'
            derived.parent.mkdir(); derived.write_bytes(b'fixture')
            self.assertEqual(len(_check_font_inventory(root, allow_derived_subsets=True)), 58)
            (root/'ttf/stale.ttf').write_bytes(b'stale')
            with self.assertRaisesRegex(ValueError, 'stale.ttf'):
                _check_font_inventory(root, allow_derived_subsets=True)

    def test_release_check_rejects_missing_generated_fonts(self):
        from scripts.build_sans_equal_ink import check_release
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root/'finalized').mkdir()
            with self.assertRaisesRegex(ValueError, 'incomplete finalized font set'):
                check_release(root, root/'release')

    def test_release_mismatch_writes_table_and_glyph_diagnostics(self):
        from scripts.build_sans_equal_ink import check_release
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            expected = root/'finalized/ttf/test.ttf'
            actual = root/'release/ttf/test.ttf'
            expected.parent.mkdir(parents=True)
            actual.parent.mkdir(parents=True)
            make_font(expected, 'Fixture')
            make_font(actual, 'Fixture')
            with TTFont(actual) as font:
                glyph = font['glyf']['u0041']
                glyph.coordinates[0] = (glyph.coordinates[0][0] + 1, glyph.coordinates[0][1])
                font.save(actual)
            with patch('scripts.build_sans_equal_ink._check_font_inventory', return_value={'ttf/test.ttf'}):
                with self.assertRaisesRegex(ValueError, 'release-differences.json'):
                    check_release(root, root/'release')
            report = json.loads((root/'release-differences.json').read_text())
            difference, = report['differences']
            self.assertNotEqual(difference['expected_sha256'], difference['actual_sha256'])
            self.assertIn('glyf', difference['differing_tables'])
            self.assertIn('u0041', difference['affected_glyphs']['glyf'])

    def test_metadata_survives_new_order_and_no_release_binary_is_required(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            release, compiled, output = root/'old.ttf', root/'compiled.ttf', root/'new.ttf'
            fixture = root/'contract.ttf.ttx'
            make_font(release, 'PublicNamche')
            make_font(compiled, 'BuildIdentity', extra=True, hints=True)
            finalize.capture_font(release, fixture)
            release.unlink()  # The final build cannot bootstrap from old binaries.
            report = finalize.finalize_font(compiled, fixture, output)
            with TTFont(compiled) as new, TTFont(output) as result:
                self.assertEqual(result.getGlyphOrder(), [n for n in new.getGlyphOrder() if n != 'new.helper'])
                self.assertEqual(result['name'].getDebugName(1), 'PublicNamche')
                self.assertEqual(result['OS/2'].usWeightClass, 400)
                self.assertEqual(result['glyf']['u0041'].coordinates, new['glyf']['u0041'].coordinates)
                ligature = result['GSUB'].table.LookupList.Lookup[0].SubTable[0].ligatures['u0041'][0]
                self.assertEqual(ligature.Component, ['u0042'])
                self.assertEqual(ligature.LigGlyph, 'u0043')
                self.assertNotIn('fpgm', result)
                self.assertFalse(result['glyf']['u0041'].program.getBytecode())
                self.assertEqual(set(result.getBestCmap()), finalize.SANS_CODEPOINTS)
            self.assertEqual(report['new_unencoded_glyphs'], [])
            self.assertEqual(report['pruned_unreachable_glyphs'], ['new.helper'])
            self.assertIn('fpgm', report['removed_hint_tables'])
            self.assertEqual(report['advance_differences'], {})
            # Captured fixtures contain no previous geometry or hint programs.
            with TTFont() as contract:
                contract.importXML(fixture)
                self.assertNotIn('glyf', contract)
                self.assertNotIn('hmtx', contract)
                self.assertNotIn('maxp', contract)
                self.assertNotIn('fpgm', contract)

    def test_cff_identity_restores_absent_fields_and_public_attribution(self):
        class CFF:
            fontNames = ['PublicNamche-Regular']
            def __init__(self):
                self.topDictIndex = [SimpleNamespace(rawDict={'Copyright': 'New build text'},
                    Copyright='New build text', Notice='Build notice', Weight='Regular')]
            def __getitem__(self, name):
                return self.topDictIndex[0]
        cff = CFF()
        font = {'CFF ': SimpleNamespace(cff=cff)}
        identity = {'font_names': ['PublicNamche-Regular'],
                    'attributes': {'Notice': 'Public original and Namche attribution', 'Weight': 'Regular'}}
        finalize._apply_cff_identity(font, identity)
        top = cff.topDictIndex[0]
        self.assertEqual(top.Notice, 'Public original and Namche attribution')
        self.assertFalse(hasattr(top, 'Copyright'))
        self.assertNotIn('Copyright', top.rawDict)

    def test_only_unencoded_static_one_unit_advances_can_be_normalized(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            release, compiled = root/'old.ttf', root/'compiled.ttf'
            fixture, output = root/'contract.ttf.ttx', root/'new.ttf'
            make_font(release, 'PublicNamche')
            make_font(compiled, 'BuildIdentity', extra=True, advance_delta=1)
            finalize.capture_font(release, fixture)
            with self.assertRaisesRegex(ValueError, 'advance widths changed'):
                finalize.finalize_font(compiled, fixture, output)
            with self.assertRaisesRegex(ValueError, 'advance widths changed'):
                finalize.finalize_font(compiled, fixture, output, normalize_unencoded_advances=True)
            make_font(compiled, 'BuildIdentity', extra=True, advance_delta=1, advance_name='lig.helper')
            with self.assertRaisesRegex(ValueError, 'advance widths changed'):
                finalize.finalize_font(compiled, fixture, output)
            report = finalize.finalize_font(compiled, fixture, output, normalize_unencoded_advances=True)
            self.assertEqual(report['normalized_unencoded_advances'], {'lig.helper': [500, 501]})
            with TTFont(output) as font:
                self.assertEqual(font['hmtx']['lig.helper'][0], 500)
            make_font(compiled, 'BuildIdentity', extra=True, advance_delta=2, advance_name='lig.helper')
            with self.assertRaisesRegex(ValueError, 'advance widths changed'):
                finalize.finalize_font(compiled, fixture, output, normalize_unencoded_advances=True)


    def test_pruning_retains_new_component_dependencies(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            release, compiled, output = root/'old.ttf', root/'compiled.ttf', root/'new.ttf'
            fixture = root/'contract.ttf.ttx'
            make_font(release, 'PublicNamche')
            make_font(compiled, 'BuildIdentity', extra=True)
            with TTFont(compiled) as font:
                pen = TTGlyphPen(font['glyf'])
                pen.addComponent('new.helper', (1, 0, 0, 1, 0, 0))
                font['glyf']['u0041'] = pen.glyph()
                font.save(compiled)
            finalize.capture_font(release, fixture)
            report = finalize.finalize_font(compiled, fixture, output)
            with TTFont(output) as font:
                self.assertIn('new.helper', font.getGlyphOrder())
                self.assertEqual(font['glyf']['u0041'].components[0].glyphName, 'new.helper')
            self.assertEqual(report['pruned_unreachable_glyphs'], [])

    def test_static_cleanup_preserves_filled_outline_and_advances(self):
        from scripts.check_equal_ink import _filled_geos
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'font.ttf'
            make_font(path, 'PublicNamche')
            with TTFont(path) as font:
                pen = TTGlyphPen(font['glyf'])
                pen.moveTo((10, 0))
                pen.lineTo((10, 0))
                pen.qCurveTo((10, 0), (10, 0), (10, 0))
                pen.lineTo((200, 0))
                pen.lineTo((100, 300))
                pen.closePath()
                pen.moveTo((350, 350))
                pen.lineTo((351, 351))
                pen.lineTo((350, 350))
                pen.closePath()
                font['glyf']['u0041'] = pen.glyph()
                before, _ = _filled_geos(font.getGlyphSet(), 'u0041', 0.001)
                metrics = dict(font['hmtx'].metrics)
                changes = finalize._cleanup_static_geometry(font)
                after, _ = _filled_geos(font.getGlyphSet(), 'u0041', 0.001)
                self.assertEqual(before.symmetric_difference(after).area, 0)
                self.assertEqual(font['hmtx'].metrics, metrics)
                self.assertEqual(font['glyf']['u0041'].numberOfContours, 1)
                self.assertEqual(changes['u0041']['removed_collinear_contours'], 1)

    def test_source_roundtrip_rejects_geometry_changes_before_pinning_hashes(self):
        from scripts import build_sans_equal_ink as builder
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder)
            baseline = output/'fresh-compilation.ttf'
            make_font(baseline, 'PublicNamche')
            clean = output/'clean.json'
            clean.write_text(json.dumps({'source_commit': 'synthetic-design-input'}))

            def finalized(_compiled, _metadata, final, **_kwargs):
                for suffix in ('', '-Italic'):
                    name = f'NamcheShadowSans{suffix}[wght]'
                    (final/'variable').mkdir(parents=True, exist_ok=True)
                    (final/'webfonts').mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(baseline, final/'variable'/f'{name}.ttf')
                    (final/'webfonts'/f'{name}.woff2').write_bytes(b'synthetic webfont')

            def recovered(ttf, woff, source, _commit, _italic):
                source.mkdir(parents=True)
                manifest = {'outputs': {f'variable/{ttf.name}': 'not-pinned',
                                        f'webfonts/{woff.name}': 'not-pinned'}}
                (source/'provenance.json').write_text(json.dumps(manifest))

            def damaged_roundtrip(source, target):
                style = source.name.split('-')[-1]
                suffix = '-Italic' if style == 'Italic' else ''
                name = f'NamcheShadowSans{suffix}[wght].ttf'
                (target/'variable').mkdir(parents=True)
                with TTFont(baseline, recalcTimestamp=False) as font:
                    coordinates = font['glyf']['u0041'].coordinates
                    x, y = coordinates[0]
                    coordinates[0] = x+1, y
                    font.save(target/'variable'/name)

            with patch.object(builder, 'BASE', clean), \
                 patch('scripts.finalize_equal_ink.finalize_tree', side_effect=finalized), \
                 patch('scripts.recover_sans_production_source.recover', side_effect=recovered), \
                 patch('scripts.build_sans_open.build', side_effect=damaged_roundtrip):
                with self.assertRaisesRegex(ValueError, 'round trip changed glyf'):
                    builder.finalize(output)
            manifest = json.loads((output/'production-source/NamcheShadowSans-Upright/provenance.json').read_text())
            self.assertTrue(all(value == 'not-pinned' for value in manifest['outputs'].values()))


if __name__ == '__main__':
    unittest.main()
