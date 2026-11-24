# Round 5: final look at 6ab84d8

Before/after close-ups of every spot that changed between 66120c2 and 6ab84d8, found automatically from raster differences. Columns: 66120c2, 6ab84d8, and 6ab84d8 with the 66120c2 outline in red. About 3 px per unit.

- `r5_y.png`: italic y, Regular and Medium.
- `r5_up.png`: upright b and u at 150, 200, 250, 300.
- `r5_it.png`: italic b, n and p at 150, 200, 250, 300.
- `r5_a.png`: upright a at Thin, Regular and Black (also smoothed in this commit).
- `r5_simon_ink.png`: for the reply on google/fonts#11180. Added ink at each inner corner (red = ink added to Geist), submitted build vs. 6ab84d8, Thin, Regular and Black.

Tangent check (`../prototype/check5.py`): explicit on-curve points with a 2–40° direction change, all lowercase. Upright 150: 70 → 43, italic 150: 83 → 56, no glyph gained one. The remaining points are real corners (k, w, x, z, t).
