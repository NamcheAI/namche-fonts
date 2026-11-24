#!/usr/bin/env python3
"""Import Michael Marte's corrected upright Sans Glyphs package.

The incoming package is the visual source of truth for retained glyph geometry. Project naming, filters and attribution stay in the repository's
existing fontinfo.plist. Only the current Latin Core glyph inventory is imported.

This updates the Glyphs design/static source only. The production upright VF
is rebuilt separately from sources/NamcheShadowSans-Upright; changes imported
here require an explicit migration of that quadratic source and its deltas.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import re
import shutil


def import_package(incoming: Path, target: Path) -> None:
    incoming_glyphs = incoming / "glyphs"
    target_glyphs = target / "glyphs"
    incoming_names = {path.name for path in incoming_glyphs.glob("*.glyph")}
    target_names = {path.name for path in target_glyphs.glob("*.glyph")}
    if target_names - incoming_names:
        raise ValueError(f"incoming package lacks retained glyphs: {sorted(target_names-incoming_names)}")
    # Validate and normalize the complete incoming package before the first
    # maintained source file is replaced. A rejected drop must leave no hybrid
    # package behind.
    # Keep the maintained scope, naming, feature closure and encoding. Only
    # copy geometry for already-retained glyphs, stripping excluded Unicode.
    import tempfile
    import openstep_plist
    with tempfile.TemporaryDirectory() as temporary:
        stage = Path(temporary) / target.name
        shutil.copytree(target, stage)
        for name in sorted(target_names):
            text = (incoming_glyphs / name).read_text()
            openstep_plist.loads(text)  # Validate before replacing maintained files.
            old_text = (target_glyphs / name).read_text()
            old = openstep_plist.loads(old_text)
            # Preserve the maintained Unicode assignment, including unencoded
            # components that were encoded in a historical designer package.
            text = re.sub(r'^unicode = [^;]+;\n?', '', text, flags=re.M)
            if 'unicode' in old:
                assignment = re.search(r'^unicode = [^;]+;', old_text, re.M).group()
                text = text.replace('{', '{\n'+assignment+'\n', 1)
            (stage/'glyphs'/name).write_text(text)
        import glyphsLib
        from latin_core import CODEPOINTS
        staged = glyphsLib.GSFont(str(stage))
        if {int(u, 16) for g in staged.glyphs for u in g.unicodes} != CODEPOINTS:
            raise ValueError('Imported source does not retain exact Latin Core encoding')
        for glyph in staged.glyphs:
            for layer in glyph.layers:
                for component in layer.components:
                    if staged.glyphs[component.componentName] is None:
                        raise ValueError(f'Missing component in imported source: {component.componentName}')
        # The current filters are authoritative after the scope migration.
        # An incoming filter change requires a separately reviewed recipe edit.
        for name in sorted(target_names):
            shutil.copyfile(stage/'glyphs'/name, target_glyphs/name)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("incoming", type=Path)
    parser.add_argument(
        "--target",
        type=Path,
        default=Path("sources/NamcheShadowSans.glyphspackage"),
    )
    args = parser.parse_args()
    import_package(args.incoming, args.target)


if __name__ == "__main__":
    main()
