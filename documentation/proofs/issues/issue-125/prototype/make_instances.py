import sys
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer
srcs = {
 "namche": "/home/claude/namche-lc/fonts/NamcheShadowSans/variable/NamcheShadowSans[wght].ttf",
 "namche_main": "/home/claude/namcheai/namche-fonts/fonts/NamcheShadowSans/variable/NamcheShadowSans[wght].ttf",
 "geist": "/home/claude/namche-lc/fonts/Geist/webfonts/Geist-Variable.woff2",
}
for key, p in srcs.items():
    for w in (100, 200, 300, 400, 500, 700, 900):
        f = TTFont(p)
        inst = instancer.instantiateVariableFont(f, {"wght": w})
        inst.flavor = None
        inst.save(f"inst/{key}-{w}.ttf")
print("ok")
