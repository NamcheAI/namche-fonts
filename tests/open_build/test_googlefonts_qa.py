"""Ensure candidate baselines cannot turn incomplete or new failures green."""
import sys
from pathlib import Path
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from check_googlefonts_qa import REQUIRED, validate, normalize


class CandidateQATests(unittest.TestCase):
    def setUp(self):
        self.checks = [dict(check_id=key, worst_status='PASS', subresults=[{'severity': 'PASS'}])
                       for key, count in REQUIRED.items() for _ in range(count)]
        self.checks.append(dict(check_id='googlefonts/metadata/subsets_correct',
                               worst_status='PASS', subresults=[{'severity': 'PASS'}]))
        self.report = {'results': {'family': {'checks': self.checks}}}
        self.finding = dict(check='googlefonts/tofu', code='missing', severity='FAIL', message='Known missing mark')
        self.baseline = {'findings': [self.finding]}

    def add_failure(self, severity='FAIL', message='Known missing mark'):
        self.checks.append(dict(check_id='googlefonts/tofu', worst_status=severity,
                               subresults=[dict(severity=severity, code='missing', message=message)]))

    def test_baseline_is_not_submission_approval(self):
        self.add_failure()
        self.assertFalse(validate(self.report, self.baseline)['submission_ready'])

    def test_new_failure_is_blocking(self):
        self.add_failure(message='New missing mark')
        with self.assertRaisesRegex(ValueError, 'Unexpected'):
            validate(self.report, self.baseline)

    def test_error_is_blocking_even_if_baselined(self):
        self.add_failure(severity='ERROR')
        self.finding['severity'] = 'ERROR'
        with self.assertRaisesRegex(ValueError, 'Unexpected'):
            validate(self.report, self.baseline)

    def test_missing_required_check_is_blocking(self):
        self.checks.pop(0)
        with self.assertRaisesRegex(ValueError, 'Required'):
            validate(self.report, self.baseline)

    def test_duplicated_failure_is_blocking(self):
        self.add_failure()
        self.add_failure()
        with self.assertRaisesRegex(ValueError, 'Unexpected'):
            validate(self.report, self.baseline)

    def test_skipped_known_failure_is_blocking(self):
        self.checks.append(dict(check_id="googlefonts/tofu", worst_status="SKIP",
                               subresults=[dict(severity="SKIP", code="network-error")]))
        with self.assertRaisesRegex(ValueError, "skipped or missing"):
            validate(self.report, self.baseline)

    def test_subset_order_is_normalized_but_message_is_preserved(self):
        self.assertEqual(normalize('any of the subsets latin, cyrillic:\nU+0302'),
                         'any of the subsets cyrillic, latin:\nU+0302')
