#!/usr/bin/env python3
"""Merge outline-only corrections into the committed Sans italic binaries.

The Namche Shadow Sans statics are committed exports (see AGENTS.md), so a
source correction cannot simply be rebuilt over them: a fresh build also
rewrites metadata, layout packing and hinting that the release already
carries. This script does the surgical half instead.

Give it a fresh gftools build of ``sources/NamcheShadowSans-Italic.glyphspackage``
(``otf/`` and ``ttf/`` subdirectories) and it copies only the glyph outlines
that actually changed into ``fonts/NamcheShadowSans``, regenerates the matching
WOFF2 webfonts, and leaves every other table byte-identical.

The italic package carries no RoundCorner instance filters — its Shadow
treatment is baked into the masters — so ``gftools builder`` reproduces the
committed italic outlines exactly. ``--check`` asserts that.

Usage:
  gftools builder sources/config-NamcheShadowSans-Italic.yaml   # -> out/sans-italic
  python3 scripts/refresh_sans_italic_outlines.py --compiled out/sans-italic
  python3 scripts/refresh_sans_italic_outlines.py --compiled out/sans-italic --check
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Dict, List, Sequence

from fontTools.pens.recordingPen import RecordingPen
from fontTools.ttLib import TTFont

ITALIC_SUFFIX = "Italic"
REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = REPO_ROOT / "fonts" / "NamcheShadowSans"


def italic_statics(directory: Path, extension: str) -> List[Path]:
    return sorted(
        p
        for p in directory.glob(f"*{extension}")
        if p.stem.endswith(ITALIC_SUFFIX)
    )


def open_font(path: Path) -> TTFont:
    # lazy keeps untouched tables as their original bytes; recalcTimestamp
    # would rewrite head.modified on every run.
    return TTFont(path, lazy=True, recalcTimestamp=False)


def changed_outlines(release: TTFont, compiled: TTFont) -> List[str]:
    order = release.getGlyphOrder()
    if order != compiled.getGlyphOrder():
        raise SystemExit("glyph order differs between release and compiled font")
    rel_set, com_set = release.getGlyphSet(), compiled.getGlyphSet()
    changed = []
    for name in order:
        rel_pen, com_pen = RecordingPen(), RecordingPen()
        rel_set[name].draw(rel_pen)
        com_set[name].draw(com_pen)
        if rel_pen.value != com_pen.value:
            changed.append(name)
    return changed


def check_metrics(release: TTFont, compiled: TTFont, names: Sequence[str]) -> None:
    rel_hmtx, com_hmtx = release["hmtx"], compiled["hmtx"]
    for name in names:
        if rel_hmtx[name] != com_hmtx[name]:
            raise SystemExit(
                f"{name}: horizontal metrics changed "
                f"{rel_hmtx[name]} -> {com_hmtx[name]}; refusing to merge"
            )


# CFF top-dict entries that carry the release's identity rather than its
# outlines. scripts/rename_font_metadata.py stamps these on the committed
# binaries; a source build compiles its own, so they must survive the swap.
CFF_IDENTITY_KEYS = (
    "version",
    "Notice",
    "Copyright",
    "FullName",
    "FamilyName",
    "Weight",
    "UniqueID",
    "XUID",
)


def charstrings(font: TTFont):
    cff = font["CFF "].cff
    return cff[cff.fontNames[0]].CharStrings


def preserve_cff_identity(release: TTFont, compiled: TTFont) -> List[str]:
    """Carry the release's CFF top-dict identity onto the incoming table."""
    rel_cff, com_cff = release["CFF "].cff, compiled["CFF "].cff
    if rel_cff.fontNames != com_cff.fontNames:
        raise SystemExit(
            f"CFF font name differs: {rel_cff.fontNames} vs {com_cff.fontNames}"
        )
    rel_top = rel_cff[rel_cff.fontNames[0]]
    com_top = com_cff[com_cff.fontNames[0]]
    preserved = []
    for key in CFF_IDENTITY_KEYS:
        rel_has, com_has = hasattr(rel_top, key), hasattr(com_top, key)
        if not rel_has and com_has:
            raise SystemExit(
                f"the build sets CFF {key} but the release does not; "
                "resolve by hand rather than merging"
            )
        if not rel_has:
            continue
        if com_has and getattr(com_top, key) == getattr(rel_top, key):
            continue
        setattr(com_top, key, getattr(rel_top, key))
        preserved.append(key)
    return preserved


def check_untouched_charstrings(
    release: TTFont, compiled: TTFont, changed: Sequence[str]
) -> None:
    """Every glyph outside ``changed`` must already be byte-identical.

    CFF charstrings share subroutines, so the table has to move as a unit
    rather than glyph by glyph. That is only as narrow as a per-glyph copy if
    the build encodes the untouched glyphs exactly as the release does.
    """
    rel, com = charstrings(release), charstrings(compiled)
    moved = set(changed)
    for name in release.getGlyphOrder():
        if name in moved:
            continue
        if rel[name].bytecode != com[name].bytecode:
            raise SystemExit(
                f"{name}: charstring differs from the release without an outline "
                "change; the build no longer matches and cannot be merged wholesale"
            )


def merge_otf(release_path: Path, compiled_path: Path, write: bool) -> List[str]:
    release, compiled = open_font(release_path), open_font(compiled_path)
    changed = changed_outlines(release, compiled)
    if changed:
        check_metrics(release, compiled, changed)
        check_untouched_charstrings(release, compiled, changed)
        if write:
            preserved = preserve_cff_identity(release, compiled)
            if preserved:
                print(f"  otf {release_path.name}: kept CFF {', '.join(preserved)}")
            release["CFF "] = compiled["CFF "]
            release.save(release_path, reorderTables=False)
    release.close()
    compiled.close()
    return changed


def merge_ttf(release_path: Path, compiled_path: Path, write: bool) -> List[str]:
    release, compiled = open_font(release_path), open_font(compiled_path)
    changed = changed_outlines(release, compiled)
    if changed:
        check_metrics(release, compiled, changed)
        if write:
            rel_glyf, com_glyf = release["glyf"], compiled["glyf"]
            for name in changed:
                rel_glyf[name] = com_glyf[name]
            release.save(release_path, reorderTables=False)
    release.close()
    compiled.close()
    return changed


def rebuild_webfont(ttf_path: Path, webfont_path: Path) -> None:
    font = TTFont(ttf_path, lazy=True, recalcTimestamp=False)
    font.flavor = "woff2"
    font.save(webfont_path, reorderTables=False)
    font.close()


def report(kind: str, path: Path, changed: Sequence[str]) -> None:
    if changed:
        head = ", ".join(changed[:6])
        more = f" (+{len(changed) - 6} more)" if len(changed) > 6 else ""
        print(f"  {kind} {path.name}: {len(changed)} glyph(s) — {head}{more}")
    else:
        print(f"  {kind} {path.name}: unchanged")


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--compiled",
        type=Path,
        required=True,
        help="Fresh gftools build of the italic source (contains otf/ and ttf/)",
    )
    ap.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Release directory to update (default: fonts/NamcheShadowSans)",
    )
    ap.add_argument(
        "--check",
        action="store_true",
        help="Only report; fail when the release outlines differ from the build",
    )
    args = ap.parse_args(argv)

    for sub in ("otf", "ttf"):
        if not (args.compiled / sub).is_dir():
            raise SystemExit(f"Missing {sub}/ under {args.compiled}")

    write = not args.check
    total: Dict[str, List[str]] = {}

    print(f"{'CHECK' if args.check else 'MERGE'}  compiled={args.compiled}")
    for compiled_path in italic_statics(args.compiled / "otf", ".otf"):
        release_path = args.output / "otf" / compiled_path.name
        if not release_path.exists():
            raise SystemExit(f"Release font missing: {release_path}")
        changed = merge_otf(release_path, compiled_path, write)
        total[str(release_path)] = changed
        report("otf", release_path, changed)

    touched_ttf: List[Path] = []
    for compiled_path in italic_statics(args.compiled / "ttf", ".ttf"):
        release_path = args.output / "ttf" / compiled_path.name
        if not release_path.exists():
            raise SystemExit(f"Release font missing: {release_path}")
        changed = merge_ttf(release_path, compiled_path, write)
        total[str(release_path)] = changed
        report("ttf", release_path, changed)
        if changed and write:
            touched_ttf.append(release_path)

    for ttf_path in touched_ttf:
        webfont_path = args.output / "webfonts" / f"{ttf_path.stem}.woff2"
        rebuild_webfont(ttf_path, webfont_path)
        print(f"  woff2 {webfont_path.name}: regenerated from {ttf_path.name}")

    changed_any = any(total.values())
    if args.check and changed_any:
        sys.stderr.write(
            "Release italic outlines differ from the compiled source build.\n"
            "Run without --check to merge them.\n"
        )
        return 1
    if not changed_any:
        print("Release italic outlines already match the compiled source build.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
