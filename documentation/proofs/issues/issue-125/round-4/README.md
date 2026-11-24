# Shadow Sans · final outline review

Michael approved the Thin lowercase joins, the taper through the light weights,
and the shape of the default **y** in the third revision. He asked to smooth a
small ripple before the flat terminal of italic **y** and the point where
several light lowercase fillets meet their bowls. These sheets compare the
compiled revision with `66120c2`, the exact build he reviewed.
[Michael’s fourth review](https://github.com/NamcheAI/namche-fonts/issues/125#issuecomment-7124584259) ·
[Designer’s close-ups](https://github.com/NamcheAI/namche-fonts/tree/f085ee0aefa70129d1c473e8dadf2141042e0c2d/documentation/proofs/issues/issue-125/runde-4)

| Where to look | Comparison |
| --- | --- |
| **Italic y** just before the flat terminal | Regular and Medium in the statics and variable font, plus a variable instance at 450. [Terminal close-ups](y-terminal.png) |
| **Upright b and u** where the fillet joins the bowl | Compare weights 150, 200, 250 and 300. Michael flagged 250–300 in particular. [Upright close-ups](tangent-upright.png) |
| **Italic b, n and p** at the same transition | Compare weights 150–300, especially the three lightest instances. [Italic close-ups](tangent-italic.png) |
| **Regular at 11–16 px** | Open the PNG at native resolution to compare the static and variable versions of the same two lines. [Upright](text-upright.png) · [Italic](text-italic.png) · [All 108 rendering comparisons](rendering.csv) |

The close-ups use a fixed crop for each before/after pair and four pixels per
font unit. Each VF instance is frozen, serialized and reopened so the sheets
show the integer outline Michael inspected. Magenta marks removed ink and teal
marks added ink. The text-size proofs instead rasterize the variable font at
the chosen weight directly with FreeType.

| Measurement on the rebuilt fonts | Result |
| --- | --- |
| Italic y, maximum turn between curves before the flat terminal | Regular VF went from 13.13° to 0° and Medium from 29.05° to 0°. The inward dent in those two VF instances now measures 0.000 font units. All 33 frozen VF weights and the four Regular/Medium static TTF and OTF cases measure 0° to three decimals. [Terminal measurements](y-terminal.csv) |
| Light b/u upright and b/n/p italic | The largest curve-to-curve turn inside each of the 20 pictured crops is now 0°. The previous maxima ranged from 1.33° to 15.07°. [Measurements for each crop](tangent-crops.csv) |
| Added Thin ink across the ten reviewed lowercase letters, against Geist | Upright went from 13,078 to 13,099 square units (+0.16%). Italic went from 12,675 to 12,705 (+0.24%). [Ink by slope and weight](lowercase-ink.csv) |
| Regular at 11–16 px | On the two proof lines, variable versus static ink ranges from −0.030% to +0.995% upright and +0.476% to +0.556% italic. [Measurements at every size](rendering.csv) |

The former y ledge measures zero across all 18 static TTFs and 66 VF samples.
The four accented bases match the default y at each of these locations. The
heavy A, 4 and # counter areas match the reviewed build in both slopes.
[Accented y comparison](manifest.json) · [Heavy counter areas](counters.csv)

## Reproduce the sheets

Use the rebuilt Sans family in the repository and extract the previous PR fonts.

```sh
proof_inputs=$(mktemp -d)
git archive 66120c26117ff2488e72449f0eb9ba0138851405 -- fonts/NamcheShadowSans | tar -xf - -C "$proof_inputs"
venv/bin/python scripts/proof_equal_ink_review.py \
  --before "$proof_inputs/fonts/NamcheShadowSans" --after fonts/NamcheShadowSans \
  --tangent-details --output "$proof_inputs/proofs"
```

[Input and output hashes, rendering method and accented y checks](manifest.json) ·
[Earlier review and approval references](../round-3/README.md)
