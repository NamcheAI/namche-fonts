#!/usr/bin/env python3
"""Recover editable quadratic designspace masters and verify their exact deltas."""
from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
import tempfile

from fontTools.designspaceLib import AxisDescriptor, DesignSpaceDocument, SourceDescriptor
from fontTools.ttLib import TTFont, newTable
from fontTools.pens.ttGlyphPen import TTGlyphPointPen
from fontTools.ttLib.tables._g_l_y_f import GlyphCoordinates
from fontTools.ttLib.tables.TupleVariation import TupleVariation
from fontTools.misc.roundTools import otRound
from fontTools.misc.fixedTools import floatToFixedToFloat
from fontTools.varLib.models import VariationModel, supportScalar
from ufoLib2 import Font

from build_sans_open import SOURCE, ITALIC_SOURCE, check, build


def load_outline_source(source, default):
    font = TTFont()
    font.importXML(source / 'variation-and-layout.ttx')
    font['glyf'] = newTable('glyf')
    font['glyf'].glyphs = {}
    font['glyf'].glyphOrder = default.glyphOrder
    for name in default.glyphOrder:
        pen = TTGlyphPointPen(default)
        default[name].drawPoints(pen)
        font['glyf'][name] = pen.glyph()
    return font


def build_reconstructed(source, output, verify=False):
    manifest = json.loads((source / 'provenance.json').read_text())
    document = DesignSpaceDocument.fromfile(source / 'Sans.designspace')
    locations = []
    for descriptor in document.sources:
        weight = descriptor.location['Weight']
        peak = floatToFixedToFloat((weight - 400) / (300 if weight < 400 else 500), 14)
        locations.append({'wght': peak} if peak else {})
    model = VariationModel(locations, axisOrder=['wght'])
    saved = [Font.open(source / descriptor.filename) for descriptor in document.sources]
    default = saved[locations.index({})]
    point_order = json.loads((source / 'point-order.json').read_text())
    for master in saved:
        if master.glyphOrder != default.glyphOrder:
            raise ValueError('Reconstructed master glyph order changed')
        for name in default.glyphOrder:
            if master[name].components:
                raise ValueError(f'{name}: reconstructed masters cannot contain components')
            phantom = master[name].lib['org.namche.phantomPoints']
            if abs(master[name].width - (phantom[1][0] - phantom[0][0])) > 1e-6:
                raise ValueError(f'{name}: edited width needs a metric variation migration')
            actual = [[point.identifier for point in contour.points] for contour in master[name].contours]
            if actual != point_order[name]:
                raise ValueError(f'{name}: reconstructed master point topology changed')
            if [[point.type for point in contour.points] for contour in master[name].contours] != [
                    [point.type for point in contour.points] for contour in default[name].contours]:
                raise ValueError(f'{name}: reconstructed master point types changed')
    font = load_outline_source(source, default)
    font['gvar'] = newTable('gvar')
    font['gvar'].version, font['gvar'].reserved = 1, 0
    font['gvar'].variations = {}
    structure = json.loads((source / 'variation-structure.json').read_text())
    for name in default.glyphOrder:
        values = [GlyphCoordinates([(point.x, point.y) for contour in master[name].contours
                                    for point in contour.points] +
                                   [tuple(point) for point in master[name].lib['org.namche.phantomPoints']])
                  for master in saved]
        deltas = model.getDeltas(values)
        by_support = {tuple(sorted(support.items())): delta
                      for support, delta in zip(model.supports, deltas)}
        recorded = {tuple(sorted((axis, tuple(values)) for axis, values in record['axes'].items()))
                    for record in structure[name]}
        for support, delta in by_support.items():
            if support and support not in recorded and any(
                    abs(value) > 1e-6 for point in delta for value in point):
                raise ValueError(f'{name}: edited master needs a new variation support')
        restored = []
        for record in structure[name]:
            axes = {axis: tuple(support) for axis, support in record['axes'].items()}
            delta = by_support[tuple(sorted(axes.items()))]
            points = [None] * len(delta)
            for index in record['explicit_points']:
                points[index] = tuple(otRound(value) for value in delta[index])
            variation = TupleVariation(axes, points)
            expanded = deepcopy(variation)
            coordinates, controls = font['glyf']._getCoordinatesAndControls(name, font['hmtx'].metrics)
            expanded.calcInferredDeltas(coordinates, controls.endPts)
            if any(abs(actual[axis] - expected[axis]) > 1e-6
                   for actual, expected in zip(expanded.coordinates, delta) for axis in (0, 1)):
                raise ValueError(f'{name}: edited master needs a variation-structure migration')
            restored.append(variation)
        font['gvar'].variations[name] = restored
    with tempfile.TemporaryDirectory(prefix='namche-master-build-') as scratch:
        recovered = Path(scratch)
        default.save(recovered / manifest.get('ufo', 'Upright.ufo'))
        for filename in ('provenance.json', 'point-order.json', 'variation-and-layout.ttx'):
            (recovered / filename).write_bytes((source / filename).read_bytes())
        font.saveXML(recovered / 'variations.ttx', tables=['gvar'])
        if verify:
            check(recovered, SOURCE.parent.parent / 'fonts/NamcheShadowSans')
        build(recovered, output)


def reconstruct(source: Path, output: Path) -> dict:
    manifest = json.loads((source / 'provenance.json').read_text())
    default = Font.open(source / manifest.get('ufo', 'Upright.ufo'))
    font = load_outline_source(source, default)
    font.importXML(source / 'variations.ttx')
    peaks = sorted({variation.axes['wght'][1]
                    for variations in font['gvar'].variations.values()
                    for variation in variations} | {0.0})
    locations = [{'wght': peak} if peak else {} for peak in peaks]
    model = VariationModel(locations, axisOrder=['wght'])
    masters = [deepcopy(default) for peak in peaks]
    structure = {}
    maximum_error = 0.0
    for name in default.glyphOrder:
        coordinates, controls = font['glyf']._getCoordinatesAndControls(name, font['hmtx'].metrics)
        variations = font['gvar'].variations.get(name, [])
        expanded = deepcopy(variations)
        for variation in expanded:
            variation.calcInferredDeltas(coordinates, controls.endPts)
        values = []
        for master, location in zip(masters, locations):
            value = GlyphCoordinates(coordinates)
            for variation in expanded:
                scalar = supportScalar(location, variation.axes)
                if scalar:
                    value += GlyphCoordinates(variation.coordinates) * scalar
            values.append(value)
            for point, (horizontal, vertical) in zip(
                    (point for contour in master[name].contours for point in contour.points), value):
                point.x, point.y = horizontal, vertical
            master[name].lib['org.namche.phantomPoints'] = list(value[-4:])
            master[name].width = value[-3][0] - value[-4][0]
        deltas = model.getDeltas(values)
        by_support = {tuple(sorted(support.items())): delta
                      for support, delta in zip(model.supports, deltas)}
        structure[name] = []
        for original, inferred in zip(variations, expanded):
            delta = by_support[tuple(sorted(original.axes.items()))]
            explicit = [index for index, point in enumerate(original.coordinates) if point is not None]
            for index in explicit:
                error = max(abs(delta[index][axis] - original.coordinates[index][axis]) for axis in (0, 1))
                maximum_error = max(maximum_error, error)
                if error > 1e-7:
                    raise ValueError(f'{name}: reconstructed explicit delta differs by {error}')
            for actual, expected in zip(delta, inferred.coordinates):
                if max(abs(actual[axis] - expected[axis]) for axis in (0, 1)) > 1e-7:
                    raise ValueError(f'{name}: reconstructed interpolation differs')
            structure[name].append({'axes': original.axes, 'explicit_points': explicit})
    output.mkdir(parents=True, exist_ok=False)
    document = DesignSpaceDocument()
    axis = AxisDescriptor()
    axis.name, axis.tag = 'Weight', 'wght'
    axis.minimum, axis.default, axis.maximum = 100, 400, 900
    document.addAxis(axis)
    for peak, master in zip(peaks, masters):
        weight = 400 + peak * (300 if peak < 0 else 500)
        filename = f'Weight-{weight:.8f}.ufo'
        master.info.styleName = f'Weight {weight:.8f}'
        master.save(output / filename)
        descriptor = SourceDescriptor()
        descriptor.filename = filename
        descriptor.name = filename[:-4]
        descriptor.familyName = master.info.familyName
        descriptor.styleName = master.info.styleName
        descriptor.location = {'Weight': weight}
        document.addSource(descriptor)
    document.write(output / 'Sans.designspace')
    (output / 'variation-structure.json').write_text(json.dumps(structure, indent=2) + '\n')
    for filename in ('provenance.json', 'point-order.json', 'variation-and-layout.ttx'):
        (output / filename).write_bytes((source / filename).read_bytes())
    build_reconstructed(output, output / 'roundtrip', verify=True)
    report = {'source': source.name, 'glyphs': len(default), 'masters': len(peaks),
              'maximum_explicit_delta_error': maximum_error,
              'normalized_master_locations': peaks,
              'saved_master_roundtrip': 'TTF and WOFF2 byte-identical to approved release in two builds',
              'note': 'Recovered quadratic masters, not historical cubic Glyphs exports. Preserve quantized locations and point topology. No variation delta values are stored in variation-structure.json.'}
    (output / 'reconstruction.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--build-from', type=Path, help='Build one exported designspace directory without original variation XML')
    args = parser.parse_args()
    if args.build_from:
        build_reconstructed(args.build_from, args.output)
        return
    for source in (SOURCE, ITALIC_SOURCE):
        print(json.dumps(reconstruct(source, args.output / source.name)))


if __name__ == '__main__':
    main()
