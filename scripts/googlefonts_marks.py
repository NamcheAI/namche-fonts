"""Build the candidate's macron below from the family's existing mark design."""
from copy import deepcopy
import math

from fontTools.misc.roundTools import otRound
from fontTools.ttLib.tables._g_l_y_f import GlyphCoordinates
from fontTools.ttLib.tables.TupleVariation import TupleVariation
from fontTools.ttLib.tables import otTables
from fontTools.varLib.builder import buildVarData, buildVarDevTable, buildVarRegionList
from fontTools.varLib.instancer import instantiateVariableFont
from fontTools.varLib.models import VariationModel
from fontTools.ttLib import TTFont

GLYPH = 'uni0331'


def extend_candidate(path):
    original = TTFont(path, recalcTimestamp=False)
    candidate = TTFont(path, recalcTimestamp=False)
    add_macron_below(candidate)
    candidate.save(path, reorderTables=False)
    rebuilt = TTFont(path, recalcTimestamp=False)
    for name in original.getGlyphOrder():
        if original['glyf'][name].compile(original['glyf']) != rebuilt['glyf'][name].compile(rebuilt['glyf']):
            raise ValueError(f'Macron-below addition changed existing outline {name}')
        if original['hmtx'][name] != rebuilt['hmtx'][name]:
            raise ValueError(f'Macron-below addition changed advance or sidebearing {name}')
        before = original['gvar'].variations.get(name, [])
        after = rebuilt['gvar'].variations.get(name, [])
        if [(v.axes, v.coordinates) for v in before] != [(v.axes, v.coordinates) for v in after]:
            raise ValueError(f'Macron-below addition changed variation {name}')
    for tag in ('name', 'GSUB', 'STAT', 'fvar', 'OS/2'):
        if original.getTableData(tag) != rebuilt.getTableData(tag):
            raise ValueError(f'Macron-below addition changed protected table {tag}')


def mark_anchor(font, glyph):
    for lookup in font['GPOS'].table.LookupList.Lookup:
        for subtable in lookup.SubTable:
            if lookup.LookupType == 4 and glyph in subtable.MarkCoverage.glyphs:
                return subtable.MarkArray.MarkRecord[subtable.MarkCoverage.glyphs.index(glyph)].MarkAnchor
    raise ValueError(f'Missing mark-to-base anchor for {glyph}')


def add_macron_below(font):
    if 0x0331 in font.getBestCmap() or GLYPH in font.getGlyphOrder():
        raise ValueError('Candidate already contains macron below')
    peaks = sorted({variation.axes['wght'][1]
                    for variations in font['gvar'].variations.values()
                    for variation in variations} | {0.0})
    model = VariationModel([{'wght': peak} if peak else {} for peak in peaks], axisOrder=['wght'])
    masters, stacking = [], []
    slope = math.tan(math.radians(-font['post'].italicAngle))
    for peak in peaks:
        weight = 400 + peak * (300 if peak < 0 else 500)
        instance = instantiateVariableFont(font, {'wght': weight}, inplace=False)
        macron = instance['glyf']['uni0304']
        dot = instance['glyf']['dotbelowcomb']
        above = mark_anchor(instance, 'uni0304')
        below = mark_anchor(instance, 'dotbelowcomb')
        vertical = dot.yMax - macron.yMax
        horizontal = below.XCoordinate - above.XCoordinate + slope * (vertical + above.YCoordinate)
        coordinates = GlyphCoordinates([(otRound(horizontal + x), otRound(vertical + y))
                                        for x, y in macron.coordinates])
        bottom = min(y for x, y in coordinates)
        stacking.append((otRound(below.XCoordinate + slope * bottom), bottom))
        coordinates.extend([(0, 0)] * 4)
        masters.append(coordinates)
    default = masters[peaks.index(0)]
    glyph = deepcopy(font['glyf']['uni0304'])
    glyph.coordinates = GlyphCoordinates(default[:-4])
    glyph.recalcBounds(font['glyf'])
    order = font.getGlyphOrder() + [GLYPH]
    font.setGlyphOrder(order)
    font['glyf'].glyphOrder = order
    font['glyf'][GLYPH] = glyph
    font['hmtx'][GLYPH] = (0, glyph.xMin)
    font['gvar'].variations[GLYPH] = [TupleVariation(support, [tuple(otRound(value) for value in point) for point in delta])
                                     for support, delta in zip(model.supports[1:], model.getDeltas(masters)[1:])]
    for subtable in font['cmap'].tables:
        if subtable.isUnicode() and subtable.format in (4, 12):
            subtable.cmap[0x0331] = GLYPH
    for attribute in ('AdvWidthMap', 'LsbMap', 'RsbMap'):
        mapping = getattr(font['HVAR'].table, attribute)
        if mapping is not None:
            mapping.mapping[GLYPH] = mapping.mapping['dotbelowcomb']
    definition = font['GDEF'].table
    definition.GlyphClassDef.classDefs[GLYPH] = 3
    if definition.MarkAttachClassDef and 'dotbelowcomb' in definition.MarkAttachClassDef.classDefs:
        definition.MarkAttachClassDef.classDefs[GLYPH] = definition.MarkAttachClassDef.classDefs['dotbelowcomb']
    if definition.MarkGlyphSetsDef:
        for coverage in definition.MarkGlyphSetsDef.Coverage:
            if 'dotbelowcomb' in coverage.glyphs:
                coverage.glyphs.append(GLYPH)
    store = definition.VarStore
    region_offset = len(store.VarRegionList.Region)
    regions = buildVarRegionList(model.supports[1:], ['wght'])
    store.VarRegionList.Region.extend(regions.Region)
    store.VarRegionList.RegionCount = len(store.VarRegionList.Region)
    values = [model.getDeltas([point[axis] for point in stacking], round=otRound) for axis in (0, 1)]
    variation_index = len(store.VarData) << 16
    store.VarData.append(buildVarData(list(range(region_offset, region_offset + len(regions.Region))),
                                      [delta[1:] for delta in values], optimize=False))
    store.VarDataCount = len(store.VarData)
    stack_anchor = otTables.Anchor()
    stack_anchor.Format = 3
    stack_anchor.XCoordinate, stack_anchor.YCoordinate = (delta[0] for delta in values)
    stack_anchor.XDeviceTable = buildVarDevTable(variation_index)
    stack_anchor.YDeviceTable = buildVarDevTable(variation_index + 1)
    for lookup in font['GPOS'].table.LookupList.Lookup:
        for subtable in lookup.SubTable:
            for coverage_name, array_name, record_name, count_name in (
                    ('MarkCoverage', 'MarkArray', 'MarkRecord', 'MarkCount'),
                    ('Mark1Coverage', 'Mark1Array', 'MarkRecord', 'MarkCount')):
                coverage = getattr(subtable, coverage_name, None)
                if coverage is not None and 'dotbelowcomb' in coverage.glyphs:
                    array = getattr(subtable, array_name)
                    records = getattr(array, record_name)
                    records.append(deepcopy(records[coverage.glyphs.index('dotbelowcomb')]))
                    coverage.glyphs.append(GLYPH)
                    setattr(array, count_name, len(records))
            coverage = getattr(subtable, 'Mark2Coverage', None)
            if coverage is not None and 'dotbelowcomb' in coverage.glyphs:
                records = subtable.Mark2Array.Mark2Record
                record = deepcopy(records[coverage.glyphs.index('dotbelowcomb')])
                record.Mark2Anchor = [deepcopy(stack_anchor) if anchor else None for anchor in record.Mark2Anchor]
                records.append(record)
                coverage.glyphs.append(GLYPH)
                subtable.Mark2Array.Mark2Count = len(records)
