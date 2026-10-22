# Sans VF provenance and open build

Examined release: NamcheAI/namche-fonts 26f8807f8b23a91374057c919f6a2144fe170599.

## Root cause

The upright VF first shipped in commit 327248bddb4609e06b4b0bc6c999cc1b8881a9d6
(PR #15, 2026-08-13). Its glyf, gvar and hmtx tables are byte-identical to today's
release. Later changes preserve these outlines and modify metadata/layout.

The production recipe used nine native Glyphs 4 OTF exports with all seven
RoundCorner filters in `compatible` mode. Their exact historical files and the
Glyphs patch version have not been recovered. These OTF inputs were not committed
with #15. The checked-in upright OTF statics came from #10 (65bfe8b) earlier that day.
Consequently, they cannot be assumed to be the same VF masters.

The #15 dependency lock pins FontTools 4.60.1, NumPy 2.2.6 and Brotli 1.2.0.
The installed experiment environment also uses these versions. A control run with
that commit's original builder and the checked-in static OTFs produces the same
glyf bytes as today's builder, but different glyf bytes from the shipped VF.
Example default-master point counts: E is 20 in the release versus 390 rebuilt;
a is 56 versus 483. This excludes the new italic contour-order code as the cause
of the observed glyf drift and establishes that the checked-in OTFs are not a
reproducible input for the published upright build in this environment.

Sources: https://github.com/NamcheAI/namche-fonts/pull/15
https://github.com/NamcheAI/namche-fonts/pull/82

## Recovery used for the fixed open build

Recover the approved production representation directly, without re-fitting
curves or re-running RoundCorner: 970 quadratic default-master glyphs in an
editable UFO, all gvar interpolation deltas in readable TTX, and layout/metadata
in separate TTX. This is a reconstructed production source, NOT a claim that the
missing original cubic Glyphs exports were found.

The build reads only those text sources. It compiles the UFO using TTGlyphPointPen,
imports variation/layout data and preserves the published table order. No release
binary, Glyphs installation, or proprietary filter is used during the build.
The exact TTF and WOFF2 hashes are enforced by `scripts/build_sans_open.py --check`. Equality covers
every glyph, every position on the weight axis, metrics, shaping and metadata.

## Maintenance boundary

The recovered source exposes fixed point-index topology plus variation deltas.
Stable UFO point identifiers and `point-order.json` guard point order and contour
boundaries before applying the indexed deltas. Preserve identifiers when editing
coordinates; changing counts/order requires migrating the deltas and this map too; it is not a set of
ordinary cubic Glyphs design masters. Changing a RoundCorner parameter is no
longer an automatic operation. Google Fonts acceptance of this source layout
has not been established. A future ergonomic designspace migration must preserve
the pinned release geometry rather than silently reconstructing it from the
incompatible static OTFs.

## Repository workflow

Install `requirements-open-build.txt` in an isolated Python 3.11 environment.
HarfBuzz 0.53.3 is pinned alongside FontTools: upright explicitly uses its layout
repacker; italic explicitly disables it to retain the original FontTools packing.
Run `make check-sans-open PYTHON=python` for two clean builds, SHA-256 validation
and comparison to the committed release. `make build-sans-variable` writes the
both pairs of release artifacts using the full repository build environment. The
complete release build regenerates and verifies both VFs before creating artifacts.

The unconditional Linux CI job is included in the mandatory `Build and test`
aggregate and gates release artifact creation. The source contains no input font
binary: UFO contours, indexed variation XML, layout/metadata XML and a provenance
manifest are sufficient. The complete upright output is byte-identical, so every
weight, glyph, shaping behavior, hinting instruction and public name is preserved.

For intentional changes to upright shaping, metadata, or design, update the
corresponding open sources, build, review proofs, then update the manifest and
committed binaries together. In particular, binary-only metadata/layout refreshes
will fail CI until the XML sources and approved hashes are updated. Do not bypass
the gate or reconstruct upright from the incompatible static OTFs.

## Italic production source

`sources/NamcheShadowSans-Italic/` recovers the complete approved 0.6.2 italic VF
(commit `039e0efdd5c404df38491ef4d676af5331e02da9`) into 970 quadratic UFO glyphs,
point identifiers and readable variation/layout TTX. This is an open production
representation, not a recovered cubic designspace. Unlike the former OTF-based
command, the normal build consumes no compiled fonts, including for metadata or
layout. The same point-order guards and two-build hash checks apply to italic.

- TTF SHA-256: `a79f21b2c31ead8e6296be8a12b46c870d0e394840df2cb7eed3d0773e69c439`
- WOFF2 SHA-256: `8400debbacde1fa7b8228cd4d9d085bb3eb188340a2301107871fe8391ce8d9a`

The serializer distinction is intentional: upright uses HarfBuzz repacking;
italic uses pure FontTools layout packing. Both are pinned and produce the
approved complete binary bytes, including all interpolated outlines, shaping,
metrics and public names. No visual approximation is involved.

`scripts/recover_sans_production_source.py` documents the one-time extraction
for provenance or a reviewed future migration. It is not called by normal builds
or CI. It refuses composite/hinted glyph inputs that this representation does
not support. The existing Glyphs packages remain the separate design source;
editing them does not automatically regenerate the recovered production source.
Static production is unchanged. GF acceptance of this source organization remains
unverified. See [candidate packages and remaining gates](GOOGLE_FONTS_READINESS.md).
