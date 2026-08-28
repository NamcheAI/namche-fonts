# Learnings & findings (Namche RoundCorner)

Operational notes from shipping **Namche-Shadow** (multi-tier) and **Namche-Shadow-Simple** (−40/−25) via Glyphs RoundCorner. Recipe details live in [`scripts/NAMCHE_SHADOW.md`](scripts/NAMCHE_SHADOW.md). Research on CLI / RoboFont / interactive apps: [`scripts/ROUNDCORNER_OUTSIDE_GLYPHS.md`](scripts/ROUNDCORNER_OUTSIDE_GLYPHS.md).

## Production path

- **Ship with Glyphs RoundCorner export filters**, not the experimental Python inner-fillet engine (`scripts/round_inner_corners.py`).
- Filters are the production mechanism for **static instances** and for the
  post-rounding OTF masters used by the upright VF builder. Glyphs' own VF
  export is still unsuitable because it skips those filters. Use the
  `compatible` filter option, then `scripts/build_sans_variable.py` to align
  the remaining rounded segmentation and build the VF.
- Upstream/`originals/geist/` stays **Geist** and immutable. Delivery family names (`Namche-Shadow`, `Namche-Shadow-Simple`) are set at export / name-table rewrite.

## The italics are the exception: baked, not filtered

The Sans **italic** package carries **no** RoundCorner instance filters. Its Shadow
treatment was baked straight into the three masters by `scripts/round_inner_corners.py`
at `--radius 40` (issue #4, 2026-08-13). Two consequences that are easy to get wrong:

- `gftools builder sources/config-NamcheShadowSans-Italic.yaml` reproduces the
  committed italic outlines **exactly** — unlike the uprights, which need a Glyphs
  GUI export. An italic source correction can therefore be merged into the
  committed release with `make refresh-sans-italic-outlines`, which replaces only
  the glyph outlines that changed and leaves metadata, layout and hinting alone.
- The filter has been retuned since that bake (acute-angle radius reduction, mouth
  cap, Black scale), so today's defaults do **not** reproduce the italics. Pass
  `--italic-recipe` to get the profile that did: plain circular fillet, master
  scales 0.55 / 1.00 / 1.35. It reproduces every straight-sided italic master
  byte-for-byte; the curve-carrying glyphs (`fillet_mixed`) have drifted and are
  not reproducible.

### Boolean topology is the failure mode to watch (issue #78)

`A` is drawn as a silhouette plus a separate crossbar that overlaps it. The
resolver classified the crossbar as a counter — it tested only whether the
crossbar's *first point* fell inside the silhouette — and subtracted it instead of
unioning it. The counter stopped being a contour of its own, and every italic
weight shipped an `A` that renders as a filled wedge with a hairline notch.

Nesting is now decided by actual containment (`path_is_nested`), and pathops'
repeated closing point is dropped before filleting — left in place it silently
skipped the corner it sat on, which is why the counter's lower-left crotch came
back sharp on the first attempt. `scripts/check_sans_counters.py` blocks the whole
class: it asserts the contour count of twenty counter-bearing glyphs across every
committed Sans binary and npm copy.

To re-derive the corrected `A` from the pre-Shadow drawing:

```sh
mkdir -p /tmp/pkg/glyphs
git show 54de7f6:sources/NamcheShadowSans-Italic.glyphspackage/glyphs/A_.glyph \
  > /tmp/pkg/glyphs/A_.glyph
venv/bin/python scripts/round_inner_corners.py \
  --package /tmp/pkg --glyphs A --radius 40 --italic-recipe --write
```

## Family naming (resolved 2026-08-11)

| Family | Role | Recipe |
|--------|------|--------|
| **Namche-Shadow** | Primary | Multi-tier: −60 exclude → −80 include → −60 (`A,V,Z,X,Germandbls`) → −50 (`k,x,v,w`) → −40 (`M,N,W,two,four,seven,six`) → −50 (`nine`) → −10 (`Yusbig-cy,yusbig-cy,mu,baht,peso`) |
| **Namche-Shadow-Simple** | Prior recipe | Two-radius: caps/figures −40 include, rest −25 exclude |

The temporary name **Namche-Darth** for the multi-tier stack is **retired**. Older docs/commits may still mention it.

## `glyphs-cli` / Cursor cannot replace Glyphs GUI export

Automated export with [`glyphs-cli`](https://pypi.org/project/glyphs-cli/) (`glyphs export --app 4 --plugins …`) **does not reliably apply RoundCorner instance filters**.

| Evidence (Regular `H`) | `curveTo` count |
|------------------------|-----------------|
| Glyphs GUI export (good) | **4** (inners rounded) |
| `glyphs-cli` (Filter with `;1;` slot) | **0** (sharp) |
| `glyphs-cli` (GUI-native Filter string + explicit RoundCorner plugin) | **0** (still sharp) |

Also: bad CLI Regular OTFs were ~71 KB vs ~92 KB for correctly rounded GUI exports.

**Rule:** For shipping binaries, use **File → Export… in Glyphs.app** (or a Glyphs Macro that calls `font.export`). After any automated export, proof an inner-corner glyph (`H`, `E`, `a`).

Filter **string format** still matters for packages that open correctly in Glyphs:

- Prefer GUI-native compatible form: `RoundCorner;-60;compatible;include:A,…`
  (no `;1;` visual-correctness slot, no space after `:`).
- Order for multi-tier stacks is significant — paste / apply in the documented order (see paste file).

Accessibility / AppleScript automation of Glyphs UI from Cursor may be blocked; do not rely on it.

## Downloads naming collisions

Glyphs often exports as `Geist.glyphspackage` / `Geist-*.otf` regardless of intended Namche family.

- **Always archive** under dated `exports/<Family>/_received/…` before overwriting delivery.
- Never drop Downloads onto `originals/geist/` or blindly onto `exports/Namche-Shadow/otf/`.
- Confirm recipe with outline fingerprints (or known-good hash) before renaming — multi-tier and −40/−25 can both arrive as `Geist-*.otf`.

## Verification checklist (after every GUI export)

1. File size in the rounded ballpark (~90 KB+ Regular), not the sharp CLI size (~71 KB).
2. Regular `H` has inner `curveTo`s (expect **4** for these recipes).
3. Name tables: family **Namche-Shadow** or **Namche-Shadow-Simple** (not Geist).
4. Compare a few diagonals (`A`, `V`, `M`) if both families exist — multi-tier and Simple must differ.
5. Rebuild `woff` / `woff2`; refresh `~/Library/Fonts/<Family>/` and the `:8765` specimen.

## Tooling split

| Tool | Use for |
|------|---------|
| `apply_roundcorner_filters.py` | Two-radius pairs (**Shadow-Simple** / experiments) |
| `roundcorner_shadow_filters.txt` | Multi-tier **Namche-Shadow** paste into Glyphs statics |
| `glyphs_export_namche_shadow.py` | Glyphs Macro → export OTFs into `exports/Namche-Shadow/otf/` |
| `inner_round_app.py` | Local specimen (`PREVIEW_FAMILIES`) |

Multi-tier is maintained in Glyphs / the paste file; the two-radius Python helper is not a substitute for that stack.

## Local delivery layout

```
exports/
  Namche-Shadow/           # primary multi-tier + package + _received
  Namche-Shadow-Simple/    # −40/−25 + package + _received
```

`exports/` is gitignored; binaries ship on GitHub Releases. Docs and scripts in git are the reproducible recipe.

## Package hygiene after renames

When renaming families (e.g. temporary **Namche-Darth** → **Namche-Shadow**), rewrite not only `familyName` and OTF name tables but also instance `fileName` custom parameters (VF often keeps `Namche-Darth[wght]`). Strip trailing commas in RoundCorner `include:` / `exclude:` glyph lists — Glyphs paste can leave `six, ` which should be `six`.
