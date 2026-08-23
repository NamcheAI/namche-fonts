from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
CSS_FILES = (
    ROOT / "documentation/cdn/fonts.css",
    ROOT / "documentation/cdn/fonts-latin.css",
)


class CdnCssTests(unittest.TestCase):
    def test_every_local_source_exists_in_the_release_tree(self) -> None:
        for css_path in CSS_FILES:
            with self.subTest(css=css_path.name):
                sources = re.findall(r'url\("\./([^"?]+)"\)', css_path.read_text())
                self.assertGreater(len(sources), 0)
                missing = [
                    source for source in sources if not (ROOT / "fonts" / source).is_file()
                ]
                self.assertEqual(missing, [])

    def test_all_faces_define_display_policy(self) -> None:
        for css_path in CSS_FILES:
            with self.subTest(css=css_path.name):
                css = css_path.read_text()
                self.assertEqual(css.count("@font-face"), css.count("font-display: swap"))

    def test_latin_faces_are_physically_subsetted_and_ranged(self) -> None:
        css = (ROOT / "documentation/cdn/fonts-latin.css").read_text()
        face_count = css.count("@font-face")
        self.assertEqual(face_count, css.count("unicode-range:"))
        sources = re.findall(r'url\("\./([^"?]+)"\)', css)
        self.assertTrue(all(source.endswith("-latin.woff2") for source in sources))


if __name__ == "__main__":
    unittest.main()
