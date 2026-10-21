# Upright VF provenance and corrected open build

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
Editing point counts/order requires migrating the deltas too; it is not a set of
ordinary cubic Glyphs design masters. Changing a RoundCorner parameter is no
longer an automatic operation. Google Fonts acceptance of this source layout
has not been established. A future ergonomic designspace migration must preserve
the pinned release geometry rather than silently reconstructing it from the
incompatible static OTFs.

## Repository workflow

Install `requirements-open-build.txt` in an isolated Python 3.11 environment.
HarfBuzz 0.53.3 is pinned alongside FontTools: its layout repacker is explicitly
required, since the pure-Python fallback serializes different bytes.
Run `make check-sans-open PYTHON=python` for two clean builds, SHA-256 validation
and comparison to the committed release. `make build-sans-variable` writes the
release artifacts using the full repository build environment. The complete
release build also regenerates and verifies upright before creating artifacts.

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

This adds the byte-preserving upright production build only. Italic and static
production paths retain their existing sources and checks. The preserved
quadratic/TTX representation is not a reconstructed cubic designspace, and
Google Fonts acceptance of this source organization remains unverified.
