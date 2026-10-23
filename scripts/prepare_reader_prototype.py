#!/usr/bin/env python3
"""Prepare an isolated Glyphs source for the experimental Reader; never export releases."""
import json
import re
import shutil
from pathlib import Path

root = Path(__file__).resolve().parent.parent
recipe = json.loads((root / "sources/reader-prototype.json").read_text())
target = root / "out/reader-prototype/NamcheShadowSansReader.glyphspackage"
if target.exists():
    raise SystemExit(f"Refusing to overwrite {target}")
shutil.copytree(root / recipe["source"], target)
p = target / "fontinfo.plist"
text = p.read_text()
text, count = re.subn(r"RoundCorner;(-\d+);", lambda m: "RoundCorner;" + str(round(int(m[1]) * recipe["radius_scale"])) + ";", text)
assert count == 63, f"Unexpected filter count: {count}"
text = text.replace('familyName = "Namche Shadow Sans"', 'familyName = "' + recipe["family"] + '"')
p.write_text(text)
print(target)
print(f"Prepared {count} scaled filters; export natively in Glyphs, no release files modified.")
