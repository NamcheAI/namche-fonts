# Round 3: rebuild 7b47095

Close-ups of the PR #126 rebuild (commit 7b47095) against the previous build and Claude's prototype. Labels are in German: `bisher` = previous build, `neu` = rebuild 7b47095, `Prototyp` = Claude's prototype, `Vorschau B` = the round-2 preview of y option B.

- `r3_thin_upright.png`, `r3_thin_italic.png`: acute lowercase joins in Thin. Columns: previous build, rebuild (minimum radius 0.6 × r90), prototype at 0.6, prototype at 0.4. Added corner ink over a b d h m n p q r u relative to Geist, upright: previous 11.5k units², rebuild 21.7k, prototype 0.6 16.9k, prototype 0.4 12.7k. Italic: previous 5.1k, rebuild 21.6k, prototype 0.6 16.4k, prototype 0.4 13.0k.
- `r3_joins_400.png`, `r3_joins_900.png`: the same joins in Regular and Black. Columns: previous build, first PR #126 build, rebuild.
- `r3_y_vorschau.png`: y, arm into descender. Columns: previous build, rebuild, round-2 preview of option B (step removed, then the regular rule applied to the new corner).
- `r3_y_zoom.png`: rebuild, the same junction in Bold and Black at about 3.5 px per unit.
- `r3_hash.png`: italic #, centre counter.

Scripts: `../prototype/r3_sheets.py` (prototype `fill_corners(..., c=1.6, floor=0.4 or 0.6, space=0.9)`), `../prototype/r3_y_cmp.py`.
