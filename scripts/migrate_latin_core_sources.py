"""Explicit migration of Glyphs design sources to the pinned Latin Core scope.

Retains layout closure and component dependencies without re-fitting outlines.
The immutable originals/geist archive is never touched.
"""
from copy import deepcopy
import json
import logging
from pathlib import Path
import re
import shutil
import tempfile

import glyphsLib
import ufoLib2
import openstep_plist
from fontTools.feaLib.parser import Parser
from fontTools.feaLib.ast import FeatureBlock
from io import StringIO
from ufomerge import subset_ufo
from latin_core import CODEPOINTS, ROOT, normalize_info


def migrate(path):
    original = glyphsLib.GSFont(str(path))
    analysis = deepcopy(original)
    for glyph in analysis.glyphs:
        for layer in glyph.layers:
            layer._background = None
    if 'Shape' in path.name:
        analysis.axes = []
        analysis.customParameters = [p for p in analysis.customParameters if p.name != 'Virtual Master']
        for glyph in analysis.glyphs:
            for layer in list(glyph.layers):
                if layer.layerId != layer.associatedMasterId:
                    del glyph.layers[layer.layerId]
        analysis.instances = []
    designspace = glyphsLib.to_designspace(analysis, ufo_module=ufoLib2, minimize_glyphs_diffs=True)
    subsets = [subset_ufo(source.font, codepoints=CODEPOINTS, glyphs=['.notdef'],
                          layout_handling='closure') for source in designspace.sources if not source.layerName]
    keep = set().union(*(set(ufo.keys()) for ufo in subsets))
    # Preserve component geometry in all retained design layers, including
    # references and intermediate layers that are not exported by fontmake.
    while True:
        expanded = keep | {c.componentName for name in keep for layer in original.glyphs[name].layers
                           for c in layer.components if original.glyphs[c.componentName] is not None}
        if expanded == keep:
            break
        keep = expanded
    removed = [g.name for g in original.glyphs if g.name not in keep]
    changed_encoding = set()
    for glyph in list(original.glyphs):
        if glyph.name not in keep:
            del original.glyphs[glyph.name]
            continue
        codes = [u for u in glyph.unicodes if int(u, 16) in CODEPOINTS]
        if list(glyph.unicodes) != codes:
            changed_encoding.add(glyph.name)
            glyph.unicodes = codes
    # Subset feature rules as syntax trees, preserving substitutions rather
    # than deleting lines containing out-of-scope glyph names.
    original.features = []
    original.classes = []
    original.featurePrefixes = []
    features = re.sub(r'^languagesystem (?!DFLT|latn).*;\n', '', subsets[0].features.text, flags=re.M)
    tree = Parser(StringIO(features), glyphNames=keep).parse()
    prefix = []
    for statement in tree.statements:
        if isinstance(statement, FeatureBlock):
            original.features.append(glyphsLib.GSFeature(statement.name, '\n'.join(s.asFea() for s in statement.statements)))
        else:
            prefix.append(statement.asFea())
    original.featurePrefixes.append(glyphsLib.GSFeaturePrefix('Latin Core layout', '\n'.join(prefix)))
    # Remove orphaned direct-glyph kerning keys. Kerning group keys remain.
    for master, lefts in original.kerning.items():
        for left in list(lefts):
            if not left.startswith('@') and left not in keep:
                del lefts[left]
                continue
            for right in list(lefts[left]):
                if not right.startswith('@') and right not in keep:
                    del lefts[left][right]
    originals = {}
    for file in (path / 'glyphs').glob('*.glyph'):
        match = re.search(r'^glyphname = "?([^";]+)"?;', file.read_text(), re.M)
        if match:
            originals[match[1]] = (file.name, file.read_bytes())
    with tempfile.TemporaryDirectory() as temp:
        dest = Path(temp) / path.name
        (dest / 'glyphs').mkdir(parents=True)
        for glyph in original.glyphs:
            filename = originals[glyph.name][0]
            (dest / 'glyphs' / filename).write_text(glyphsLib.dumps(glyph))
        order = [glyph.name for glyph in original.glyphs]
        original.glyphs = []
        info = openstep_plist.loads(glyphsLib.dumps(original), use_numbers=True)
        info.pop('glyphs', None)
        normalize_info(info, keep)
        (dest / 'fontinfo.plist').write_text(openstep_plist.dumps(info))
        (dest / 'order.plist').write_text(openstep_plist.dumps(order))
        # The original raw geometry remains authoritative; only glyphs whose
        # Unicode mapping changed need the serializer's updated glyph file.
        for name, (filename, data) in originals.items():
            if name in keep:
                if name in changed_encoding:
                    text = data.decode()
                    text = re.sub(r'^unicode = [^;]+;\n?', '', text, flags=re.M)
                    data = text.encode()
                (dest / 'glyphs' / filename).write_bytes(data)
        shutil.rmtree(path)
        shutil.copytree(dest, path)
    return {'removed': removed, 'retained': sorted(keep), 'unencoded_dependencies': sorted(changed_encoding)}


if __name__ == '__main__':
    logging.disable(logging.CRITICAL)
    reports = {}
    for path in sorted((ROOT / 'sources').glob('Namche*.glyphspackage')):
        print(path.name, flush=True)
        reports[path.name] = migrate(path)
        print(len(reports[path.name]['retained']), 'retained', flush=True)
    (ROOT / 'sources/charsets/source-migration.json').write_text(json.dumps(reports, indent=2)+'\n')
