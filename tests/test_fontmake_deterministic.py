"""Cross-platform compiler selection and a real half-grid curve regression."""
import json
import importlib.metadata
import os
from pathlib import Path
import subprocess
import sys
import unittest

from fontTools.misc.roundTools import otRound
from scripts.fontmake_deterministic import (
    CU2QU_SOURCE_SHA256, FONTTOOLS_VERSION, converter_info, fontmake_environment, load_python_cu2qu,
)


# Bold Aogonek's existing cubic: compiled ARM conversion gives the first
# quadratic control y=-94.50000000000003, which rounds to -95 instead of -94.
HALF_GRID_CURVE = [(649.2, -102.8), (649.2, -86.2), (661.2, -66.2), (680.8, -39.6)]
EXPECTED_QUADRATIC = [(649, -103), (649, -94), (657, -75), (671, -53), (681, -40)]


class CompilerPinTest(unittest.TestCase):
    def test_build_refuses_an_unreviewed_converter_version(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        wrong = SimpleNamespace(version='0.0',locate_file=lambda name:name)
        with patch('scripts.fontmake_deterministic.importlib.metadata.distribution',return_value=wrong):
            with self.assertRaisesRegex(RuntimeError,'Expected fontTools 4.60.1'):
                converter_info()


@unittest.skipUnless(importlib.metadata.version('fonttools') == FONTTOOLS_VERSION,
                     'requires the full pinned fontTools compiler environment')
class DeterministicFontmakeTest(unittest.TestCase):
    def test_real_half_grid_curve_has_stable_integer_controls(self):
        converter = load_python_cu2qu()
        result = converter.curve_to_quadratic(HALF_GRID_CURVE, .1)
        self.assertFalse(converter.COMPILED)
        self.assertEqual(result[1][1], -94.5)
        self.assertEqual([tuple(map(otRound, p)) for p in result], EXPECTED_QUADRATIC)

    def test_compatible_conversion_uses_the_same_half_grid_rule(self):
        converter = load_python_cu2qu()
        curves = converter.curves_to_quadratic([HALF_GRID_CURVE, HALF_GRID_CURVE], [.1, .1])
        self.assertEqual([[tuple(map(otRound, p)) for p in curve] for curve in curves],
                         [EXPECTED_QUADRATIC, EXPECTED_QUADRATIC])

    def test_loading_python_source_does_not_modify_parent_converter(self):
        import fontTools.cu2qu
        original = fontTools.cu2qu.curve_to_quadratic
        load_python_cu2qu()
        self.assertIs(fontTools.cu2qu.curve_to_quadratic, original)

    def test_scoped_launcher_selects_python_in_a_real_child_process(self):
        environment = dict(os.environ)
        original = dict(environment)
        with fontmake_environment(environment) as child:
            launcher = Path(child['PATH'].split(os.pathsep)[0])/'fontmake'
            self.assertTrue(launcher.is_file())
            result = subprocess.run(['fontmake', '--namche-cu2qu-info'], env=child,
                                    check=True, capture_output=True, text=True)
            info = json.loads(result.stdout)
            self.assertEqual(info['fonttools_version'], FONTTOOLS_VERSION)
            self.assertEqual(info['source_sha256'], CU2QU_SOURCE_SHA256)
            self.assertFalse(info['compiled'])
            self.assertEqual(info['selected_module'], 'fontTools.cu2qu._namche_python')
        self.assertEqual(environment, original)
        self.assertFalse(launcher.exists())

    def test_all_static_and_variable_pen_imports_select_python(self):
        code = '''
from scripts.fontmake_deterministic import activate_python_cu2qu
converter = activate_python_cu2qu()
import fontTools.cu2qu as package
import fontTools.cu2qu.ufo as ufo
import fontTools.pens.cu2quPen as pen
assert package.curve_to_quadratic is converter.curve_to_quadratic
assert package.curves_to_quadratic is converter.curves_to_quadratic
assert ufo.curves_to_quadratic is converter.curves_to_quadratic
assert pen.curve_to_quadratic is converter.curve_to_quadratic
assert pen.curves_to_quadratic is converter.curves_to_quadratic
'''
        subprocess.run([sys.executable, '-c', code], check=True,
                       cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True)


if __name__ == '__main__':
    unittest.main()
