import sys; sys.path.insert(0,'/home/claude/work')
import pathops
from measure import glyph_path, stem
from proto import fill_corners
from fontTools.ttLib import TTFont
from fontTools.pens.areaPen import AreaPen
bad=0; n=0
for w in (100,200,300,400,500,700,900):
    gf=TTFont(f"inst/geist-{w}.ttf"); s=stem(gf); gc=gf.getBestCmap()
    for ch in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789#$&@%?!ßæøÆØŒœ":
        if ord(ch) not in gc: continue
        g=glyph_path(gf,gc[ord(ch)]); n+=1
        o=fill_corners(g,s,c=1.2,rmax=70 if (ch.isupper() or ch.isdigit()) else 53,as_skia=False)
        added = abs(o.area) - abs(g.area)
        nc_g = len(list(g.contours)); nc_o = len(list(o.contours))
        if added < -5 or added > 14*0.2146*min(1.2*s,70)**2 or nc_o < nc_g:
            bad+=1; print("check", w, ch, round(added), nc_g, nc_o, flush=True)
print("Zeichen×Gewichte geprüft:", n, "auffällig:", bad)
