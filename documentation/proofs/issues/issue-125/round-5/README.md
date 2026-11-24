# Shadow Sans small figures

Michael’s final review singled out the triangular counter in the small **4**. This round compares the same glyph and weight in the pinned Geist 1.7.2 webfonts, the approved Shadow Sans build `6ab84d8`, and the revised release. Michael Marte designed Namche Shadow Sans for Ruhm etc. [Designer’s review](https://github.com/NamcheAI/namche-fonts/issues/125#issuecomment-7131913584) · [Designer’s reference sheet](https://github.com/NamcheAI/namche-fonts/blob/e4b1caa9828d7fba1ba0adfd5b6013fca4f2b9cf/documentation/proofs/issues/issue-125/runde-5/r6_four_small.png) · [Michael Marte](https://github.com/fizzybubbele) · [Ruhm etc.](https://ruhmetc.com/)

| What to inspect | Upright | Italic |
| --- | --- | --- |
| Small 4 at 400, 700 and 900. Each triplet runs from Geist through the previous PR font to the revision. The percentage below each glyph gives its white counter area relative to Geist. | [Four roles](small-four-upright.png) | [Four roles](small-four-italic.png) |
| All ten digits in each role at 100, 400, 700 and 900. The guide marks the ordinary text baseline and shows how the four sets sit in a line. | [Digits and baseline](small-digits-upright.png) | [Digits and baseline](small-digits-italic.png) |
| Regular text, static and VF, at each whole pixel size from 11 to 16. View at native size. | [FreeType proof](text-upright.png) | [FreeType proof](text-italic.png) |

The reading-size sheet renders `3/4` and `4/9` with `frac`, a fourth power with `sups`, and an indexed variable with `subs`. It shows Regular and Black at each native size. At Regular, the VF’s grayscale ink sum exceeds the static’s by 0.25–0.44% upright and 0.39–0.54% italic. The general text samples retain exactly the previous coverage across all 108 slope, weight and size combinations. [Both slopes at 11–16 px](small-figures-text.png) · [Feature-enabled rendering measurements](small-figure-rendering.csv)

## Counter and shaping checks

The clean small 4 stands 387 units high against 710 for the full-size 4. Applying that scale to the former 53-unit maximum gives a 28.89-unit cap for all forty small figures. The four positions use the same figure outline, so their counter percentages agree at each weight. [Design and build details](../../../../EQUAL_INK.md)

| Slope | Regular 400 | Bold 700 | Black 900 |
| --- | ---: | ---: | ---: |
| Upright, previous → revised | 78.61% → 92.94% | 76.86% → 91.85% | 76.17% → 92.21% |
| Italic, previous → revised | 80.53% → 93.87% | 78.50% → 94.82% | 78.23% → 94.71% |

All 4,080 measured glyphs, weights and formats retained their enclosed counter count, including 2,856 individual counters. The CSV covers all 40 production glyphs in both slopes at 33 live VF positions in 25-unit steps from 100 through 900, plus all nine static weights in TTF and OTF. The numerators and denominators use `numr` and `dnom`. Superiors and inferiors use `sups`, `subs` and `sinf`. These are OpenType forms of the encoded digits in the Latin Core release. [Counter measurements](small-figure-counters.csv)

White areas are square font units in a 1000-unit em. All three outlines use the same coordinate scale and matching weight. Closed regions are measured from nonzero-filled contours, with Béziers flattened to a 0.01-unit tolerance. A zero-counter row records a glyph with no enclosed white region. Multiple counters are listed bottom to top.

The proof shapes every digit with each numeric feature, ordinary digits without features, and a fraction built from ASCII digits and a slash. All 816 shaping comparisons retained identical glyph names, clusters, advances and offsets. The upright VF changed 40 small figures and the italic VF changed 36. The other outlines, layout tables and advances matched the previous release in both VFs and all 36 statics. The manifest lists each changed outline, input SHA-256 hashes and output hashes. [Build and validation manifest](small-figure-manifest.json)

## Reproduce

From the repository root, extract the reviewed fonts and run the proof against the rebuilt release.

```sh
proof_inputs=$(mktemp -d)
git archive 6ab84d8510fb87efd1ebe7e196c6d8983ef1e853 -- fonts/NamcheShadowSans | tar -xf - -C "$proof_inputs"
venv/bin/python scripts/proof_equal_ink_small_figures.py \
  --before "$proof_inputs/fonts/NamcheShadowSans" \
  --after fonts/NamcheShadowSans \
  --output "$proof_inputs/round-5"
```

[11–16 px rendering data](rendering.csv) · [Previous review](../round-4/README.md)
