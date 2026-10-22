"""Semantic URL checks must protect credits and reject real repository drift."""
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from check_googlefonts_links import validate_description
from build_googlefonts import CONFIG


class CandidateLinksTests(unittest.TestCase):
    def setUp(self):
        self.description = (CONFIG / 'DESCRIPTION.en_us.html').read_text()

    def test_real_html_and_designer_profile_are_valid(self):
        self.assertIn('https://github.com/fizzybubbele', validate_description(self.description))

    def test_real_repository_mismatch_is_rejected(self):
        with self.assertRaises(ValueError):
            validate_description(self.description.replace('NamcheAI/namche-fonts', 'wrong/repo'))

    def test_missing_designer_credit_is_rejected(self):
        with self.assertRaises(ValueError):
            validate_description(self.description.replace('https://github.com/fizzybubbele', 'https://example.com'))

    def test_extra_unrelated_repository_is_rejected(self):
        with self.assertRaises(ValueError):
            validate_description(self.description + '<a href="https://github.com/wrong/repo">source</a>')

    def test_normal_url_forms_are_accepted(self):
        text = self.description.replace('https://github.com/NamcheAI/namche-fonts',
                                        'https://github.com/NamcheAI/namche-fonts.git/')
        self.assertTrue(validate_description(text))
