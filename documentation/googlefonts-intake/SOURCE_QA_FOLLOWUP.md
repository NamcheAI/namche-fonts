# Source reconstruction and candidate mark correction

Investigation for #116, 2026-10-25. Designer: [Michael Marte](https://github.com/fizzybubbele)
for [Ruhm etc.](https://ruhmetc.com/).

## Exact editable masters

The histories of the original static PR #10 and variable PR #15 were fetched,
including their pre-squash commits. The variable PR changed the filter recipe
and committed its final TTF/WOFF2, but did not commit the compatible rounded OTF
masters. Older OTF revisions are the static exports already distinguished in
OPEN_BUILD.md. GitHub's available artifact inventory contains no August build
artifacts. This search did not recover the historical cubic masters.

We can nevertheless reconstruct the exact approved quadratic masters:

```sh
venv/bin/python scripts/reconstruct_sans_masters.py --output out/reconstructed-masters
```

This writes a designspace and nine editable UFO masters for each style, all
970 glyphs, plus layout XML and a variation structure map. The map records
supports and explicit point indices, not delta values. Delta values are derived
from the saved UFO coordinates. The verification reloads those saved files,
reconstructs the variation data, builds twice, and compares the complete TTF
and WOFF2 with the approved release hashes. All four files match byte-for-byte.
The output difference is zero, including intermediate weights and shaping.

For comparison, a fresh scan of 18 representative glyphs at all nine named
weights against the native OTF statics found maximum sampled outline distances
of 3.800585 units upright and 3.692582 italic on a 1000-unit em. Both maxima were
Scedilla. At 16 px, 3.800585 units is about 0.061 px. This is the existing VF/static
difference, not an error introduced by the reconstruction. The measurement uses
four-unit outline sampling and is not an exhaustive curve-distance guarantee.

The masters use the exact quantized variation peaks. Their designspace weights
therefore differ slightly from nominal integers (for example 199.99389648).
Rounding those locations or changing point topology would invalidate exact
interpolation. The original cubic Glyphs exports and filter workflow have not
been recovered. The production build still uses the existing UFO/TTX sources;
this is a verified conversion and editing artifact, not an unreviewed migration
of the normal build or a claim of Google Fonts source-format acceptance.

An exported directory builds independently of the original variation XML:

```sh
venv/bin/python scripts/reconstruct_sans_masters.py \
  --build-from out/reconstructed-masters/NamcheShadowSans-Upright \
  --output out/reconstructed-masters/rebuilt
```

Point-order changes and edits that cannot be represented by the saved explicit
point structure are rejected rather than silently discarded.
Components are not supported in these flattened quadratic masters. Advance
widths must match the recorded phantom metrics; ordinary width edits require
a separate metric-variation migration and are rejected before compilation.

## Candidate-only U+0331

The submission builder now adds a real combining macron below to both candidate
VFs, using the existing macron's shape and weight progression. Its top follows
the existing dot-below clearance; italic placement follows the font's slant.
The mark has zero advance, mark-to-base and mark-to-ligature positioning, and
mark-to-mark attachment with variable stacking anchors.

The recipe runs on fonts built from the open sources before packaging. It
verifies that all 970 existing glyph outlines, variation tuples, advances and
sidebearings remain unchanged. Name, GSUB, STAT, fvar and OS/2 tables are protected.
Regression tests check existing text positions, new mark attachment, zero
advance and non-overlapping repeated below marks across both styles and weights.
The nine-weight visual proof is `documentation/proofs/issues/issue-116-macron-below.png`.

This deliberately extends the candidate rather than the npm/release family.
Its manifest records the addition. The unmodified production archive still
matches the approved release. Both archives remain reproducible.

## What the full official QA now says

Fontspector 1.9.0 reports 264 PASS, 112 WARN, 10 FAIL, 72 SKIP and 17 INFO
messages. No ERROR/FATAL. The three missing-glyph/sample failures are gone.
The increased FAIL count comes from additional inferred language samples whose
glyphs now exist but whose combining marks the tested subset data omit:

- U+0302: Aleut.
- U+0331: Amarakaeri, Chickasaw, Central Mazahua, Otomi (Mezquital), Secoya,
  Siona and Ticuna.
- U+0338: another Central Mazahua sample; this glyph already existed.
- The existing HTML repository-link false positive remains.

The exact new serving findings replace the previous missing-glyph findings in
the candidate regression baseline. They are not waived or presented as passing.
The extended-subset warnings and other warning count are unchanged.

The concrete serving correction is to include U+0302, U+0331 and U+0338 in
Google Fonts' Latin extended subset data. A patch against the pinned data is
included as `latin-ext-marks.patch`. The fonts alone cannot change Google's
subset definitions. Adding unrelated script subsets or deleting supported
characters is not an acceptable correction. Intake must request the serving
change and verify the resulting delivered fonts before claiming completion.

## Why plain text does not solve the URL check

Fontspector's `description/git_url` requires an actual repository hyperlink.
Plain text removes that hyperlink and introduces `lacks-git-url`. The conflicting
`metadata/consistent_repo_urls` check tokenizes raw HTML rather than parsing its
links. Its canonical bare repository token cannot also be a normal HTML href.
Retain valid links and the correct Michael Marte for Ruhm etc. attribution;
request an upstream parser fix. Do not encode or obscure the URL to evade the
broken token check. The independent semantic link validation remains mandatory.
