# Round 5: final look at 6ab84d8

Before/after close-ups of every spot that changed between 66120c2 and 6ab84d8, found automatically from raster differences. Columns: 66120c2, 6ab84d8, and 6ab84d8 with the 66120c2 outline in red. About 3 px per unit.

- `r5_y.png`: italic y, Regular and Medium.
- `r5_up.png`: upright b and u at 150, 200, 250, 300.
- `r5_it.png`: italic b, n and p at 150, 200, 250, 300.
- `r5_a.png`: upright a at Thin, Regular and Black (also smoothed in this commit).
- `r5_simon_ink.png`: for the reply on google/fonts#11180. Added ink at each inner corner (red = ink added to Geist), submitted build vs. 6ab84d8, Thin, Regular and Black.

Tangent check (`../prototype/check5.py`): explicit on-curve points with a 2–40° direction change, all lowercase. Upright 150: 70 → 43, italic 150: 83 → 56, no glyph gained one. The remaining points are real corners (k, w, x, z, t).

## Special characters and alternates

- `r6_sonder_up.png`, `r6_sonder_it.png`: all punctuation, symbols, figures and the special and accented letters at Thin, Regular and Black. Red = ink added to Geist, blue = ink removed from Geist.
- `r6_alt_up.png`, `r6_alt_it.png`: stylistic sets, ligatures, tabular, fraction, superior and inferior figures.
- `r6_four_small.png`: superior 4 (same outline as `four.numr`, `four.dnom`, `uni2084`), Geist vs. submitted vs. 6ab84d8 at Regular, Bold and Black. Its counter is 76–78 % of Geist's from Regular up (submitted: 66–69 %).

Checks (`../prototype/check6.py`, `../prototype/check7.py`): 303 encoded characters and 184 unencoded glyphs, 13 weights per slope. No counter closes; GSUB, GPOS, GDEF, cmap and hmtx match the Latin Core build bbdc0fd6 before the corner work.

## Small-figure fix 7333797

- `r7_small_figures.png`: superior figures at Regular and Black: Geist, 6ab84d8, 7333797.

Check (`../prototype/check8.py`): against 6ab84d8 only the 40 small figures changed (numerator, denominator, superior, inferior); every other glyph, alternates included, is unchanged. Small-figure counters are 92–97 % of Geist's upright and 93–97 % italic across Thin to Black; no counter closes at any of 10 weights.
