# Shadow Sans · round three

Michael approved the removal of the step from the default **y** and the revised
text color at 11–16 px. He asked for a smoother curve where the arm enters the
descender and less ink at the exterior lowercase joins in Thin. These sheets
compare the rebuilt fonts with the revision he reviewed (`7b470958`).
[Michael’s feedback](https://github.com/NamcheAI/namche-fonts/issues/125#issuecomment-7115664602) ·
[Designer’s comparison sheets and prototype measurements](https://github.com/NamcheAI/namche-fonts/tree/5ef6ee4c998e542f7a38c1656dd9d51aa598bdef/documentation/proofs/issues/issue-125/runde-3)

| What to review | Proof |
| --- | --- |
| **y**, especially Bold and Black | Compare the arm-to-descender junction in all nine weights. Each upright and italic pair uses an identical crop and scale. [Enlarged junctions](y-junction.png) · [Michael’s option B reference, right column](https://github.com/NamcheAI/namche-fonts/blob/5ef6ee4c998e542f7a38c1656dd9d51aa598bdef/documentation/proofs/issues/issue-125/runde-3/r3_y_vorschau.png?raw=true) |
| **Thin** lowercase joins | Compare the exterior joins in **a b d h m n p q r u** at two pixels per font unit. [Upright](thin-joins-upright.png) · [Italic](thin-joins-italic.png) |
| **ExtraLight, Light and Regular** | See the taper in context with the rest of the glyphs. [Upright outlines](outlines-upright.png) · [Italic outlines](outlines-italic.png) · [Contour overlay](changes.png) |
| **Regular, 11–16 px** | At 100% zoom each line is set at its labeled pixel size. Compare static and variable rendering on the same sample. [Upright text](text-upright.png) · [Italic text](text-italic.png) · [All 108 measured comparisons](rendering.csv) |

## Comparison with the option B preview

Each figure is the horizontal root-mean-square distance in font units between
the left edge of the variable **y** and the same edge in Michael’s preview.
The image has 0.95 pixels per font unit. These figures describe agreement with
the raster reference at the sampled scanlines.

| Weight and slope | Previous PR | Revision |
| --- | ---: | ---: |
| Bold upright | 6.92 | 0.83 |
| Black upright | 13.41 | 0.34 |
| Bold italic | 6.42 | 0.32 |
| Black italic | 16.90 | 0.35 |

The [complete comparison](y-reference.csv) includes all seven cases pictured
in the reference and the corresponding static fonts.
The ledge length measures zero in all 18 statics and all 66 sampled VF
instances. The bases of **ý ÿ ŷ ỳ** match the default **y** exactly.

## Thin lowercase ink

The figures are total added ink relative to Geist for **a b d h m n p q r u**,
in square font units. All builds are measured at weight 100. The prototype
figures are Michael’s rounded values from his comparison sheet.

| Slope | Historical Namche | Previous PR | Michael’s 0.4 prototype | Revision |
| --- | ---: | ---: | ---: | ---: |
| Upright | 11,491 | 21,662 | ≈12,700 | 13,078 |
| Italic | 5,071 | 21,645 | ≈13,000 | 12,675 |

Upright comes within 3.0% of the prototype and is 13.8% above historical
Namche. Italic comes within 2.5% of the prototype, which also carries more
ink than historical italic. The [per-glyph measurements](lowercase-ink.csv)
cover the transition to Regular and all heavier named weights.

The ten letters have identical static point sequences from Regular through
Black in both slopes (120 comparisons). In the variable fonts, sampling every
25 weight units from 400 to 900 gives a maximum outline shift of 1.30 font
units from the shared quadratic conversion and interpolation.

## Regular at 11–16 px

The table reports the percentage difference in summed FreeType grayscale
coverage for the same two lines at native pixel sizes. Positive values mean
the variable font laid down more ink than the matching static.

| Slope | 11 px | 12 px | 13 px | 14 px | 15 px | 16 px |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Upright | +0.050% | +1.055% | +0.511% | +0.197% | +0.381% | +0.192% |
| Italic | +0.587% | +0.603% | +0.581% | +0.538% | +0.601% | +0.542% |

## Reproduce the sheets

Start in the repository root with the rebuilt fonts and project virtual environment.

```sh
proof_inputs=$(mktemp -d)
git archive 7b4709581dbaed9dfb923ac0ca7c02d7783bf04c -- fonts/NamcheShadowSans/ttf fonts/NamcheShadowSans/variable | tar -xf - -C "$proof_inputs"
venv/bin/python scripts/proof_equal_ink_review.py \
  --before "$proof_inputs/fonts/NamcheShadowSans" --after fonts/NamcheShadowSans \
  --join-details --output "$proof_inputs/proofs"
```

[Input and output hashes, rendering method, accented y checks](manifest.json) ·
[Counter measurements](counters.csv) · [Earlier review snapshot](../round-2/README.md)

The [y reference measurements](y-reference.csv) compare the compiled left edge
with the rightmost column in Michael’s option B preview. The script verifies the
reference image hash and measures static and variable outlines independently.

```sh
curl -fL https://raw.githubusercontent.com/NamcheAI/namche-fonts/5ef6ee4c998e542f7a38c1656dd9d51aa598bdef/documentation/proofs/issues/issue-125/runde-3/r3_y_vorschau.png -o "$proof_inputs/y-reference.png"
venv/bin/python scripts/measure_y_review.py --reference "$proof_inputs/y-reference.png" \
  --previous "$proof_inputs/fonts/NamcheShadowSans" --candidate fonts/NamcheShadowSans \
  --output "$proof_inputs/proofs/y-reference.csv"
```

To reproduce the [lowercase ink measurements](lowercase-ink.csv), also extract
the Latin Core build that preceded PR #126. The script measures each glyph
once against the bundled Geist variable font at the same weight and slope.

```sh
mkdir -p "$proof_inputs/pre-pr"
git archive bbdc0fd6f436316347e40bc15c243df3fd957a6d -- fonts/NamcheShadowSans/variable | tar -xf - -C "$proof_inputs/pre-pr"
venv/bin/python scripts/measure_lowercase_joins.py \
  --historical "$proof_inputs/pre-pr/fonts/NamcheShadowSans" \
  --round2 "$proof_inputs/fonts/NamcheShadowSans" --round3 fonts/NamcheShadowSans \
  --output "$proof_inputs/proofs/lowercase-ink.csv"
```
