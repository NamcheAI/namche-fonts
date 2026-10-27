import json
from pathlib import Path
import tempfile
import unittest

from scripts.check_language_shaping import validate_inventory, validate_report


def report(
    message: str,
    soft_dotted_status: str = "PASS",
    font_path: str = "fonts/NamcheShadowSans/ttf/NamcheShadowSans-Regular.ttf",
    shape_status: str = "WARN",
    shape_code: str = "warning-language-shaping",
) -> dict:
    return {
        "results": {
            font_path: {
                "Google Fonts": [
                    {
                        "check_id": "soft_dotted",
                        "worst_status": soft_dotted_status,
                    },
                    {
                        "check_id": "googlefonts/glyphsets/shape_languages",
                        "worst_status": shape_status,
                        "subresults": [
                            {
                                "message": message,
                                "severity": "WARN",
                                "code": shape_code,
                            }
                        ],
                    },
                ]
            }
        }
    }


class LanguageShapingReportTest(unittest.TestCase):
    def validate(self, data: dict) -> tuple[int, list[str]]:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "report.json"
            path.write_text(json.dumps(data))
            checked, errors = validate_report(path)
            return len(checked), errors

    def test_accepts_documented_auxiliary_omissions(self) -> None:
        message = "\n".join(
            [
                "Warning language shaping:",
                "| Auxiliary orthography codepoints: | * da_Latn (Danish) |",
                "| The following auxiliary characters are missing from the font: Ǿ | |",
                "| The following auxiliary characters are missing from the font: ǿ | |",
            ]
        )

        checked, errors = self.validate(report(message))

        self.assertEqual(checked, 1)
        self.assertEqual(errors, [])

    def test_rejects_undocumented_auxiliary_omission(self) -> None:
        message = (
            "| The following auxiliary characters are missing from the font: Å | |"
        )

        _, errors = self.validate(report(message))

        self.assertEqual(
            errors,
            [
                "fonts/NamcheShadowSans/ttf/NamcheShadowSans-Regular.ttf: "
                "undocumented auxiliary omissions: Å"
            ],
        )

    def test_rejects_obsolete_cyrillic_exception(self) -> None:
        message = (
            "| The following auxiliary characters are missing from the font: ѫ | |"
        )
        variable_path = (
            "fonts/NamcheShadowSans/variable/NamcheShadowSans[wght].ttf"
        )

        _, variable_errors = self.validate(
            report(message, font_path=variable_path)
        )
        _, static_errors = self.validate(report(message))

        self.assertEqual(len(variable_errors), 1)
        self.assertEqual(len(static_errors), 1)
        self.assertIn("undocumented auxiliary omissions: ѫ", static_errors[0])

    def test_rejects_real_shaping_warning(self) -> None:
        _, errors = self.validate(report("Shaper failed to attach acutecomb"))

        self.assertGreaterEqual(len(errors), 1)
        self.assertIn("unrecognized shaping message line", errors[0])

    def test_accepts_shape_pass_without_warning_message(self) -> None:
        _, errors = self.validate(report("", shape_status="PASS"))

        self.assertEqual(errors, [])

    def test_rejects_unknown_warning_code(self) -> None:
        _, errors = self.validate(
            report("Unexpected attachment failure", shape_code="new-warning")
        )

        self.assertEqual(len(errors), 1)
        self.assertIn("unrecognized shaping subresult", errors[0])

    def test_rejects_soft_dotted_failure(self) -> None:
        _, errors = self.validate(
            report("", soft_dotted_status="WARN", shape_status="PASS")
        )

        self.assertEqual(len(errors), 1)
        self.assertIn("soft_dotted is WARN instead of PASS", errors[0])

    def test_rejects_incomplete_font_inventory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            font_dir = Path(directory)
            present = font_dir / "Present.ttf"
            missing = font_dir / "Missing.ttf"
            present.touch()
            missing.touch()

            errors = validate_inventory({present.resolve()}, [font_dir])

        self.assertEqual(len(errors), 1)
        self.assertIn("missing Fontspector result for expected font", errors[0])
        self.assertIn("Missing.ttf", errors[0])


if __name__ == "__main__":
    unittest.main()
