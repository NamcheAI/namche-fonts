#!/usr/bin/env python3
"""Fail CI on real language-shaping regressions in Fontspector reports."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


SHAPE_CHECK = "googlefonts/glyphsets/shape_languages"
SOFT_DOTTED_CHECK = "soft_dotted"
AUXILIARY_MISSING_PREFIX = (
    "The following auxiliary characters are missing from the font:"
)
# Explicit auxiliary characters outside the pinned GF Latin Core scope (#118).
# Missing Core characters and actual shaping failures remain blocking.
ALLOWED_AUXILIARY_OMISSIONS = frozenset(
    "Ǿ ǿ Ĕ ĕ Ĭ ĭ Ŀ ŀ Ŏ ŏ Ĳ ĳ Ȟ ȟ Ʒ ʒ Ǯ ǯ Ǔ ǔ ſ ʻ Ĩ ĩ Ŋ ŋ Ō ō Ŗ ŗ Ŝ ŝ Ţ ţ Ŧ ŧ Ũ ũ Ŭ ŭ Ǎ ǎ Ǥ ǥ Ǧ ǧ Ǩ ǩ Ẽ ẽ".split()
)
SHAPE_WARNING_CODE = "warning-language-shaping"


def checks_for(result: dict) -> dict[str, dict]:
    return {
        check["check_id"]: check
        for section in result.values()
        for check in section
        if "check_id" in check
    }


def parse_auxiliary_warning(message: str) -> tuple[set[str], list[str]]:
    omissions: set[str] = set()
    errors: list[str] = []
    for line in message.splitlines():
        value = line.strip()
        if not value:
            continue
        if value == "Warning language shaping:":
            continue
        if not value.startswith("|"):
            errors.append(f"unrecognized shaping message line: {value!r}")
            continue
        cells = value.split("|")
        message_cell = cells[1].strip() if len(cells) > 2 else ""
        if (
            message_cell == "Message"
            or message_cell == "Auxiliary orthography codepoints:"
            or (message_cell and set(message_cell) == {"-"})
        ):
            continue
        if not message_cell.startswith(AUXILIARY_MISSING_PREFIX):
            errors.append(
                f"unrecognized shaping message entry: {message_cell!r}"
            )
            continue
        missing = message_cell.removeprefix(AUXILIARY_MISSING_PREFIX).strip()
        if not missing:
            errors.append(
                f"could not parse auxiliary omission from {message_cell!r}"
            )
            continue
        omissions.update(missing.strip("`").split())
    if not omissions:
        errors.append("warning contains no auxiliary omissions")
    return omissions, errors


def validate_inventory(
    checked_fonts: set[Path], font_dirs: list[Path]
) -> list[str]:
    expected_fonts = {
        path.resolve()
        for font_dir in font_dirs
        for path in font_dir.rglob("*.ttf")
    }
    errors: list[str] = []
    for path in sorted(expected_fonts - checked_fonts):
        errors.append(f"missing Fontspector result for expected font: {path}")
    for path in sorted(checked_fonts - expected_fonts):
        errors.append(f"unexpected font in Fontspector reports: {path}")
    return errors


def validate_report(path: Path) -> tuple[set[Path], list[str]]:
    data = json.loads(path.read_text())
    errors: list[str] = []
    checked: set[Path] = set()
    for font_path, result in data.get("results", {}).items():
        if Path(font_path).suffix.lower() not in {".ttf", ".otf", ".woff2"}:
            continue
        if "NamcheShadowSans" not in font_path and "NamcheShadowMono" not in font_path:
            continue
        checked.add(Path(font_path).resolve())
        checks = checks_for(result)

        soft_dotted = checks.get(SOFT_DOTTED_CHECK)
        if soft_dotted is None:
            errors.append(f"{font_path}: missing {SOFT_DOTTED_CHECK} result")
        elif soft_dotted.get("worst_status") != "PASS":
            errors.append(
                f"{font_path}: {SOFT_DOTTED_CHECK} is "
                f"{soft_dotted.get('worst_status')} instead of PASS"
            )

        shape = checks.get(SHAPE_CHECK)
        if shape is None:
            errors.append(f"{font_path}: missing {SHAPE_CHECK} result")
            continue
        shape_status = shape.get("worst_status")
        if shape_status == "PASS":
            continue
        if shape_status != "WARN":
            errors.append(
                f"{font_path}: {SHAPE_CHECK} is {shape_status} instead of PASS/WARN"
            )
            continue
        reported_auxiliary = set()
        subresults = shape.get("subresults", [])
        if not subresults:
            errors.append(f"{font_path}: shaping warning has no subresults")
        for subresult in subresults:
            if (
                subresult.get("severity") != "WARN"
                or subresult.get("code") != SHAPE_WARNING_CODE
            ):
                errors.append(
                    f"{font_path}: unrecognized shaping subresult: "
                    f"severity={subresult.get('severity')!r}, "
                    f"code={subresult.get('code')!r}"
                )
                continue
            omissions, message_errors = parse_auxiliary_warning(
                subresult.get("message", "")
            )
            reported_auxiliary.update(omissions)
            errors.extend(f"{font_path}: {error}" for error in message_errors)
        allowed_auxiliary = ALLOWED_AUXILIARY_OMISSIONS
        unexpected_auxiliary = sorted(reported_auxiliary - allowed_auxiliary)
        if unexpected_auxiliary:
            errors.append(
                f"{font_path}: undocumented auxiliary omissions: "
                f"{' '.join(unexpected_auxiliary)}"
            )

    return checked, errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--font-dir",
        action="append",
        default=[],
        type=Path,
        help="directory whose TTF inventory must be present in the reports",
    )
    parser.add_argument("reports", nargs="+", type=Path)
    args = parser.parse_args()

    checked: set[Path] = set()
    errors: list[str] = []
    for report in args.reports:
        if not report.is_file():
            errors.append(f"missing Fontspector report: {report}")
            continue
        report_checked, report_errors = validate_report(report)
        checked.update(report_checked)
        errors.extend(report_errors)
    if args.font_dir:
        errors.extend(validate_inventory(checked, args.font_dir))

    if errors:
        print("\n".join(errors))
        return 1
    if not checked:
        print("No Namche Shadow Sans or Mono Fontspector results found")
        return 1
    print(
        f"Validated language shaping in {len(checked)} font files; "
        "retained warnings are auxiliary omissions only"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
