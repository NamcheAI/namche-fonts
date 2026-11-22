"""Geometry regressions for check_equal_ink's directional loss measurement."""

from pathlib import Path
import sys
import unittest

from fontTools.pens.recordingPen import RecordingPen

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from check_equal_ink import compare_glyphs, _FlattenPen, _filled_geos


class FakeGlyph:
    width = 500

    def __init__(self, commands):
        self.commands = commands

    def draw(self, pen):
        for operation, arguments in self.commands:
            getattr(pen, operation)(*arguments)


class FakeGlyphSet(dict):
    pass


def rectangle(x0, y0, x1, y1, clockwise=False):
    points = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    if clockwise:
        points.reverse()
    pen = RecordingPen()
    pen.moveTo(points[0])
    for point in points[1:]:
        pen.lineTo(point)
    pen.closePath()
    return pen.value


class FilledOutlineDistanceTest(unittest.TestCase):
    def test_hidden_patch_edges_do_not_change_visible_outline_distance(self):
        from check_sans_variable import _outline_points, _outline_distance
        from types import SimpleNamespace
        union = FakeGlyphSet({'shape': FakeGlyph(rectangle(0, 0, 200, 100))})
        overlapping = FakeGlyphSet({'shape': FakeGlyph(
            rectangle(0, 0, 200, 100)+rectangle(30, 30, 170, 70))})
        first = SimpleNamespace(getGlyphSet=lambda: union)
        second = SimpleNamespace(getGlyphSet=lambda: overlapping)
        self.assertEqual(_outline_distance(_outline_points(first, 'shape'),
                                           _outline_points(second, 'shape')), 0)


class StaticFormatSelectionTest(unittest.TestCase):
    def setUp(self):
        import tempfile
        import check_equal_ink as validator
        self.validator = validator
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.baseline, self.candidate = self.root/'baseline', self.root/'candidate'
        for directory in (self.baseline,self.candidate):
            for style,filename in validator.VF_FILENAMES.items():
                path = directory/'variable'/filename
                path.parent.mkdir(parents=True,exist_ok=True)
                path.touch()
                for extension in ('ttf','otf'):
                    path = validator._static_path(directory,style,400,extension)
                    path.parent.mkdir(parents=True,exist_ok=True)
                    path.touch()

    def test_default_does_not_require_or_compare_otfs(self):
        from unittest.mock import patch
        for directory in (self.baseline,self.candidate):
            for path in (directory/'otf').iterdir():path.unlink()
        with patch.object(self.validator,'_compare_pair',return_value=([],[])) as compare:
            report = self.validator.validate(self.baseline,self.candidate,[400])
        self.assertFalse(report['includes_otf_static_fonts'])
        self.assertEqual(compare.call_count,4)
        self.assertTrue(all(call.args[0].suffix == '.ttf' for call in compare.call_args_list))

    def test_cli_flag_compares_matching_otfs_as_static_fonts(self):
        from unittest.mock import patch
        import json
        output = self.root/'report.json'
        with patch.object(self.validator,'_compare_pair',return_value=([],[])) as compare:
            result = self.validator.main(['--baseline-dir',str(self.baseline),
                '--candidate-dir',str(self.candidate),'--output',str(output),
                '--weights','400','--include-otf-statics'])
        self.assertEqual(result,0)
        self.assertTrue(json.loads(output.read_text())['includes_otf_static_fonts'])
        otfs = [call for call in compare.call_args_list if call.args[0].suffix == '.otf']
        self.assertEqual(len(otfs),2)
        for call in otfs:
            self.assertEqual(call.args[0],self.validator._static_path(self.baseline,call.args[2],400,'otf'))
            self.assertEqual(call.args[1],self.validator._static_path(self.candidate,call.args[2],400,'otf'))
            self.assertEqual(call.args[4],'static-otf')
            self.assertFalse(call.kwargs['baseline_variable'])
            self.assertFalse(call.kwargs['candidate_variable'])

    def test_optional_otf_pass_refuses_a_missing_clean_baseline(self):
        from unittest.mock import patch
        missing = self.validator._static_path(self.baseline,'upright',400,'otf')
        missing.unlink()
        with patch.object(self.validator,'_compare_pair',return_value=([],[])):
            with self.assertRaisesRegex(FileNotFoundError,'missing clean static OTF baseline'):
                self.validator.validate(self.baseline,self.candidate,[400],include_otf_statics=True)


class EqualInkGeometryTests(unittest.TestCase):
    def test_lost_ink_is_detected_when_added_ink_offsets_total_area(self):
        baseline_commands = rectangle(0, 0, 10, 10)
        candidate_commands = rectangle(2, 0, 10, 10) + rectangle(20, 0, 22, 10)
        baseline = FakeGlyphSet(A=FakeGlyph(baseline_commands))
        candidate = FakeGlyphSet(A=FakeGlyph(candidate_commands))

        metrics, baseline_width, candidate_width = compare_glyphs(baseline, candidate, "A")

        self.assertEqual(metrics.baseline_area, metrics.candidate_area)
        self.assertEqual(metrics.lost_area, 20)
        self.assertEqual(metrics.added_area, 20)
        self.assertEqual(
            metrics.baseline_area - metrics.candidate_area,
            metrics.lost_area - metrics.added_area,
        )
        self.assertEqual(baseline_width, candidate_width)

    def test_counter_closure_removes_boolean_hole(self):
        baseline_commands = rectangle(0, 0, 10, 10) + rectangle(2, 2, 8, 8, clockwise=True)
        candidate_commands = rectangle(0, 0, 10, 10)
        baseline = FakeGlyphSet(O=FakeGlyph(baseline_commands))
        candidate = FakeGlyphSet(O=FakeGlyph(candidate_commands))

        metrics, _, _ = compare_glyphs(baseline, candidate, "O")

        self.assertEqual(metrics.baseline_counters, 1)
        self.assertEqual(metrics.candidate_counters, 0)
        self.assertEqual(metrics.counter_area_ratios, (0.0,))
        self.assertEqual(metrics.unmatched_candidate_counters, 0)
        self.assertEqual(metrics.lost_area, 0)
        self.assertEqual(metrics.added_area, 36)

    def test_closing_one_counter_and_opening_another_does_not_pass_matching(self):
        baseline_commands = rectangle(0, 0, 20, 20) + rectangle(2, 2, 8, 8, clockwise=True)
        candidate_commands = rectangle(0, 0, 20, 20) + rectangle(12, 12, 18, 18, clockwise=True)
        baseline = FakeGlyphSet(O=FakeGlyph(baseline_commands))
        candidate = FakeGlyphSet(O=FakeGlyph(candidate_commands))

        metrics, _, _ = compare_glyphs(baseline, candidate, "O")

        self.assertEqual(metrics.baseline_counters, 1)
        self.assertEqual(metrics.candidate_counters, 1)
        self.assertEqual(metrics.counter_area_ratios, (0.0,))
        self.assertEqual(metrics.unmatched_candidate_counters, 1)

    def test_outline_distance_allowance_only_removes_narrow_gap_loss(self):
        baseline = FakeGlyphSet(A=FakeGlyph(rectangle(0, 0, 20, 5)))
        candidate = FakeGlyphSet(
            A=FakeGlyph(rectangle(0, 0, 9, 5) + rectangle(11, 0, 20, 5))
        )

        metrics, _, _ = compare_glyphs(
            baseline, candidate, "A", max_outline_loss_distance=1.0
        )

        self.assertEqual(metrics.lost_area, 10)
        self.assertEqual(metrics.residual_lost_area, 0)

    def test_outline_distance_allowance_does_not_hide_a_removed_island(self):
        baseline = FakeGlyphSet(
            A=FakeGlyph(rectangle(0, 0, 10, 10) + rectangle(20, 0, 22, 10))
        )
        candidate = FakeGlyphSet(A=FakeGlyph(rectangle(0, 0, 10, 10)))

        metrics, _, _ = compare_glyphs(
            baseline, candidate, "A", max_outline_loss_distance=2.0
        )

        self.assertEqual(metrics.lost_area, 20)
        self.assertEqual(metrics.residual_lost_area, 20)


    def test_nested_black_islands_and_depth_three_holes_use_nonzero_fill(self):
        commands = (rectangle(0, 0, 20, 20) + rectangle(2, 2, 18, 18, clockwise=True)
                    + rectangle(5, 5, 15, 15) + rectangle(7, 7, 13, 13, clockwise=True))
        source = FakeGlyphSet(R=FakeGlyph(commands))
        metrics, _, _ = compare_glyphs(source, source, 'R')
        self.assertEqual(metrics.baseline_area, 208)
        self.assertEqual(metrics.baseline_counters, 2)
        self.assertEqual(metrics.counter_area_ratios, (1.0, 1.0))
        self.assertEqual(metrics.lost_area, 0)
        self.assertEqual(metrics.added_area, 0)
        self.assertEqual(metrics.geometry_backend, 'geos')

    def test_self_intersections_and_additive_crossing_bars_preserve_winding(self):
        bow = [('moveTo', ((0, 0),)), ('lineTo', ((10, 10),)),
               ('lineTo', ((0, 10),)), ('lineTo', ((10, 0),)), ('closePath', ())]
        source = FakeGlyphSet(X=FakeGlyph(bow))
        geometry, _ = _filled_geos(source, 'X', .01)
        self.assertEqual(geometry.area, 50)
        crossing = FakeGlyphSet(X=FakeGlyph(rectangle(0, 0, 20, 20)
                    + rectangle(2, 2, 18, 18, clockwise=True) + rectangle(0, 9, 20, 11)))
        geometry, _ = _filled_geos(crossing, 'X', .01)
        self.assertEqual(geometry.area, 176)
        metrics, _, _ = compare_glyphs(crossing, crossing, 'X')
        self.assertEqual(metrics.baseline_counters, 2)
        self.assertEqual(metrics.lost_area, 0)

    def test_quadratic_flattening_records_a_geometric_error_bound(self):
        commands = [('moveTo', ((0, 0),)), ('qCurveTo', ((50, 100), (100, 0))), ('closePath', ())]
        source = FakeGlyphSet(Q=FakeGlyph(commands))
        metrics, _, _ = compare_glyphs(source, source, 'Q')
        self.assertLessEqual(metrics.maximum_flattened_curve_deviation, .01)
        self.assertLessEqual(abs(metrics.baseline_area-10000/3), metrics.baseline_flattening_area_bound)
        self.assertLessEqual(metrics.area_conservation_error, metrics.area_conservation_tolerance)
        from shapely.geometry import LineString, Point
        pen = _FlattenPen(.01)
        source['Q'].draw(pen)
        outline = LineString(pen.contours[0][:-1])
        for index in range(1001):
            t = index/1000
            actual = Point(100*t, 200*t*(1-t))
            self.assertLessEqual(outline.distance(actual), .01+1e-12)

    def test_cubic_loop_flattening_and_directional_area_conservation(self):
        commands = [('moveTo', ((0, 0),)), ('curveTo', ((100, 200), (-100, 200), (0, 0))), ('closePath', ())]
        baseline = FakeGlyphSet(Q=FakeGlyph(commands))
        candidate = FakeGlyphSet(Q=FakeGlyph(commands + rectangle(20, 0, 40, 20)))
        metrics, _, _ = compare_glyphs(baseline, candidate, 'Q')
        self.assertGreater(metrics.baseline_area, 0)
        self.assertEqual(metrics.lost_area, 0)
        self.assertGreater(metrics.added_area, 0)
        self.assertLessEqual(metrics.maximum_flattened_curve_deviation, .01)
        self.assertLessEqual(metrics.area_conservation_error, metrics.area_conservation_tolerance)

    def test_sub_millifont_unit_square_counter_noise_is_explicitly_ignored(self):
        commands = rectangle(0, 0, 20, 20) + rectangle(5, 5, 5.01, 5.01, clockwise=True)
        source = FakeGlyphSet(O=FakeGlyph(commands))
        metrics, _, _ = compare_glyphs(source, source, 'O')
        self.assertEqual(metrics.baseline_counters, 0)
        self.assertAlmostEqual(metrics.baseline_area, 400-.0001)



if __name__ == "__main__":
    unittest.main()
