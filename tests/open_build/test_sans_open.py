"""Release regression checks for the isolated, pinned open-build environment."""
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
import build_sans_open as builder


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


if __name__ == '__main__':
    unittest.main()
