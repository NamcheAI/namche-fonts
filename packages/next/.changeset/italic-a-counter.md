---
"@namche/namche-shadow": patch
---

Restore the capital `A` counter in every Namche Shadow Sans italic. A boolean
pass in the italic Shadow treatment mistook the letter's crossbar for a counter
and subtracted it, so the glyph shipped as a single contour and rendered as a
filled wedge with a hairline notch in all nine italic weights, in their
webfonts, and in the `Á À Â Ä Å Ã` composites built from it. The italic `A`
masters are rebuilt with the crossbar unioned and its four inner corners
rounded like the upright; no other glyph, metric, or metadata changes.
