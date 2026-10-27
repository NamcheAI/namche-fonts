"""Compare all retained outlines, metrics and Core shaping with a prior release."""
import argparse
from io import BytesIO
import json
from pathlib import Path
import unicodedata

from fontTools.ttLib import TTFont
from fontTools.pens.recordingPen import DecomposingRecordingPen
import uharfbuzz as hb
from latin_core import ROOT, CODEPOINTS


def shaping(font, texts, weight):
    stream = BytesIO()
    font.flavor = None
    font.save(stream)
    face = hb.Font(hb.Face(stream.getvalue()))
    face.set_variations({'wght':weight})
    order = font.getGlyphOrder()
    result=[]
    for text in texts:
        buffer=hb.Buffer();buffer.add_str(text);buffer.guess_segment_properties()
        hb.shape(face,buffer)
        result.append([(order[g.codepoint],p.x_advance,p.y_advance,p.x_offset,p.y_offset)
                       for g,p in zip(buffer.glyph_infos,buffer.glyph_positions)])
    return result


def audit(before, after):
    reports=[]
    for path in sorted(after.glob('Namche*/*/*')):
        if path.suffix not in ('.otf','.ttf','.woff2'):
            continue
        old=TTFont(before/path.relative_to(after),recalcTimestamp=False)
        new=TTFont(path,recalcTimestamp=False)
        errors=[]
        if set(new.getBestCmap()) != CODEPOINTS:errors.append('wrong character scope')
        for weight in ((100,250,400,550,700,850,900) if 'fvar' in new else (400,)):
            a=old.getGlyphSet(location={'wght':weight});b=new.getGlyphSet(location={'wght':weight})
            for name in new.getGlyphOrder():
                if name not in a:errors.append(f'new glyph {name}');continue
                p=DecomposingRecordingPen(a);q=DecomposingRecordingPen(b)
                a[name].draw(p);b[name].draw(q)
                if p.value!=q.value:errors.append(f'{name}@{weight}: outline changed')
                if a[name].width!=b[name].width:errors.append(f'{name}@{weight}: width changed')
            if path.suffix=='.ttf':
                texts=[chr(cp) for cp in sorted(CODEPOINTS)]
                texts += [unicodedata.normalize('NFD',chr(cp)) for cp in sorted(CODEPOINTS)]
                texts += ['AVATAR To Wa fi ffi fl', 'aaaa llll 0000', 'į́ ï j́', 'Hamburgefontsiv 0123456789']
                aa,bb=shaping(old,texts,weight),shaping(new,texts,weight)
                errors += [f'{text!r}@{weight}: shaping changed' for text,x,y in zip(texts,aa,bb) if x!=y]
        reports.append({'file':str(path.relative_to(ROOT)), 'retained_glyphs':len(new.getGlyphOrder()),
                        'encoded_characters':len(new.getBestCmap()),'differences':sorted(set(errors))})
    return reports


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--before',required=True,type=Path)
    parser.add_argument('--after',default=ROOT/'fonts',type=Path)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args();reports=audit(args.before,args.after)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(reports,ensure_ascii=False,indent=2)+'\n')
    print(len(reports),'files;',sum(len(r['differences']) for r in reports),'differences')
    if any(r['differences'] for r in reports):raise SystemExit(1)
