"""Numerical geometry contracts for the issue #125 source recipe."""
import copy
import math
import json
from pathlib import Path
import unittest

import pathops

from scripts import equal_ink_corners as eq
from scripts.round_inner_corners import (
    add, sub, mul, norm, nodes_to_segments, segments_to_nodes,
    seg_length, MASTER_IDS,
)


def notch(theta, length=1000, curvature=0):
    half = math.radians(theta/2)
    x, y = length*math.sin(half), -200+length*math.cos(half)
    vertex, right, left = (0, -200), (x, y), (-x, y)
    points = [(-1500, -500), (1500, -500), (1500, y), right, vertex, left, (-1500, y)]
    segs = [("line", p, points[(i+1) % len(points)]) for i, p in enumerate(points)]
    if curvature:
        def mix(a, b, t):
            return add(a, mul(sub(b, a), t))
        u = norm(sub(vertex, right))
        v = norm(sub(left, vertex))
        c1 = add(mix(right, vertex, 1/3), mul((-u[1], u[0]), curvature))
        c2 = mix(right, vertex, 2/3)
        d1 = mix(vertex, left, 1/3)
        d2 = add(mix(vertex, left, 2/3), mul((-v[1], v[0]), -curvature))
        segs[3] = ("curve", right, c1, c2, vertex)
        segs[4] = ("curve", vertex, d1, d2, left)
    return segments_to_nodes(segs)


class EqualInkGeometryTest(unittest.TestCase):
    def assert_additive(self, original, rounded):
        old, new = eq._path(original), eq._path(rounded)
        loss = eq._op(old, new, pathops.PathOp.DIFFERENCE)
        self.assertLess(abs(loss.area), eq.AREA_TOLERANCE)
        return abs(eq._op(new, old, pathops.PathOp.DIFFERENCE).area)

    def test_rule_uses_measured_stem_and_category_caps(self):
        self.assertAlmostEqual(eq.r90_for_stem(32, True), 38.4)
        self.assertEqual(eq.r90_for_stem(96, True), 70)
        self.assertEqual(eq.r90_for_stem(190, True), 70)
        self.assertEqual(eq.r90_for_stem(96), 53)

    def test_straight_90_30_and_10_degree_joins_add_equal_ink(self):
        for theta in (90, 30, 10):
            with self.subTest(theta=theta):
                source = [notch(theta)]
                rounded, report = eq.round_compatible_contours([source]*3, [38.4, 70, 70])
                self.assertEqual(len(report), 1)
                types = [[node[2] for contour in m for node in contour] for m in rounded]
                self.assertEqual(types[0], types[1])
                self.assertEqual(types[1], types[2])
                self.assertEqual(types[0].count("c"), 2)
                self.assertEqual(len(rounded[0]), 2, "complete clean and rounded glyphs")
                self.assertEqual(rounded[0][0], source[0], 'base outline was trimmed')
                for master, radius in zip(rounded, [38.4, 70, 70]):
                    area = self.assert_additive(source, master)
                    self.assertAlmostEqual(area, eq.F90*radius*radius, delta=.03)

    def test_curved_acute_join_solves_actual_area(self):
        source = [notch(30, curvature=300)]
        rounded, report = eq.round_compatible_contours([source], [70])
        self.assertEqual(len(report), 1)
        actual = self.assert_additive(source, rounded[0])
        self.assertAlmostEqual(actual, eq.F90*70*70, delta=.01)
        # The tangent-angle formula is only a starting point: real curved sides
        # require a different radius to attain the same amount of added ink.
        theta = math.radians(30)
        angle_only = 70*math.sqrt(eq.F90/(1/math.tan(theta/2)-(math.pi-theta)/2))
        self.assertGreater(abs(report[0]["masters"][0]["radius"]-angle_only), .01)

    def test_impossible_pathops_local_area_uses_independent_geometry(self):
        from unittest.mock import patch
        source = [notch(90)]
        normalized = eq._normalize(source)
        base = eq._path(source)
        operation = eq._op
        impossible = eq._path([[(-10000,-10000,'l'),(10000,-10000,'l'),
                                (10000,10000,'l'),(-10000,10000,'l')]])
        def corrupt_added_area(left, right, kind):
            result = operation(left,right,kind)
            return impossible if kind == pathops.PathOp.DIFFERENCE and result.area > .01 else result
        diagnostic = {}
        with patch.object(eq,'_op',side_effect=corrupt_added_area):
            found = eq._solve(normalized,0,2,70,base,diagnostic)
        self.assertIsNotNone(found)
        self.assertEqual(diagnostic['local_area_backend'],'geos')
        self.assertGreater(diagnostic['pathops_impossible_area'],1e8)
        self.assertAlmostEqual(found.area,eq.F90*70*70,delta=.01)

    def test_obtuse_join_keeps_reference_radius(self):
        source = [notch(120)]
        rounded, report = eq.round_compatible_contours([source], [70])
        self.assertEqual(report[0]["masters"][0]["radius"], 70)
        self.assert_additive(source, rounded[0])

    def test_limited_flanks_cap_fill_before_45_percent(self):
        source = [notch(10, length=60)]
        rounded, report = eq.round_compatible_contours([source], [70])
        info = report[0]["masters"][0]
        self.assertTrue(info["capped"])
        self.assertLess(info["area"], info["target"])
        self.assert_additive(source, rounded[0])
        # The base is unchanged. The two arc contacts consume no more than
        # 45% of either original flank in the continuous rounded contour.
        self.assertEqual(rounded[0][0], source[0])
        original = eq._normalize(source)[0]
        join = report[0]['join']
        arcs = [s for s in nodes_to_segments(rounded[0][-1]) if s[0] == 'curve']
        vertex = original[join][-1]
        self.assertEqual(len(arcs), 2)
        self.assertLessEqual(math.dist(vertex, arcs[0][1]), .45*seg_length(original[join])+1e-5)
        self.assertLessEqual(math.dist(vertex, arcs[-1][-1]), .45*seg_length(original[(join+1)%len(original)])+1e-5)

    def test_winding_normalization_includes_counters(self):
        outer = [(-2000, -1000, 'l'), (2000, -1000, 'l'),
                 (2000, 1500, 'l'), (-2000, 1500, 'l')]
        inner = notch(30)
        # Input has the same winding for both contours; normalization must
        # identify and reverse the nested counter before selecting joins.
        rounded, report = eq.round_compatible_contours([[outer, inner]], [53])
        self.assertTrue(report)
        normalized = [segments_to_nodes(c) for c in eq._normalize([outer, inner])]
        self.assert_additive(normalized, rounded[0])
        self.assertEqual(eq._counter_count(eq._path(normalized)), 1)
        self.assertEqual(eq._counter_count(eq._path(rounded[0])), 1)
        self.assertTrue(eq._path([normalized[1]]).clockwise)

    def test_resolved_alignment_preserves_the_selected_segment_start(self):
        reference = [(0, 0, 'l'), (100, 0, 'l'), (110, 30, 'o'),
                     (110, 70, 'o'), (100, 100, 'c'), (0, 100, 'l')]
        segments = nodes_to_segments(reference)
        doubled = [tuple([segment[0], *[(2*x, 2*y) for x, y in segment[1:]]]) for segment in segments]
        rotated = doubled[2:]+doubled[:2]
        candidate = eq._nodes_preserving_segment_start(rotated)
        aligned, _ = eq._align_resolved_masters([[reference], [candidate]])
        first, second = [nodes_to_segments(master[0]) for master in aligned]
        self.assertEqual([s[0] for s in first], [s[0] for s in second])
        self.assertEqual(second[0][1], (0, 0))
        self.assertEqual(second, doubled)

    def test_resolver_removes_repeated_closing_point_without_changing_a_cubic(self):
        k = 4*(math.sqrt(2)-1)/3
        nodes = [(100, 0, 'l'), (100, 100*k, 'o'), (100*k, 100, 'o'), (0, 100, 'c'),
                 (-100*k, 100, 'o'), (-100, 100*k, 'o'), (-100, 0, 'c'),
                 (-100, -100*k, 'o'), (-100*k, -100, 'o'), (0, -100, 'c'),
                 (100*k, -100, 'o'), (100, -100*k, 'o'), (100, 0, 'c')]
        cleaned = eq._drop_duplicate_closure(nodes)
        self.assertEqual(len(cleaned), 12)
        self.assertEqual([s[0] for s in nodes_to_segments(cleaned)], ['curve']*4)
        self.assertEqual(eq._path([nodes]).area, eq._path([cleaned]).area)

    def test_compound_resolver_preserves_c_inside_a_ring(self):
        def circle(radius):
            k = 4*(math.sqrt(2)-1)/3
            points = [(radius, 0), (0, radius), (-radius, 0), (0, -radius)]
            segments = []
            for i, p in enumerate(points):
                q = points[(i+1) % 4]
                a = (p[0]-k*p[1], p[1]+k*p[0])
                b = (q[0]+k*q[1], q[1]-k*q[0])
                segments.append(('curve', p, a, b, q))
            return segments_to_nodes(segments)
        outer = circle(200)
        counter = segments_to_nodes(eq._reverse(nodes_to_segments(circle(160))))
        letter_c = [(x, y, 'l') for x, y in [(-80, -100), (80, -100), (80, -60),
                    (-40, -60), (-40, 60), (80, 60), (80, 100), (-80, 100)]]
        raw = [outer, counter, letter_c]
        snapshot = copy.deepcopy(raw)
        resolved = eq.resolve_clean_contours(raw)
        self.assertEqual(raw, snapshot)
        before, after = eq._path(raw), eq._path(resolved)
        self.assertLess(eq._op(before, after, pathops.PathOp.DIFFERENCE).area, .001)
        self.assertLess(eq._op(after, before, pathops.PathOp.DIFFERENCE).area, .001)
        ring = eq._path([outer, counter])
        self.assertGreater(after.area, ring.area + 10000)
        self.assertEqual(len(resolved), 3)
        self.assertEqual(eq._counter_count(after), 1)

    def test_additive_island_crossing_a_counter_preserves_source_winding(self):
        outer = [(0, 0, 'l'), (400, 0, 'l'), (400, 400, 'l'), (0, 400, 'l')]
        counter = [(100, 100, 'l'), (100, 300, 'l'), (300, 300, 'l'), (300, 100, 'l')]
        slash = [(150, 50, 'l'), (350, 250, 'l'), (325, 275, 'l'), (125, 75, 'l')]
        source = [outer, counter, slash]
        normalized = [segments_to_nodes(c) for c in eq._normalize(source)]
        self.assertFalse(eq._path([normalized[2]]).clockwise, 'black island became a white hole')
        rounded, report = eq.round_compatible_contours([source], [20])
        added = self.assert_additive(source, rounded[0])
        local = sum(r['masters'][0]['area'] for r in report if r['status'] == 'rounded')
        self.assertLessEqual(added, local + .05*len(report))
        self.assertEqual(eq._counter_count(eq._path(source)), eq._counter_count(eq._path(rounded[0])))

    def test_inactive_master_retains_compatible_degenerate_bridges(self):
        a, b = notch(30), notch(180)
        rounded, report = eq.round_compatible_contours([[a], [b]], [70, 70])
        self.assertTrue(report)
        self.assertEqual([n[2] for n in rounded[0][0]], [n[2] for n in rounded[1][0]])
        self.assert_additive([a], rounded[0])
        self.assert_additive([b], rounded[1])

    def test_incompatible_input_fails_instead_of_independent_rounding(self):
        with self.assertRaisesRegex(ValueError, 'incompatible'):
            eq.round_compatible_contours([[notch(30)], [notch(30, curvature=100)]], [70, 70])


class ActualMasterGeometryTest(unittest.TestCase):
    """Exercise real straight, acute and curved clean joins in all weights."""
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parents[1]
        cls.clean = json.loads((root / 'sources/equal-ink/clean-outlines.json').read_text())['styles']

    def test_real_upright_and_clean_italic_backgrounds(self):
        signature = lambda ms: [[[s[0] for s in nodes_to_segments(c)] for c in m] for m in ms]
        for style in ('Upright', '-Italic'):
            for name in ('K', 'a', 'n', 'A', 'H', 'E'):
                with self.subTest(style=style, glyph=name):
                    source = self.clean[style][name]['masters']
                    masters = [eq.resolve_clean_contours(source[mid]) for mid in MASTER_IDS.values()]
                    snapshot = copy.deepcopy(masters)
                    radii = [eq.r90_for_stem(stem, name.isupper()) for stem in (32, 96, 190)]
                    rounded, report = eq.round_compatible_contours(masters, radii)
                    self.assertEqual(masters, snapshot, 'rounding mutated clean source')
                    self.assertTrue(any(r['status'] == 'rounded' for r in report), report)
                    self.assertTrue(all(r.get("reason") == "subunit_fillet" for r in report if r["status"] == "skipped"), report)
                    self.assertEqual(signature(rounded)[0], signature(rounded)[1])
                    self.assertEqual(signature(rounded)[1], signature(rounded)[2])
                    for mi, (clean, final) in enumerate(zip(masters, rounded)):
                        # Clean data is already overlap-resolved and correctly
                        # wound. Never normalize the independent expected region:
                        # doing so would conceal a broken normalization routine.
                        old, new = eq._path(clean), eq._path(final)
                        loss = eq._op(old, new, pathops.PathOp.DIFFERENCE)
                        self.assertLess(abs(loss.area), eq.AREA_TOLERANCE)
                        added = abs(eq._op(new, old, pathops.PathOp.DIFFERENCE).area)
                        local_area = sum(r['masters'][mi]['area'] for r in report if r['status'] == 'rounded')
                        self.assertLessEqual(added, local_area + .05*len(report))
                        self.assertEqual(eq._counter_count(new), eq._counter_count(old))
                        if name == 'A':
                            self.assertEqual(eq._counter_count(old), 1)
                            self.assertEqual(eq._counter_count(new), 1)
                        self.assertTrue(math.isfinite(new.area))


    def test_raw_overlapping_zero_slash_and_near_tangent_brace_are_safe(self):
        for style, name in (('Upright', 'zerosuperior'), ('-Italic', 'zerosuperior'),
                            ('Upright', 'euro'), ('-Italic', 'braceleft')):
            with self.subTest(style=style, glyph=name):
                records = self.clean[style][name]['masters']
                source = [records[mid] for mid in MASTER_IDS.values()]
                # Deliberately do not resolve the raw overlapping zero slash:
                # that produces incompatible contour counts across masters.
                final, report = eq.round_compatible_contours(source, [38.4, 53, 53])
                for mi, (clean, rounded) in enumerate(zip(source, final)):
                    old, new = eq._path(clean), eq._path(rounded)
                    loss = eq._op(old, new, pathops.PathOp.DIFFERENCE)
                    self.assertLess(loss.area, eq.AREA_TOLERANCE)
                    added = eq._op(new, old, pathops.PathOp.DIFFERENCE).area
                    local = sum(r['masters'][mi]['area'] for r in report if r['status'] == 'rounded')
                    self.assertLessEqual(added, local + .05*max(1, len(report)))
                    self.assertEqual(eq._counter_count(old), eq._counter_count(new))


    def test_independent_source_verification_resolves_false_pathops_loss(self):
        source = list(self.clean['Upright']['euro']['masters'].values())
        # Stress the coincident-edge failure with the larger radius. PathOps
        # claims hundreds of lost square units; GEOS proves no material loss.
        rounded, report = eq.round_compatible_contours(source, [38.4, 70, 70])
        evidence = [eq._verify_source_geos(clean, final, i)
                    for i, (clean, final) in enumerate(zip(source, rounded))]
        self.assertTrue(all(v['residual_lost_area'] <= v['precision_bound'] for v in evidence))
        self.assertTrue(all(v['baseline_counters'] == v['candidate_counters'] for v in evidence))

    def test_independent_source_verification_refuses_material_loss_and_counter_closure(self):
        outer = [(0, 0, 'l'), (20, 0, 'l'), (20, 20, 'l'), (0, 20, 'l')]
        clipped = [(1, 0, 'l'), (20, 0, 'l'), (20, 20, 'l'), (1, 20, 'l')]
        counter = [(5, 5, 'l'), (5, 15, 'l'), (15, 15, 'l'), (15, 5, 'l')]
        with self.assertRaisesRegex(ValueError, 'GEOS confirms .* lost'):
            eq._verify_source_geos([outer], [clipped], 0)
        with self.assertRaisesRegex(ValueError, 'GEOS confirms changed counters'):
            eq._verify_source_geos([outer, counter], [outer], 0)


    def test_resolver_preserves_original_copyright_registered_a_and_notdef(self):
        import glyphsLib
        root = Path(__file__).resolve().parents[1]
        kinds = {'line': 'l', 'curve': 'c', 'offcurve': 'o'}
        for suffix in ('', '-Italic'):
            original = glyphsLib.GSFont(root/f'originals/geist/sources/Geist{suffix}.glyphspackage')
            for name in ('copyright', 'registered', 'A', 'H', '.notdef'):
                for master in original.masters:
                    with self.subTest(style=suffix, glyph=name, master=master.name):
                        layer = original.glyphs[name].layers[master.id]
                        raw = [[(float(n.position.x), float(n.position.y), kinds[n.type])
                                for n in p.nodes] for p in layer.paths]
                        snapshot = copy.deepcopy(raw)
                        resolved = eq.resolve_clean_contours(raw)
                        self.assertEqual(raw, snapshot)
                        before, after = eq._path(raw), eq._path(resolved)
                        self.assertLess(eq._op(before, after, pathops.PathOp.DIFFERENCE).area, .001)
                        self.assertLess(eq._op(after, before, pathops.PathOp.DIFFERENCE).area, .001)
                        self.assertEqual(eq._counter_count(before), eq._counter_count(after))
                        if name in ('copyright', 'registered'):
                            self.assertEqual(len(resolved), 3 if name == 'copyright' else 4)


    def test_italic_b_subunit_black_fillets_do_not_create_interpolated_holes(self):
        from scripts.check_equal_ink import _filled_geos, _geos_counters
        records = self.clean['-Italic']['B']['masters']
        masters = [records[mid] for mid in MASTER_IDS.values()]
        rounded, report = eq.round_compatible_contours(masters, [38.4, 70, 70])
        skipped = [r for r in report if r.get('reason') == 'subunit_fillet']
        self.assertEqual(len(skipped), 2)
        self.assertTrue(all(max(m['area'] for m in r['masters']) < 1 for r in skipped))

        class Glyph:
            width = 0
            def __init__(self, contours):
                self.contours = contours
            def draw(self, pen):
                for nodes in self.contours:
                    segs = nodes_to_segments(nodes)
                    pen.moveTo(segs[0][1])
                    for seg in segs:
                        if seg[0] == 'line':
                            pen.lineTo(seg[-1])
                        else:
                            pen.curveTo(*seg[2:])
                    pen.closePath()

        for weight in range(400, 901, 50):
            with self.subTest(weight=weight):
                t = (weight-400)/500
                interpolated = [[(a[0]+t*(b[0]-a[0]), a[1]+t*(b[1]-a[1]), a[2])
                                 for a, b in zip(regular, black)]
                                for regular, black in zip(rounded[1], rounded[2])]
                geometry, _ = _filled_geos({'B': Glyph(interpolated)}, 'B', .001)
                self.assertEqual(len(_geos_counters(geometry)), 2)


    def test_complete_glyph_union_preserves_curved_base_ink_between_masters(self):
        from scripts.check_equal_ink import _filled_geos, _geos_counters
        weights = (100, 400, 900)
        def interpolate(source, weight):
            low = 0 if weight <= 400 else 1
            t = (weight-weights[low])/(weights[low+1]-weights[low])
            return [[(a[0]+t*(b[0]-a[0]), a[1]+t*(b[1]-a[1]), a[2]) for a,b in zip(left,right)]
                    for left,right in zip(source[low],source[low+1])]
        cases = [('Upright','at',600,650,53), ('-Italic','at',350,400,53),
                 ('Upright','eight',350,400,70), ('Upright','three',500,550,70),
                 ('Upright','braceright',200,300,53)]
        for style, name, lower, upper, radius in cases:
            with self.subTest(style=style,glyph=name):
                original = [self.clean[style][name]['masters'][mid] for mid in MASTER_IDS.values()]
                pair = [interpolate(original,w) for w in (lower,upper)]
                rounded,_ = eq.round_compatible_contours(pair,[radius,radius])
                self.assertEqual(rounded[0][:len(pair[0])],pair[0])
                self.assertEqual(rounded[1][:len(pair[1])],pair[1])
                for t in (0,.25,.5,.75,1):
                    mix = lambda values:[[((1-t)*a[0]+t*b[0],(1-t)*a[1]+t*b[1],a[2])
                        for a,b in zip(left,right)] for left,right in zip(values[0],values[1])]
                    base,_ = _filled_geos({'g':eq._NodeGlyph(mix(pair))},'g',.001)
                    final,_ = _filled_geos({'g':eq._NodeGlyph(mix(rounded))},'g',.001)
                    self.assertLess(base.difference(final).area,1e-7)
                    self.assertEqual(len(_geos_counters(base)),len(_geos_counters(final)))

    def test_brace_subunit_members_are_inactive_without_discarding_heavier_joins(self):
        originals = [self.clean['Upright']['braceleft']['masters'][mid] for mid in MASTER_IDS.values()]
        def at(weight):
            low = 0 if weight <= 400 else 1
            lower,upper = ((100,400),(400,900))[low]
            t = (weight-lower)/(upper-lower)
            return [[((1-t)*a[0]+t*b[0],(1-t)*a[1]+t*b[1],a[2])
                     for a,b in zip(left,right)]
                    for left,right in zip(originals[low],originals[low+1])]
        source = [at(w) for w in (200,250,300,900)]
        rounded,report = eq.round_compatible_contours(source,[53]*4)
        for join in (3,4):
            item = next(r for r in report if r['join'] == join)
            self.assertEqual(item['status'],'rounded')
            self.assertTrue(all(m.get('inactive') for m in item['masters'][:3]))
            self.assertGreaterEqual(item['masters'][-1]['area'],1)
        for base,final in zip(source,rounded):
            self.assertEqual(final[:len(base)],base)
            self.assertEqual(len(final),2*len(base))

    def test_compiled_inactive_slots_preserve_counters_at_every_quarter_step(self):
        from fontTools.designspaceLib import DesignSpaceDocument, AxisDescriptor, SourceDescriptor
        from ufoLib2 import Font
        from ufo2ft import compileVariableTTF
        from scripts.check_equal_ink import _filled_geos, _geos_counters
        weights = list(range(100,901,50))
        for style,name,expected in [('Upright','zerosuperior',2),('-Italic','sterling',0),('-Italic','a',1)]:
            original = [self.clean[style][name]['masters'][mid] for mid in MASTER_IDS.values()]
            def at(weight):
                low = 0 if weight <= 400 else 1
                lower,upper = ((100,400),(400,900))[low]
                t = (weight-lower)/(upper-lower)
                return [[((1-t)*a[0]+t*b[0],(1-t)*a[1]+t*b[1],a[2])
                         for a,b in zip(left,right)] for left,right in zip(original[low],original[low+1])]
            clean = [at(w) for w in weights]
            stems = [32+(96-32)*(w-100)/300 if w <= 400 else 96+(190-96)*(w-400)/500 for w in weights]
            rounded,_ = eq.round_compatible_contours(clean,[eq.r90_for_stem(stem) for stem in stems])
            document = DesignSpaceDocument()
            document.addAxis(AxisDescriptor(name='Weight',tag='wght',minimum=100,default=400,maximum=900))
            for weight,paths in zip(weights,rounded):
                ufo = Font()
                ufo.info.familyName='Counter Regression'
                ufo.info.styleName=f'Weight{weight}'
                ufo.info.unitsPerEm=1000
                glyph = ufo.newGlyph(name)
                glyph.width=1000
                eq._NodeGlyph(paths).draw(glyph.getPen())
                document.addSource(SourceDescriptor(name=f'weight{weight}',font=ufo,location={'Weight':weight}))
            font = compileVariableTTF(document,optimizeGvar=False,removeOverlaps=False,
                                      cubicConversionError=.0001,featureWriters=[],useProductionNames=False)
            for weight in range(100,901,25):
                with self.subTest(style=style,glyph=name,weight=weight):
                    shape,_ = _filled_geos(font.getGlyphSet(location={'wght':weight}),name,.001)
                    self.assertEqual(len(_geos_counters(shape)),expected)

    def test_static_ordinal_inactive_corner_does_not_enclose_a_new_counter(self):
        from ufoLib2 import Font
        from ufo2ft import compileTTF, compileOTF
        from scripts.check_equal_ink import _filled_geos, _geos_counters
        original = [self.clean['-Italic']['ordfeminine']['masters'][mid] for mid in MASTER_IDS.values()]
        bold = [[(.4*a[0]+.6*b[0],.4*a[1]+.6*b[1],a[2]) for a,b in zip(left,right)]
                for left,right in zip(original[1],original[2])]
        source = [original[1],bold,original[2]]
        rounded,_ = eq.round_compatible_contours(source,[53]*3)
        for compiler in (compileTTF,compileOTF):
            with self.subTest(format=compiler.__name__):
                ufo = Font()
                ufo.info.familyName='Ordinal Regression'
                ufo.info.styleName='BoldItalic'
                ufo.info.unitsPerEm=1000
                glyph = ufo.newGlyph('ordfeminine')
                glyph.width=1000
                # Named static export keeps the complete solved contour set.
                eq._NodeGlyph(rounded[1][len(bold):]).draw(glyph.getPen())
                options = dict(removeOverlaps=True,featureWriters=[],useProductionNames=False)
                if compiler is compileTTF:
                    options['cubicConversionError'] = .0001
                font = compiler(ufo,**options)
                shape,_ = _filled_geos(font.getGlyphSet(),'ordfeminine',.001)
                self.assertEqual(len(_geos_counters(shape)),1)

    def test_semantic_b_waist_rounds_actual_filled_curve_intersection(self):
        from scripts.check_equal_ink import _filled_geos,_geos_counters,_polygon_parts
        from shapely.geometry import LineString
        from shapely.geometry.polygon import orient
        source = [self.clean['-Italic']['B']['masters'][mid] for mid in MASTER_IDS.values()]
        rounded,report = eq.round_compatible_contours(source,[38.4,70,70],semantic_b_waist=True)
        semantic = next(r for r in report if r.get('semantic') == 'B_waist')
        self.assertAlmostEqual(semantic['masters'][-1]['connector_length'],math.sqrt(5))
        for mi,(clean,final) in enumerate(zip(source,rounded)):
            self.assertAlmostEqual(semantic['masters'][mi]['area'],semantic['masters'][mi]['target'],delta=.02)
            self.assertEqual(len(final), 2*len(clean))
            self.assertEqual(len(nodes_to_segments(final[-1])),9)
            old,_ = _filled_geos({'B':eq._NodeGlyph(clean)},'B',.001)
            new,_ = _filled_geos({'B':eq._NodeGlyph(final)},'B',.001)
            self.assertLess(old.difference(new).area,1e-7)
            self.assertEqual(len(_geos_counters(new)),2)
            def waist_turn(geometry):
                polygon = orient(max(_polygon_parts(geometry),key=lambda p:p.area),sign=1)
                points = list(polygon.exterior.coords)
                line = LineString(points)
                x0,y0,x1,y1 = polygon.bounds
                distance,sharpest = 0.,0.
                for a,p in zip(points,points[1:]):
                    distance += math.dist(a,p)
                    if p[0] <= x0+.45*(x1-x0) or not y0+.35*(y1-y0) < p[1] < y0+.65*(y1-y0):continue
                    before = line.interpolate((distance-.5)%line.length)
                    after = line.interpolate((distance+.5)%line.length)
                    u,v = (p[0]-before.x,p[1]-before.y),(after.x-p[0],after.y-p[1])
                    sharpest = max(sharpest,-math.degrees(math.atan2(eq.cross(u,v),eq.dot(u,v))))
                return sharpest
            self.assertGreater(waist_turn(old),100)
            self.assertLess(waist_turn(new),15)


if __name__ == '__main__':
    unittest.main()
