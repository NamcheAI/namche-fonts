# Shadow Sans review proofs

The November 23 revision compares Michael Marte’s requested changes with the previous PR #126 build at `fc9062d`. For the heavy counters, the measurements also include the Latin Core build at `bbdc0fd` that preceded the PR. [Michael’s first review](https://github.com/NamcheAI/namche-fonts/issues/125#issuecomment-7103017258) · [Lowercase joins](https://github.com/NamcheAI/namche-fonts/issues/125#issuecomment-7103995878) · [Default y decision](https://github.com/NamcheAI/namche-fonts/issues/125#issuecomment-7104336521)

| Proof | What to inspect |
| --- | --- |
| [Changed contours](changes.png) | The default y in both slopes, the bowl-to-tail transition in a, the n shoulder, upright 4 and italic A. Gray is shared by both builds, magenta shows removed ink and teal shows added ink. |
| [Upright outlines](outlines-upright.png) · [Italic outlines](outlines-italic.png) | Six weights at matching size and baseline, including the five encoded y forms, lowercase joins and currency symbols. |
| [Upright text](text-upright.png) · [Italic text](text-italic.png) | Regular 400 at every integer size from 11 to 16 px. Open at native resolution to compare the static and variable font in each build. |

## Measured results

At each pixel size, the rendering check sums 8-bit FreeType grayscale coverage for the same two lines of text. A positive percentage means that the VF lays down more ink than the static at the same weight and size. The measurements used FreeType 2.14.3 with Pillow 12.3.0 and RAQM shaping.

| Regular 400, 11–16 px | Previous VF versus static | Revised VF versus static |
| --- | ---: | ---: |
| Upright | +5.45% to +9.83% | −0.01% to +1.00% |
| Italic | +6.93% to +10.33% | +0.40% to +0.87% |

Across all nine weights and both slopes, the revised prose sample ranges from −0.86% to +1.51%. A separate comparison covering all 319 Latin Core characters ranges from −0.35% to +1.01%.

The white area in italic **A** grew by 6.90% at Bold and 16.21% at Black against the previous PR head. Upright Black **4** gained 13.11%. Against the earlier Latin Core reference, the respective differences are +0.39%, +2.16% and +2.99%.

The horizontal step at the base of **y** measured 8–40 font units in the previous binaries. Its measured length is now zero across all 18 statics and 66 VF instances, sampled from 100 through 900 every 25 units in each slope. Every sampled **ý ÿ ŷ ỳ** has exactly the same base outline as the matching **y**.

[All 108 rendering comparisons](rendering.csv) · [Heavy counter areas](counters.csv) · [Methods, font hashes and y measurements](manifest.json)

## Reproduce

From the repository root, extract the two reference snapshots and run the proof on the current Sans TTFs.

```sh
proof_inputs=$(mktemp -d)
mkdir -p "$proof_inputs/previous" "$proof_inputs/pre-pr"
git archive fc9062dc16564814be34d93fba84468fb85d1e7d -- fonts/NamcheShadowSans/ttf fonts/NamcheShadowSans/variable | tar -xf - -C "$proof_inputs/previous"
git archive bbdc0fd6f436316347e40bc15c243df3fd957a6d -- fonts/NamcheShadowSans/ttf | tar -xf - -C "$proof_inputs/pre-pr"
venv/bin/python scripts/proof_equal_ink_review.py \
  --before "$proof_inputs/previous/fonts/NamcheShadowSans" \
  --counter-reference "$proof_inputs/pre-pr/fonts/NamcheShadowSans" \
  --after fonts/NamcheShadowSans --output "$proof_inputs/review"
```

The first review build and its original comparison are preserved in the [targeted sheet](../00-targeted.png), [intermediate-weight sheet](../19-intermediate-vfs.png) and [first-round manifest](../proof-manifest.json).
