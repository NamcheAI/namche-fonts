"""Release regression checks for the isolated, pinned open-build environment."""
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
import build_sans_open as builder
from build_googlefonts import rename_font


class OpenBuildTests(unittest.TestCase):
    def test_rejects_modified_committed_release(self):
        with tempfile.TemporaryDirectory() as tmp:
            release = Path(tmp)
            for relative in builder.FILES:
                target = release / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(builder.RELEASE / relative, target)
            with (release / builder.FILES[0]).open('ab') as handle:
                handle.write(b'changed')
            with self.assertRaisesRegex(ValueError, 'committed release differs'):
                builder.check(builder.SOURCE, release)

    def test_rejects_point_rotation_with_unchanged_flags(self):
        ufo = builder.Font.open(builder.SOURCE / 'Upright.ufo')
        points = ufo['H'].contours[0].points
        points[:] = points[10:] + points[:10]
        with tempfile.TemporaryDirectory() as tmp, patch.object(builder.Font, 'open', return_value=ufo):
            with self.assertRaisesRegex(ValueError, 'point order or contour boundaries changed'):
                builder.build(builder.SOURCE, Path(tmp))

    def test_rejects_point_type_changes_before_applying_indexed_deltas(self):
        ufo = builder.Font.open(builder.SOURCE / 'Upright.ufo')
        # Turning a contour endpoint into a control point invalidates gvar's
        # point-index contract even though the point count did not change.
        point = ufo['H'].contours[0].points[0]
        point.type = None if point.type is not None else 'line'
        with tempfile.TemporaryDirectory() as tmp, patch.object(builder.Font, 'open', return_value=ufo):
            with self.assertRaisesRegex(ValueError, 'point topology changed'):
                builder.build(builder.SOURCE, Path(tmp))

    def test_rejects_italic_point_rotation(self):
        ufo = builder.Font.open(builder.ITALIC_SOURCE / 'Italic.ufo')
        points = ufo['H'].contours[0].points
        points[:] = points[1:] + points[:1]
        with tempfile.TemporaryDirectory() as tmp, patch.object(builder.Font, 'open', return_value=ufo):
            with self.assertRaisesRegex(ValueError, 'point order or contour boundaries changed'):
                builder.build(builder.ITALIC_SOURCE, Path(tmp))

    def test_submission_rejects_existing_overlong_italic_family(self):
        source = builder.RELEASE / 'variable/NamcheShadowSans-Italic[wght].ttf'
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, 'exceed 32 characters'):
                rename_font(source, Path(tmp) / 'font.ttf', 'Namche Shadow Sans')

    def test_submission_preserves_italic_styles_and_longest_name_fits(self):
        source = builder.RELEASE / 'variable/NamcheShadowSans-Italic[wght].ttf'
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / 'font.ttf'
            rename_font(source, target, 'Namche Shadow')
            font = builder.TTFont(target)
            styles = [font['name'].getDebugName(i.subfamilyNameID) for i in font['fvar'].instances]
            self.assertIn('ExtraLight Italic', styles)
            self.assertEqual(max(len('Namche Shadow ' + s) for s in styles), 31)


if __name__ == '__main__':
    unittest.main()
