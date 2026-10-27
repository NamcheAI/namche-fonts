"""One row per Core character, every named static weight/style, no fallback."""
from pathlib import Path
import argparse
import json
import unicodedata

from PIL import Image, ImageDraw, ImageFont
from fontTools.ttLib import TTFont
from latin_core import CODEPOINTS, ROOT

WEIGHTS = ('Thin', 'ExtraLight', 'Light', 'Regular', 'Medium', 'SemiBold', 'Bold', 'ExtraBold', 'Black')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT/'out/latin-core-review')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    label_paths = ['/System/Library/Fonts/Menlo.ttc',
                   '/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf']
    label_path = next((p for p in label_paths if Path(p).exists()), None)
    if label_path is None:
        raise RuntimeError('Install Menlo or DejaVu Sans Mono for proof labels')
    label = ImageFont.truetype(label_path, 13)
    title = ImageFont.truetype(label_path, 20)
    records = []
    for family in ('NamcheShadowSans', 'NamcheShadowMono', 'NamcheShape'):
        root = ROOT/'fonts'/family/'ttf'
        if family == 'NamcheShape':
            styles = ('Metaball', 'Origin', 'Skeleton')
            cell = 450
        else:
            styles = WEIGHTS + tuple('Italic' if w == 'Regular' else w+'Italic' for w in WEIGHTS)
            cell = 80
        faces = [ImageFont.truetype(str(root/f'{family}-{style}.ttf'), 63,
                                   layout_engine=ImageFont.Layout.RAQM) for style in styles]
        for page, offset in enumerate(range(0, len(CODEPOINTS), 20), 1):
            points = sorted(CODEPOINTS)[offset:offset+20]
            width, height = 155 + len(styles)*cell, 100 + len(points)*110
            image = Image.new('RGB', (width, height), 'white')
            draw = ImageDraw.Draw(image)
            draw.text((12, 8), f'{family} | GF Latin Core | {page:02d} | one row per character', font=title, fill='black')
            for col, style in enumerate(styles):
                text = style.replace('Extra', 'X').replace('Regular', 'Reg').replace('Italic', 'It').replace('Semi', 'S')
                draw.text((155+col*cell, 46), text, font=label, fill='black')
            for row, cp in enumerate(points):
                y = 80+row*110
                draw.line((0,y,width,y),fill='#dddddd')
                name = unicodedata.name(chr(cp), 'UNNAMED')
                draw.text((8,y+8), f'U+{cp:04X}',font=title,fill='black')
                words=name.lower().split();line='';lines=[]
                for word in words:
                    if len(line)+len(word)>18:lines.append(line);line=''
                    line+=((' ' if line else '')+word)
                lines.append(line)
                for i,line in enumerate(lines[:4]):draw.text((8,y+38+i*15),line,font=label,fill='#555555')
                text = ('n'+chr(cp)) if unicodedata.combining(chr(cp)) else chr(cp)
                if family=='NamcheShape':text = text*4
                for col,face in enumerate(faces):
                    draw.text((155+col*cell+3,y+82),text,font=face,fill='black',anchor='ls')
                records.append({'family':family,'codepoint':f'U+{cp:04X}','character':chr(cp),'name':name,
                                'proof':f'{family}-{page:02d}.png','row':row+1,'styles':list(styles)})
            image.save(args.output/f'{family}-{page:02d}.png')
    (args.output/'index.json').write_text(json.dumps(records,ensure_ascii=False,indent=2)+'\n')


if __name__ == '__main__':
    main()
