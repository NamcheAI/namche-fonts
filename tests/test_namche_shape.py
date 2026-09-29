import unittest

from fontTools.pens.recordingPen import RecordingPen

from scripts import namche_shape as ns


def recording(path):
    pen = RecordingPen()
    path.draw(pen)
    return pen.value


class NamcheShapeGeneratorTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.grids = ns.load_grids()

    def testEveryStyleIsDeterministic(self):
        grid = self.grids["a"]
        for style in ns.STYLES:
            first = recording(ns.base_outline(style, grid, {}))
            second = recording(ns.base_outline(style, grid, {}))
            self.assertEqual(first, second, style)

    def testEveryExportedGridGlyphHasInkInEveryStyle(self):
        names = [n for n, g in self.grids.items() if g.cells and not n.startswith("pixel")]
        self.assertGreater(len(names), 200)
        for style in ns.STYLES:
            for name in names:
                with self.subTest(style=style, glyph=name):
                    self.assertTrue(recording(ns.base_outline(style, self.grids[name], {})))

    def testMetaballOverridesForceAndBlockLinks(self):
        cells = self.grids["l"].cells
        link = ns.orthogonal_links(cells)[0]
        key = ns.link_key(*link)
        on = ns.choose_links("Metaball", "l", cells, 0.0, {"Metaball": {"l": {"link": [key]}}})
        off = ns.choose_links("Metaball", "l", cells, 1.0, {"Metaball": {"l": {"unlink": [key]}}})
        self.assertIn(link, on)
        self.assertNotIn(link, off)

    def testSkeletonTraceKeepsEachComponentConnected(self):
        for name in ("A", "N", "a", "g", "three", "at"):
            cells = self.grids[name].cells
            links, _ = ns.skeleton_links(name, cells, {})
            parent = {c: c for c in cells}

            def find(c):
                while parent[c] != c:
                    c = parent[c]
                return c

            for a, b in links:
                parent[find(a)] = find(b)
            groups = {find(c) for c in cells}
            self.assertEqual(len(groups), len(ns._components(cells)), name)

    def testOriginOverrideFixesACellShape(self):
        cells = {(0, 0)}
        square = recording(ns.draw_origin("x", cells, {"Origin": {"x": {"cells": {"0,0": "square"}}}}))
        quarter = recording(ns.draw_origin("x", cells, {"Origin": {"x": {"cells": {"0,0": "quarter"}}}}))
        self.assertNotEqual(square, quarter)
        self.assertFalse(any(op == "curveTo" for op, _ in square))


if __name__ == "__main__":
    unittest.main()
