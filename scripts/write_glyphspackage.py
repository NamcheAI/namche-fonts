#!/usr/bin/env python3
"""Write a real, reloadable Glyphs 3 package while preserving its file names."""

from __future__ import annotations

import os
import copy
from pathlib import Path
import shutil
import tempfile
import uuid

import glyphsLib
import openstep_plist
from glyphsLib import GSFont
from glyphsLib.writer import Writer


def _template_glyph_files(template: Path) -> dict[str, Path]:
    glyph_dir = template / "glyphs"
    if not glyph_dir.is_dir():
        raise ValueError(f"template has no glyphs directory: {template}")

    files: dict[str, Path] = {}
    for path in sorted(glyph_dir.glob("*.glyph")):
        record = openstep_plist.loads(path.read_text(encoding="utf-8"))
        name = record.get("glyphname")
        if not isinstance(name, str) or not name:
            raise ValueError(f"template glyph has no glyphname: {path}")
        if name in files:
            raise ValueError(f"duplicate template glyph name {name!r}")
        files[name] = path
    return files


def _write_fontinfo(font: GSFont, path: Path, format_version: int) -> None:
    # Avoid the public property setter here: it reattaches every glyph and may
    # materialize default layer backgrounds, changing canonical serialization.
    glyphs = font._glyphs
    try:
        font._glyphs = []
        from io import StringIO

        stream = StringIO()
        Writer(stream, format_version=format_version).write(font)
    finally:
        font._glyphs = glyphs

    data = openstep_plist.loads(stream.getvalue(), use_numbers=True)
    if data.get("glyphs") != []:
        raise ValueError("serialized fontinfo unexpectedly contains glyph records")
    del data["glyphs"]
    # Preserve Writer's insertion order (notably kerningLTR/RTL tables), which
    # glyphsLib's canonical serializer retains on package reload.
    path.write_text(openstep_plist.dumps(data, sort_keys=False), encoding="utf-8")


def _write_package(font: GSFont, package: Path, glyph_files: dict[str, Path]) -> None:
    package.mkdir()
    glyph_dir = package / "glyphs"
    glyph_dir.mkdir()
    format_version = font.format_version

    _write_fontinfo(font, package / "fontinfo.plist", format_version)
    (package / "order.plist").write_text(
        openstep_plist.dumps([glyph.name for glyph in font.glyphs]),
        encoding="utf-8",
    )

    for glyph in font.glyphs:
        filename = glyph_files[glyph.name].name
        with (glyph_dir / filename).open("wb") as stream:
            Writer(stream, format_version=format_version).write(glyph)


def _remove_path(path: Path) -> None:
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    else:
        path.unlink()


def save_package(font: GSFont, target: Path, template: Path) -> None:
    """Save ``font`` as a Glyphs package using ``template``'s glyph filenames.

    The template must have exactly the same glyph-name inventory as ``font``.
    A staged package is reloaded and compared canonically before the existing
    target is moved aside or replaced. The target may be a prior package
    directory or a monolithic file created by ``GSFont.save``.
    """

    target = Path(target)
    template = Path(template)
    if not template.is_dir():
        raise ValueError(f"template is not a package directory: {template}")
    if target.resolve() == template.resolve():
        raise ValueError("target and template must be different paths")
    if not target.parent.is_dir():
        raise ValueError(f"target parent does not exist: {target.parent}")
    if target.is_symlink():
        raise ValueError(f"refusing to replace a symlink target: {target}")
    if target.exists() and not (target.is_dir() or target.is_file()):
        raise ValueError(f"target is not a regular file or directory: {target}")

    glyph_files = _template_glyph_files(template)
    glyph_names = [glyph.name for glyph in font.glyphs]
    if len(glyph_names) != len(set(glyph_names)):
        raise ValueError("font contains duplicate glyph names")
    expected_names = set(glyph_files)
    actual_names = set(glyph_names)
    missing = sorted(expected_names - actual_names)
    added = sorted(actual_names - expected_names)
    if missing or added:
        raise ValueError(
            "glyph filename inventory differs from template: "
            f"missing={missing}, added={added}"
        )

    stage_root = Path(
        tempfile.mkdtemp(prefix=f".{target.name}.stage-", dir=target.parent)
    )
    staged_package = stage_root / "package"
    try:
        # A .glyphs monolith is the compiler's input semantics: its parser
        # normalizes near-zero component offsets and negative-zero kerning.
        # Compare against that normalized representation, not raw in-memory
        # values that a package writer may serialize differently. Keep all
        # serialization on clones because GlyphsLib lazily materializes empty
        # backgrounds while dumping.
        monolithic = glyphsLib.dumps(copy.deepcopy(font))
        canonical_font = glyphsLib.loads(monolithic)
        expected_serialization = glyphsLib.dumps(copy.deepcopy(canonical_font))
        write_font = copy.deepcopy(canonical_font)
        _write_package(write_font, staged_package, glyph_files)
        reloaded = GSFont(str(staged_package))
        reloaded_serialization = glyphsLib.dumps(reloaded)
        if expected_serialization != reloaded_serialization:
            raise ValueError(
                "Glyphs package round-trip changed canonical font serialization; "
                "existing target was left untouched"
            )

        backup: Path | None = None
        if target.exists():
            backup = target.parent / f".{target.name}.backup-{uuid.uuid4().hex}"
            os.replace(target, backup)
        try:
            os.replace(staged_package, target)
        except Exception:
            if backup is not None and backup.exists():
                os.replace(backup, target)
            raise
        if backup is not None:
            _remove_path(backup)
    finally:
        shutil.rmtree(stage_root, ignore_errors=True)
