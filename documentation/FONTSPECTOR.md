# Fontspector baseline

Run `make test` after `make build`. The command writes machine-readable JSON
reports to `out/fontspector/`. CI uploads that directory with the other proof
artifacts. JSON is used because the crates.io build of Fontspector 1.7.4 does
not include the optional Jinja templates required by its HTML/Markdown
reporters.

The test currently reports existing Google Fonts profile findings. The step is
non-blocking while the baseline is being reduced, but new findings are not
automatically acceptable: compare the report before and after every font
change.

Language shaping is the blocking exception. At the end of `make test`,
`scripts/check_language_shaping.py` rejects any Sans or Mono soft-dotted
failure, mark-attachment failure, or primary/mandatory orthography omission.
The only accepted `shape_languages` warnings are the optional characters
listed in [`LANGUAGE_SUPPORT.md`](LANGUAGE_SUPPORT.md).

## Current failures

| Family | Finding | Interpretation |
| --- | --- | --- |
| Sans and Mono statics | `repo/dirname_matches_nameid_1` | The Google Fonts profile interprets the distribution folder `ttf/` as a Google Fonts family directory. This repository deliberately uses the Geist-style `fonts/<Family>/ttf/` layout, so this is a profile/layout mismatch. |
| Mono italic variable | `googlefonts/fvar_instances` | The three Word-compatible named-instance aliases intentionally differ from the full STAT weight labels. This satisfies the universal 32-character family-and-style limit while preserving the public typographic names, but it would block a Google Fonts submission. |
| Pixel statics | `googlefonts/canonical_filename`, `googlefonts/font_names` | Correct WWS IDs 21/22 expose Circle, Grid, Line, Square, and Triangle to the Google Fonts profile as separate Regular-only families. That profile consequently expects filenames/full/PostScript names such as `NamcheShadowPixelCircle-Regular`, conflicting with the intentionally retained public typographic family/style model and release filenames. This is expected for the direct/npm distribution but would need a separate naming model for a Google Fonts submission. |

Namche Shadow Sans VF currently has **no Fontspector failures**. Its 26 warning
results are the existing outline, glyph-reachability, language-shaping, WWS,
vendor-ID, and sidebearing groups described below, plus:

- `file_size`: the unsubsetted 970-glyph TTF is 1.2 MB (the shipped WOFF2 is
  substantially smaller).
- `mandatory_avar_table`: the `wght` axis intentionally uses a linear mapping.
- `interpolation_issues`: heuristic kink/start-point findings in a small set of
  inherited rounded glyphs. The reviewed baseline is `uni0163`,
  `ordfeminine`, `uni0472`, `uni04E9`, and `ampersand`; any newly reported
  glyph is a regression until reviewed. The `uni0163` start-point report is a
  cyclic contour-start choice and cannot change the rendered outline. The kink
  markers identify intended curves that remain visually smooth through the
  weight axis.

All nine named VF weights were compared with Michael's approved rounded
statics for the five reported glyphs. Their sampled outlines stay within 5.76
font units on a 1000-unit em. `scripts/check_sans_variable.py` keeps a 7-unit
regression limit and fingerprints the five glyphs' coordinates, curve flags,
and contour endpoints at weights 150, 250, 350, 450, 550, 650, 750, and 850.
This reviewed geometric baseline catches any intermediate shape change, not
only empty glyphs. The visual comparison is maintained in
`documentation/proofs/issues/issue-22-variable-interpolation.png`: dark shapes are
shared by the VF and static; blue/red fringes show their small segmentation and
rounding differences. Do not move points merely to silence these heuristics;
reopen design review and regenerate the baseline if the proof, digest, or
guarded distance changes.

## Warning groups

- Outline heuristics (`alignment_miss`, `colinear_vectors`, `jaggy_segments`,
  `short_segments`, `contour_count`) identify shapes for visual inspection;
  they are not proof of a broken outline. Much of this baseline comes from
  upstream Geist and the intentional Pixel geometry.
- `outline_short_segments` has a false-positive cutoff: a font with more than
  100 short segments reports a blanket `PASS` ("probably by design") and lists
  nothing. Removing short segments can therefore turn a `PASS` into a `WARN`
  that enumerates pre-existing shapes. Fixing the italic `A` counter ([#78](https://github.com/NamcheAI/namche-fonts/issues/78))
  did exactly that to `NamcheShadowSans-BlackItalic.ttf`: the collapsed
  counter's hairline slot contributed eight short segments to `A` and to each
  of its composites, and dropping them took the font under the cutoff. The 94
  glyphs it now lists (`B`, `M`, `S`, `OE`, `Eng`, …) are untouched and
  pre-existing — reverting only glyph `A` restores the blanket `PASS`. Compare
  the enumerated glyphs, not the check's severity, when this one moves.
- Glyph reachability and naming warnings flag encoded or substitution access,
  long legacy glyph names, dotted-circle behavior, and language-shaping
  coverage. Pixel retains inherited soft-dotted warnings; Sans and Mono now
  pass that check as a hard gate. Treat any increase as a regression.
- Metadata warnings cover STAT setup, vendor registration, name length, and
  family metadata. These are suitable for focused cleanup PRs rather than
  being mixed into a design-source update.
- Design-consistency warnings such as math-sign widths need a designer/type-
  engineer decision before changing outlines or metrics.

## Reviewed maintenance triage

Issue #23 reviewed the remaining outline, metric, reachability, and Pixel
feature warnings against the rendered release fonts. The corresponding
characters are maintained in
`documentation/proofs/issues/issue-23-outline-metrics.png` and
`documentation/proofs/issues/issue-23-outline-heuristics.png`.

| Warning group | Classification | Decision |
| --- | --- | --- |
| `alignment_miss`, `colinear_vectors`, `jaggy_segments`, `short_segments`, `contour_count` | Intentional design/source heuristics | The rendered Sans, Mono, and Pixel examples show the expected rounded overshoots, interpolation/source points, and Pixel grid geometry. Do not bulk-edit these coordinates. A newly reported or visibly wrong glyph still requires an issue and focused design review; Michael's approval is required only when the issue explicitly requests it. |
| `overlapping_path_segments` | Intentional implementation artifact | Current findings are coincident component edges or zero-length segments produced by source composition and VF compatibility. They have no demonstrated rendering defect; retain them unless a focused source review proves otherwise. |
| `math_signs_width` | Intentional design choice | Sans is proportional, Mono already uses its monospaced advance, and Pixel keeps the inherited shape-specific widths. Do not normalize spacing merely to match the most common glyph width. |
| Mono `opentype/monospace` | Intentional tool mismatch | The current 1139 upright / 1128 italic values are already the minimum for the approved glyph order and metrics. Fontspector hard-codes the OpenType suggestion of `3`, which cannot represent the 39 zero-width marks without changing advances or glyph order. Retain the warning; see [#33](https://github.com/NamcheAI/namche-fonts/issues/33). |
| `opentype/fsselection_wws` | Resolved metadata defect | Sans and Mono set OS/2 `fsSelection` bit 8 and omit name IDs 21/22. Pixel keeps bit 8 clear and uses its legacy family/subfamily names as IDs 21/22 because Element Shape is not a weight/width/slope style. The public typographic names remain unchanged and the central metadata normalizer blocks regressions ([#35](https://github.com/NamcheAI/namche-fonts/issues/35)). |
| Pixel `separator_glyphs` | Resolved export defect | The source and every static release/npm font preserve inkless U+2028/U+2029 glyphs at the reviewed 600-unit width. `make check-pixel-separators` blocks regressions ([#32](https://github.com/NamcheAI/namche-fonts/issues/32)). |
| Pixel `rupee` | Resolved glyph feature | All five Pixel styles now ship **₹**, built from one 109-component design on the inherited 38-unit grid. Its two bars, open bowl, and diagonal follow the original Geist Sans rupee construction while each style retains its own Pixel element shape. `make check-pixel-rupee` guards source, release, and npm coverage ([#34](https://github.com/NamcheAI/namche-fonts/issues/34)). |
| Pixel `dotted_circle`, required `soft_dotted` | Resolved shaping/design feature | All five Pixel styles now ship a 16-component **◌** with anchors for every exported mark. The `ccmp` layout removes the base dot from required **į́ į̌ į̀ į̃ į̄ į̂** and optional **į̆ į̈ į̊ į̒ į̋ į̇** sequences while retaining the ogonek. `make check-pixel-shaping` pins the source recipe, static/variable outlines, HarfBuzz behavior, release/npm coverage, and both Fontspector passes ([#36](https://github.com/NamcheAI/namche-fonts/issues/36)). |
| Pixel `ligature_carets` | Resolved export defect | Every static release/npm font now carries all five source-defined GDEF caret records, including `caret_1 = 342` for **ﬁ ﬂ**. The Pixel finalizer derives them from the maintained Glyphs source, preserves any other caret records, and the binary check blocks regressions ([#37](https://github.com/NamcheAI/namche-fonts/issues/37)). |
| `valid_glyphnames` | Intentional internal naming choice | The release warnings are limited to `asciitilde_asciitilde_greater.liga`, `hyphen_hyphen_hyphen_greater.liga`, `numbersign_numbersign_numbersign.liga`, and `periodcentered.loclCAT.case.ss08`. They are inherited internal GSUB ligature/alternate names. Long descriptive source names for encoded box/block characters are compiled to production `uniXXXX` names and are not part of this warning baseline. Renaming the reported internal names would churn source/GSUB references for a legacy recommendation, with no public API benefit. |
| `unreachable_glyphs`, `unreachable_subsetting` | Source/distributor profile choice | Unencoded working/component glyphs remain available to the source, while this npm/direct-download project has no Google Fonts `METADATA.pb` subset-serving contract. Treat count increases as regressions, but do not remove the baseline solely for this profile. |
| Pixel `soft_hyphen` | Intentional compatibility choice | Retain encoded U+00AD; its presence conflicts with current Google Fonts policy but is valid for the direct font distribution. |
| Sans VF `suspicious_sidebearings` | Mark-metric heuristic | The reported glyph is the combining mark `uni03020301`; its right-sidebearing variation is not user-facing spacing. Reopen only if shaping proof exposes a mark-positioning defect. |

### Mono `numberOfHMetrics`

Issue [#33](https://github.com/NamcheAI/namche-fonts/issues/33)
confirmed that no safe compaction is available under the release invariants.
The upright Mono order contains `.notdef` at 500 units, 39 combining marks at
zero units, and the remaining glyphs at 600 units; italic has the same advance
classes. Since `hmtx` can elide only one trailing run with a shared advance,
FontTools already emits the minimum values for the current order: 1139 upright
and 1128 italic.

The OpenType recommendation says monospaced fonts are *suggested* to use three
long metrics; it is not a conformance requirement. The FontTools discussion
linked by Fontspector explains that this cannot model modern monospaced fonts
with zero-width marks and was closed without a compiler change:

- [Microsoft OpenType recommendations](https://learn.microsoft.com/en-us/typography/opentype/spec/recom#hhea-table)
- [FontTools issue #3014](https://github.com/fonttools/fonttools/issues/3014)

Forcing `3` would change 38 combining-mark advances. Grouping the exceptions
could reduce the TrueType value to 41, but only by changing glyph order, and
Fontspector would still warn because it requires exactly `3`. Both changes are
outside the approved invariants. `make check-mono-hmetrics` blocks any loss of
the safe minimum or the reviewed advance inventory across the TrueType release
and npm files. The proof is maintained at
`documentation/proofs/issues/issue-33-mono-hmetrics.png`.

For Sans, the release-specific acceptance checks are stronger than the generic
profile: every static weight must contain the complete seven-tier RoundCorner
result, `H` must retain the expected four rounded inner segments, the five
tier-7 glyphs must remain in all statics and stay parked from the VF, and no
static may contain an `fvar` table. Run `scripts/check_sans_variable.py` and
review `documentation/proofs/sans-variable-named-instances.png` for the VF.

## Naming compatibility

The Mono italic variable font uses the legacy named-instance aliases `XLight
Italic`, `SemiBd Italic`, and `XBold Italic`. Together with the unchanged
public family name `Namche Shadow Mono`, each stays within the 32-character
Windows/Word limit. The full weight labels remain available in the STAT table.
Google Fonts requires `fvar` instance names to match those STAT labels exactly,
so its distributor-specific `googlefonts/fvar_instances` check necessarily
fails for this compatibility choice. The universal name-length check and the
Google Fonts family-name consistency check both pass.

Some Sans and Mono italic static PostScript names exceed Fontspector's
recommended 27-character legacy guidance. They remain below the OpenType
PostScript-name limit and deliberately keep the canonical
`NamcheShadowSans`/`NamcheShadowMono` prefix: shortening only name ID 6 would
make the binaries internally inconsistent and fail the Google Fonts naming
check. Treat these warnings as an intentional compatibility tradeoff unless a
separate legacy-named distribution is introduced.
