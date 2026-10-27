"""Generate the Glyphs editor filter from the pinned GF Latin Core list."""
from pathlib import Path
import plistlib
import glyphsLib
from latin_core import ROOT, CODEPOINTS
font = glyphsLib.GSFont(str(ROOT/'sources/NamcheShadowSans.glyphspackage'))
names = sorted(g.name for g in font.glyphs if any(int(u,16) in CODEPOINTS for u in g.unicodes))
(ROOT/'sources/CustomFilter_GF_Latin_Core.plist').write_bytes(plistlib.dumps([{'name':'GF Latin Core','list':names}]))
