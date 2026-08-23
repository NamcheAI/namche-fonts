#!/usr/bin/env python3
"""Build deterministic Latin WOFF2 subsets from the approved full webfonts."""

from __future__ import annotations

import argparse
import re
import shutil
from pathlib import Path

from fontTools.subset import Options, Subsetter
from fontTools.ttLib import TTFont
from fontTools.ttLib.tables.otBase import USE_HARFBUZZ_REPACKER


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_UNICODE_FILE = ROOT / "sources" / "subsets" / "latin.txt"
SUBSET_NAME = "latin"
UNICODE_RANGE_RE = re.compile(
    r"^U\+([0-9A-Fa-f]{1,6})(?:-([0-9A-Fa-f]{1,6}))?$"
)


def read_unicode_ranges(path: Path) -> tuple[set[int], str]:
    codepoints: set[int] = set()
    css_ranges: list[str] = []

    for line_number, raw_line in enumerate(path.read_text().splitlines(), start=1):
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue
        match = UNICODE_RANGE_RE.fullmatch(line)
        if not match:
            raise ValueError(f"{path}:{line_number}: invalid Unicode range {line!r}")
        start = int(match.group(1), 16)
        end = int(match.group(2), 16) if match.group(2) else start
        if end < start or end > 0x10FFFF:
            raise ValueError(f"{path}:{line_number}: invalid Unicode interval {line!r}")
        codepoints.update(range(start, end + 1))
        css_ranges.append(line.upper())

    if not codepoints:
        raise ValueError(f"{path}: no Unicode ranges found")
    return codepoints, ", ".join(css_ranges)


def unicode_codepoints(font: TTFont) -> set[int]:
    return {
        codepoint
        for table in font["cmap"].tables
        if table.isUnicode()
        for codepoint in table.cmap
    }


def subset_path(source: Path) -> Path:
    return source.parent / "subsets" / f"{source.stem}-{SUBSET_NAME}.woff2"


def discover_webfonts(root: Path, layout: str) -> list[Path]:
    pattern = "*/webfonts/*.woff2" if layout == "release" else "*/*.woff2"
    return sorted(path for path in root.glob(pattern) if path.is_file())


def subset_webfont(source: Path, destination: Path, codepoints: set[int]) -> None:
    font = TTFont(source, recalcTimestamp=False)
    options = Options()
    options.layout_features = ["*"]
    options.name_IDs = ["*"]
    options.name_languages = ["*"]
    options.name_legacy = True
    options.notdef_outline = True
    # Do not make binary output depend on whether an optional HarfBuzz repacker
    # happens to be installed in the caller's Python environment.
    options.harfbuzz_repacker = False
    # FontTools cannot subset the OpenType meta table itself. Preserve it, then
    # narrow its script declarations to the subset's actual Latin contract.
    if "meta" not in options.no_subset_tables:
        options.no_subset_tables.append("meta")

    subsetter = Subsetter(options=options)
    subsetter.populate(unicodes=codepoints)
    subsetter.subset(font)

    if "meta" in font:
        font["meta"].data["dlng"] = "Latn"
        font["meta"].data["slng"] = "Latn"

    destination.parent.mkdir(parents=True, exist_ok=True)
    font.flavor = "woff2"
    font.cfg[USE_HARFBUZZ_REPACKER] = options.harfbuzz_repacker
    font.save(destination, reorderTables=False)


def build_subsets(root: Path, layout: str, unicode_file: Path) -> list[Path]:
    codepoints, _ = read_unicode_ranges(unicode_file)
    sources = discover_webfonts(root, layout)
    if not sources:
        raise FileNotFoundError(f"No {layout} WOFF2 files found below {root}")

    subset_directories = {source.parent / "subsets" for source in sources}
    for directory in subset_directories:
        if directory.exists():
            shutil.rmtree(directory)

    outputs: list[Path] = []
    for source in sources:
        destination = subset_path(source)
        subset_webfont(source, destination, codepoints)

        original = TTFont(source, lazy=True)
        subset = TTFont(destination, lazy=True)
        expected = unicode_codepoints(original) & codepoints
        actual = unicode_codepoints(subset)
        if actual != expected:
            missing = sorted(expected - actual)
            unexpected = sorted(actual - expected)
            raise RuntimeError(
                f"{destination}: cmap mismatch; missing={missing}, unexpected={unexpected}"
            )
        if destination.stat().st_size >= source.stat().st_size:
            raise RuntimeError(
                f"{destination}: subset is not smaller than {source} "
                f"({destination.stat().st_size} >= {source.stat().st_size})"
            )

        outputs.append(destination)
        reduction = 1 - destination.stat().st_size / source.stat().st_size
        print(
            f"Built {destination}: {source.stat().st_size:,} -> "
            f"{destination.stat().st_size:,} bytes ({reduction:.0%} smaller)"
        )

    return outputs


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--layout", choices=("release", "package"), required=True)
    parser.add_argument("--unicode-file", type=Path, default=DEFAULT_UNICODE_FILE)
    return parser.parse_args()


def main() -> None:
    args = parse_arguments()
    build_subsets(args.root.resolve(), args.layout, args.unicode_file.resolve())


if __name__ == "__main__":
    main()
