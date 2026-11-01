"""Reject unsupported edits before compiling reconstructed masters."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

from fontTools.designspaceLib import AxisDescriptor, DesignSpaceDocument, SourceDescriptor
from ufoLib2 import Font
from ufoLib2.objects import Component

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from reconstruct_sans_masters import build_reconstructed


class ReconstructedMasterTests(unittest.TestCase):
    def assert_edit_rejected(self, edit, message):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp)
            document = DesignSpaceDocument()
            axis = AxisDescriptor()
            axis.name, axis.tag = 'Weight', 'wght'
            axis.minimum, axis.default, axis.maximum = 100, 400, 900
            document.addAxis(axis)
            for weight in (400, 100):
                master = Font()
                glyph = master.newGlyph('space')
                master.glyphOrder = ['space']
                glyph.width = 500
                glyph.lib['org.namche.phantomPoints'] = [[0, 0], [500, 0], [0, 0], [0, 0]]
                if weight == 100:
                    edit(glyph)
                filename = f'{weight}.ufo'
                master.save(source / filename)
                descriptor = SourceDescriptor()
                descriptor.filename = filename
                descriptor.location = {'Weight': weight}
                document.addSource(descriptor)
            document.write(source / 'Sans.designspace')
            (source / 'provenance.json').write_text('{}')
            (source / 'point-order.json').write_text(json.dumps({'space': []}))
            with self.assertRaisesRegex(ValueError, message):
                build_reconstructed(source, source / 'output')
            self.assertFalse((source / 'output').exists())

    def test_rejects_nondefault_width_edit(self):
        self.assert_edit_rejected(lambda glyph: setattr(glyph, 'width', 520),
                                  'edited width needs a metric variation migration')

    def test_rejects_nondefault_added_component(self):
        self.assert_edit_rejected(lambda glyph: glyph.components.append(Component('H')),
                                  'cannot contain components')
