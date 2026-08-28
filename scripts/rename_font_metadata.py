#!/usr/bin/env python3
"""Rewrite Geist binary metadata for the Namche Shadow Sans derivative families.

The outlines and metrics are intentionally left untouched. This script only
updates naming, attribution, and CFF metadata in committed or freshly built
OTF, TTF, and WOFF2 files.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import re
import sys

from fontTools.ttLib import TTFont


FAMILIES = {
    "NamcheShadowSans": ("Namche Shadow Sans", "NamcheShadowSans"),
    "NamcheShadowMono": ("Namche Shadow Mono", "NamcheShadowMono"),
    "NamcheShadowPixel": ("Namche Shadow Pixel", "NamcheShadowPixel"),
    "namche-shadow-sans": ("Namche Shadow Sans", "NamcheShadowSans"),
    "namche-shadow-mono": ("Namche Shadow Mono", "NamcheShadowMono"),
    "namche-shadow-pixel": ("Namche Shadow Pixel", "NamcheShadowPixel"),
}
FONT_SUFFIXES = {".otf", ".ttf", ".woff2"}
VENDOR_ID = "NMCH"
WWS_BIT = 1 << 8
PIXEL_FAMILY = "Namche Shadow Pixel"
FAMILY_LANGUAGE_TAGS = {
    "Namche Shadow Sans": {"dlng": "Latn", "slng": "Latn,Cyrl"},
    "Namche Shadow Mono": {"dlng": "Latn", "slng": "Latn,Cyrl"},
    "Namche Shadow Pixel": {"dlng": "Latn", "slng": "Latn"},
}
LATIN_SUBSET_LANGUAGE_TAGS = {"dlng": "Latn", "slng": "Latn"}
VARIABLE_INSTANCE_NAME_ALIASES = {
    "Namche Shadow Mono": {
        "ExtraLight Italic": "XLight Italic",
        "SemiBold Italic": "SemiBd Italic",
        "ExtraBold Italic": "XBold Italic",
    },
}
PROJECT_URL = "https://github.com/NamcheAI/namche-fonts"
NAMCHE_COPYRIGHT = (
    "Copyright 2026 The Namche Shadow Project Authors "
    "(https://github.com/NamcheAI/namche-fonts)"
)
GEIST_COPYRIGHT = (
    "Copyright 2024 The Geist Project Authors "
    "(https://github.com/vercel/geist-font)"
)
# Google Fonts expects the "Project Authors" form; legal parties are listed
# in AUTHORS.txt, and the design credit lives in name ID 9.
COPYRIGHT = f"{NAMCHE_COPYRIGHT}. {GEIST_COPYRIGHT}"


def family_for(path: Path) -> tuple[str, str]:
    for part in path.parts:
        if part in FAMILIES:
            return FAMILIES[part]
    raise ValueError(f"cannot infer Namche family from {path}")


def replace_family_name(value: str, human: str, compact: str) -> str:
    if human == "Namche Shadow Sans":
        # Early Namche binaries used the suite name as the Sans family name.
        # Match only the bare legacy name so this remains idempotent and never
        # turns an already-correct family into "Namche Shadow Sans Sans".
        value = re.sub(r"\bNamche Shadow(?! (?:Sans|Mono|Pixel))", human, value)
        value = re.sub(r"\bNamcheShadow(?!Sans|Mono|Pixel)", compact, value)
    replacements = (
        ("Geist Pixel", human),
        ("GeistPixel", compact),
        ("Geist Mono", human),
        ("GeistMono", compact),
        ("Geist Sans", human),
        ("GeistSans", compact),
        ("Geist", human),
    )
    for old, new in replacements:
        value = value.replace(old, new)
    return value


def replace_postscript_name(value: str, compact: str) -> str:
    if compact == "NamcheShadowSans":
        value = re.sub(r"\bNamcheShadow(?!Sans|Mono|Pixel)", compact, value)
    for old in ("GeistPixel", "GeistMono", "GeistSans", "Geist"):
        if old in value:
            return value.replace(old, compact)
    return value.replace(" ", "")


def rewrite_name_table(font: TTFont, human: str, compact: str) -> None:
    for record in font["name"].names:
        try:
            value = record.toUnicode()
        except UnicodeDecodeError:
            continue

        if record.nameID == 0:
            value = COPYRIGHT
        elif record.nameID == 8:
            value = value.replace("Namche AI; based on ", "")
            if not value.startswith("BTLG Holding GmbH; based on "):
                value = f"BTLG Holding GmbH; based on {value}"
        elif record.nameID == 9:
            value = value.replace("Michael Marte (ruhm)", "Michael Marte (Ruhm GmbH)")
            if "Michael Marte" not in value:
                value = f"Michael Marte (Ruhm GmbH); {value}"
        elif record.nameID == 11:
            value = PROJECT_URL
        elif record.nameID in {6, 25}:
            value = replace_postscript_name(value, compact)
        else:
            value = replace_family_name(value, human, compact)

        record.string = value.encode(record.getEncoding(), errors="replace")

    aliases = VARIABLE_INSTANCE_NAME_ALIASES.get(human, {})
    if "fvar" in font and aliases:
        names = font["name"]
        for instance in font["fvar"].instances:
            current = names.getDebugName(instance.subfamilyNameID) or ""
            alias = aliases.get(current)
            if not alias:
                continue
            for record in names.names:
                if record.nameID == instance.subfamilyNameID:
                    record.string = alias.encode(
                        record.getEncoding(), errors="replace"
                    )


def rewrite_cff(font: TTFont, human: str, compact: str) -> None:
    if "CFF " not in font:
        return

    cff = font["CFF "].cff
    cff.fontNames[:] = [replace_postscript_name(name, compact) for name in cff.fontNames]
    for top_dict in cff.topDictIndex:
        if hasattr(top_dict, "FamilyName"):
            top_dict.FamilyName = replace_family_name(top_dict.FamilyName, human, compact)
        if hasattr(top_dict, "FullName"):
            top_dict.FullName = replace_family_name(top_dict.FullName, human, compact)


def copy_legacy_names_to_wws(font: TTFont) -> None:
    names = font["name"]
    names.removeNames(nameID=21)
    names.removeNames(nameID=22)
    for source_id, target_id in ((1, 21), (2, 22)):
        for record in list(names.names):
            if record.nameID != source_id:
                continue
            names.setName(
                record.toUnicode(),
                target_id,
                record.platformID,
                record.platEncID,
                record.langID,
            )


def rewrite_opentype_metadata(font: TTFont, human: str) -> None:
    if "OS/2" in font:
        if font["OS/2"].version < 4:
            raise ValueError(
                f"{human} requires OS/2 version 4 or later"
            )
        font["OS/2"].achVendID = VENDOR_ID
        if human == PIXEL_FAMILY:
            font["OS/2"].fsSelection &= ~WWS_BIT
            copy_legacy_names_to_wws(font)
        else:
            font["OS/2"].fsSelection |= WWS_BIT
            font["name"].removeNames(nameID=21)
            font["name"].removeNames(nameID=22)
    language_tags = FAMILY_LANGUAGE_TAGS.get(human)
    if language_tags:
        if "meta" not in font:
            raise ValueError(f"{human} font is missing its meta table")
        font["meta"].data.update(language_tags)


def language_tags_for_path(path: Path, human: str) -> dict[str, str] | None:
    if "subsets" in path.parts and path.stem.endswith("-latin"):
        return LATIN_SUBSET_LANGUAGE_TAGS
    return FAMILY_LANGUAGE_TAGS.get(human)


# fonts/Geist and its npm copy are byte-faithful vendored upstream binaries
# (scripts/vendor_geist.py); their Geist metadata must stay untouched.
VENDORED_UPSTREAM_DIRECTORIES = {"Geist", "geist"}


def font_files(root: Path) -> list[Path]:
    if root.is_file():
        return [root]
    return sorted(
        path
        for path in root.rglob("*")
        if path.suffix.lower() in FONT_SUFFIXES
        and VENDORED_UPSTREAM_DIRECTORIES.isdisjoint(path.parts)
    )


def rewrite(path: Path) -> None:
    human, compact = family_for(path)
    font = TTFont(path, recalcTimestamp=False)
    rewrite_name_table(font, human, compact)
    rewrite_cff(font, human, compact)
    rewrite_opentype_metadata(font, human)
    language_tags = language_tags_for_path(path, human)
    if language_tags:
        font["meta"].data.update(language_tags)
    font.save(path, reorderTables=False)
    font.close()


def check(path: Path) -> list[str]:
    human, compact = family_for(path)
    font = TTFont(path, lazy=True)
    values = []
    errors = []
    for record in font["name"].names:
        try:
            value = record.toUnicode()
        except UnicodeDecodeError:
            continue
        values.append((record.nameID, value))
        if "Geist" in value and record.nameID != 0:
            errors.append(f"{path}: name ID {record.nameID} still contains Geist: {value!r}")
    family_values = [value for name_id, value in values if name_id in {1, 4, 6, 16, 25}]
    if not family_values or not all(
        human in value or compact in value for value in family_values
    ):
        errors.append(
            f"{path}: expected family {human!r} in every family/full/PostScript name; "
            f"found {family_values!r}"
        )
    if not any("Michael Marte" in value for name_id, value in values if name_id == 9):
        errors.append(f"{path}: designer credit for Michael Marte is missing")
    if "fvar" in font:
        family = (
            font["name"].getBestFamilyName()
            or font["name"].getDebugName(1)
            or ""
        )
        instance_styles = set()
        for instance in font["fvar"].instances:
            style = font["name"].getDebugName(instance.subfamilyNameID) or ""
            instance_styles.add(style)
            combined = f"{family} {style}"
            if len(combined) > 32:
                errors.append(
                    f"{path}: variable instance name exceeds 32 characters: "
                    f"{combined!r}"
                )
        aliases = VARIABLE_INSTANCE_NAME_ALIASES.get(human, {})
        used_aliases = set(aliases.values()) & instance_styles
        if used_aliases and "STAT" in font:
            axis_value_array = font["STAT"].table.AxisValueArray
            axis_values = (
                axis_value_array.AxisValue
                if axis_value_array is not None
                else []
            )
            stat_names = {
                font["name"].getDebugName(axis_value.ValueNameID)
                for axis_value in axis_values
            }
            full_stat_styles = {
                style.removesuffix(" Italic")
                for style, alias in aliases.items()
                if alias in used_aliases
            }
            missing = sorted(full_stat_styles - stat_names)
            if missing:
                errors.append(
                    f"{path}: full public STAT style names are missing: {missing!r}"
                )
    copyright_values = [value for name_id, value in values if name_id == 0]
    if not any(NAMCHE_COPYRIGHT in value for value in copyright_values):
        errors.append(f"{path}: Namche Shadow project copyright notice is missing")
    if not any(GEIST_COPYRIGHT in value for value in copyright_values):
        errors.append(f"{path}: original Geist copyright notice is missing")
    if "OS/2" not in font or font["OS/2"].achVendID != VENDOR_ID:
        actual_vendor = font["OS/2"].achVendID if "OS/2" in font else "<missing>"
        errors.append(
            f"{path}: expected OS/2 vendor ID {VENDOR_ID!r}; found {actual_vendor!r}"
        )
    if "OS/2" in font and font["OS/2"].version < 4:
        errors.append(
            f"{path}: expected OS/2 version 4 or later; "
            f"found {font['OS/2'].version}"
        )
    wws_names = sorted(
        {record.nameID for record in font["name"].names if record.nameID in {21, 22}}
    )
    has_wws_bit = "OS/2" in font and bool(font["OS/2"].fsSelection & WWS_BIT)
    if human == PIXEL_FAMILY:
        if has_wws_bit:
            errors.append(f"{path}: Pixel's custom shape styles require WWS bit 8 clear")
        if wws_names != [21, 22]:
            errors.append(
                f"{path}: Pixel requires WWS name IDs 21/22; found {wws_names!r}"
            )
        for legacy_id, wws_id in ((1, 21), (2, 22)):
            legacy_records = {
                (record.platformID, record.platEncID, record.langID, record.toUnicode())
                for record in font["name"].names
                if record.nameID == legacy_id
            }
            wws_records = {
                (record.platformID, record.platEncID, record.langID, record.toUnicode())
                for record in font["name"].names
                if record.nameID == wws_id
            }
            if legacy_records != wws_records:
                errors.append(
                    f"{path}: Pixel name ID {wws_id} must match legacy name ID "
                    f"{legacy_id}; found {wws_records!r}, "
                    f"expected {legacy_records!r}"
                )
    else:
        if not has_wws_bit:
            actual_selection = (
                font["OS/2"].fsSelection if "OS/2" in font else "<missing>"
            )
            errors.append(
                f"{path}: expected OS/2 fsSelection WWS bit 8; "
                f"found {actual_selection!r}"
            )
        if wws_names:
            errors.append(
                f"{path}: WWS bit 8 is set, so name IDs 21/22 must be absent; "
                f"found {wws_names!r}"
            )
    expected_tags = language_tags_for_path(path, human)
    if expected_tags:
        actual_tags = font["meta"].data if "meta" in font else {}
        for tag, expected in expected_tags.items():
            if actual_tags.get(tag) != expected:
                errors.append(
                    f"{path}: expected meta {tag}={expected!r}; "
                    f"found {actual_tags.get(tag)!r}"
                )
    font.close()
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", type=Path, default=Path("fonts"))
    parser.add_argument("--check", action="store_true", help="validate without changing files")
    args = parser.parse_args()

    files = font_files(args.root)
    if not files:
        parser.error(f"no font files found below {args.root}")

    if args.check:
        errors = [error for path in files for error in check(path)]
        if errors:
            print("\n".join(errors), file=sys.stderr)
            return 1
        print(f"Validated {len(files)} Namche Shadow font files")
        return 0

    for path in files:
        rewrite(path)
    print(f"Rewrote metadata in {len(files)} font files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
