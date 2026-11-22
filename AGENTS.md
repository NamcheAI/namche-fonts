# Namche font development rules

This repository is the source, build, review, and release home for
`NamcheAI/namche-fonts`. It follows the Vercel Geist repository layout,
but Namche-specific source and release decisions take precedence over upstream
conventions.

## Character scope

All Namche families, working sources, generated releases, npm assets and the
Google Fonts candidate encode exactly the 319 characters in
`sources/charsets/GF_Latin_Core.nam`. Keep necessary unencoded components,
ligatures and alternates. Run `scripts/check_latin_core.py` after source imports
and builds. Historical evidence is not an active coverage declaration.
`originals/geist/` and the bundled upstream `fonts/Geist/` remain unchanged.

## Sources and ownership

- `sources/` contains the working Glyphs packages and builder configuration.
- `fonts/` contains generated release binaries. Commit regenerated binaries
  together with the source change that produced them.
- `originals/geist/` is an immutable copy of the upstream Geist source. Never
  edit, rename, or regenerate files there.
- `fonts/Geist/` is a committed byte-faithful copy of the upstream Geist Sans
  variable webfonts from the npm package pinned in
  `sources/geist-upstream.json`, bundled so applications can serve their Geist
  body font from the same CDN release and npm package. Never rename its
  metadata or edit its binaries; refresh it only with `make update-geist`
  after bumping the pin, and rely on `scripts/vendor_geist.py --check` (CI)
  to enforce the byte match. Geist Mono is deliberately not bundled: Namche
  Shadow Mono is an outline-identical rename of the same binaries. Geist Pixel
  is not bundled either; Namche Shape is a new design generated from its grid.
- Preserve the SIL Open Font License, the original Geist/Vercel copyright and
  author credits, and the Namche attribution already present in source and
  binary metadata.
- Credit Michael Marte as the designer of Namche Shadow Sans and link both his
  GitHub account (`fizzybubbele`) and Ruhm etc. (`https://ruhmetc.com/`) in
  user-facing credits. AI tools are tooling assistants, not designers or
  copyright authors.
- Michael's approval is not a default merge gate. Tag him when an issue depends
  on designer-supplied source, needs his specific historical context, or
  explicitly requests his review; otherwise the project reviews and approves
  focused design work through its normal issue, proof, PR, and CI workflow.

## Namche Shadow Sans production rules

- Michael's corrected upright package received on 2026-08-13 remains design
  provenance and supplies maintained identity, metrics, components, anchors,
  and layout. The geometric inputs are pinned in
  `sources/equal-ink/clean-outlines.json`. Issue #125 replaces the historical
  seven-tier RoundCorner export with the compatible equal-ink recipe in
  `scripts/equal_ink_corners.py`.
- `sources/equal-ink/clean-outlines.json` pins unrounded upright foregrounds
  and immutable Geist italic foregrounds. Historical italic backgrounds are
  not trustworthy design inputs: some contain upright forms. Never derive a
  clean input by reversing or repeatedly rounding the baked output.
- `make build-sans` bakes compatible cubic Glyphs masters and builds all 18
  statics plus both VFs with open tools. The rule uses the measured stem with
  c=1.2 and caps 70 (capitals/figures) or 53 (other glyphs); acute curved joins
  solve actual added area. Obtuse joins and the 45% flank limit are explicit
  exceptions to equal area. Preserve sparse brace layers and matched topology.
- The maintained Glyphs packages carry the generated rounded foregrounds plus
  repository metadata, components, anchors and layout. Commit these packages,
  clean inputs, the recipe, recovered production snapshots and regenerated
  binaries together after an intentional design change. Do not reintroduce
  native RoundCorner filters or use the historical italic recipe for releases.
- `sources/equal-ink/release-metadata/` is the text-only identity/layout contract.
  Finalization preserves names, attribution, shaping and static advance widths,
  removes obsolete point hint programs and reports any one-unit normalization
  of unencoded static ligatures. Encoded or variable metric changes are refused.
- `make check-sans-equal-ink` rebuilds the full recipe and compares every binary
  with the committed release. `make check-sans-open` independently builds both
  quadratic UFO/TTX production snapshots twice and checks their pinned hashes.
  `make build-sans-variable` can rebuild just those snapshots. Point topology
  changes require synchronized variation deltas, point-order maps and hashes.
  See `documentation/EQUAL_INK.md` and `documentation/OPEN_BUILD.md`.
- Source imports must preserve repository naming and credits. Reconcile a new
  clean source explicitly with `clean-outlines.json`; the historical importer
  alone is not a complete equal-ink migration.
- `make build-googlefonts` creates a separate **Namche Shadow** candidate family
  with complete STAT-matching style names, all within 32 characters. Existing
  release/npm names remain **Namche Shadow Sans**. Package renaming may change
  only the name table and checksum adjustment; preserve every other table.
  The candidate has the same exact GF Latin Core encoding as the release.
  Do not add candidate-only characters outside the pinned scope.
- Validate the compiled 319-character set in upright and italic at named and
  intermediate weights with `scripts/check_equal_ink.py`, and run the existing
  counter, metadata, shaping and Fontspector checks. Local source checks alone
  do not prove that quantized/interpolated binaries preserve the design.
- Namche Shadow Mono preserves upstream outlines for its retained Latin Core glyphs.

## Namche Shape production rules

- Namche Shape (Metaball, Origin, Skeleton; designed by Michael Marte for
  Ruhm etc.) replaced Namche Shadow Pixel on 2026-09-29. Its grid source is
  `sources/NamcheShape.glyphspackage`, restricted to GF Latin Core with
  unencoded component and layout dependencies. Every base glyph is a set of
  38-unit `pixel` components. Grid edits need a focused issue and design proof;
  `make check-source-copies` checks retained geometry against the immutable
  upstream archive, with the recorded scope migration in `sources/charsets/`.
- `scripts/namche_shape.py` turns the grid into outlines and
  `scripts/build_namche_shape.py` (`make build-shape`) compiles OTF, TTF, and
  WOFF2 with ufo2ft, keeping the source's metrics, kerning, anchors, carets,
  and OpenType features. Commit regenerated binaries with any change to the
  recipe, the source, or `sources/NamcheShape/overrides.yaml`.
- Random choices are seeded from style and glyph name. Keep them seeded;
  never use unseeded randomness. Refine a glyph through
  `sources/NamcheShape/overrides.yaml`, not by editing binaries, and review
  the result with `scripts/proof_namche_shape.py`.
- Every non-mark glyph has seeded `.shape1` to `.shape3` alternates
  (variant seeds `name#N`); a single `calt` chaining lookup rotates them by a
  step coprime with the variant count, so four repeats show four variants.
  Alternates inherit width, anchors, carets, kerning groups, and production
  names from their default glyph.
- Skeleton must stay connected: its trace is a randomized spanning tree of
  each pixel component plus random extra links, so no stroke is lost. Links
  along a stroke are always drawn (the rails stay whole); rungs across a
  stroke are random; only 2x2 dots stay solid.
- Origin turns its round shapes toward open stroke edges and corners
  (`ORIGIN_MODE = "structure"`, inspired by Nigel Cottier's *Letterform
  Variations*); Metaball melts along strokes more often than across them.
- `make check-namche-shape` blocks regressions across release and npm
  binaries: exact GF Latin Core cmap, source widths, retained ligature carets,
  combining-mark attachment and dotless-i behavior. Run
  `make check-namche-shape-reproducible` to compare every generated outline.

## Metadata and layout (all families)

- Every release and npm binary uses OS/2 version 4 or later. Sans and Mono set
  `fsSelection` WWS bit 8 and omit name IDs 21/22. Namche Shape keeps bit 8
  clear and mirrors its legacy family/subfamily names into WWS IDs 21/22
  because its styles are not weight/width/slope qualifiers. Preserve the
  public typographic family/style names; `scripts/rename_font_metadata.py` is
  the maintained normalization and check.
- For an OpenType-layout-only source change, build a temporary matching family
  with gftools and run `scripts/refresh_shaping_tables.py` against the approved
  release family. The script may replace only `GDEF`, `GSUB`, and `GPOS`; it
  verifies that outlines, variation data, and metrics remain byte-identical.

## Required workflow

1. Start with a GitHub issue for a font bug or design correction. Record the
   expected visual result. Designer approval is required only when the issue
   explicitly says so; do not infer a Michael review gate from the fact that a
   change is visual.
2. Create a focused `codex/<topic>` or `jodok/<topic>` branch. Never push
   directly to protected `main` and never force-push `main`.
3. Keep changes single-topic. Do not mix a font correction with unrelated
   cleanup.
4. Use Conventional Commit messages and PR titles (`fix:`, `feat:`,
   `refactor:`, `docs:`, and so on). Commits made through the maintainer's agent
   environment are authored as `Jodok Batlogg <jodok@batlogg.com>`; the agent
   may add its own `Co-Authored-By:` trailer but must never replace the human
   author. Credit designer-provided source drops in the issue, PR, and project
   history.
5. Add a Changesets file under `packages/next/.changeset/` for every
   user-visible npm change. Use patch/minor/major according to SemVer.
6. Open a PR, let GitHub Actions build and test it, request `@codex review`, and
   address and resolve every actionable review thread. Merge only when required
   checks are green and GitHub reports a clean merge state.
7. Squash-merge and delete the branch. Releases are prepared by the Changesets
   PR and published through npm Trusted Publishing; do not publish manually
   with a local npm token.

### CI execution

- The fast `Validate committed release fonts` job checks committed binaries
  directly with `requirements-checks.txt`; generated npm font fixtures are
  assembled from those binaries before the release checks run. The required
  `Build and test` check aggregates that result with every applicable family
  rebuild, so a source-build failure cannot be bypassed by the fast path.
- Pull requests rebuild Mono or Namche Shape only when that family's source or
  a shared build input changes. A Namche Shape change must not pay for a Mono
  rebuild, and vice versa. Sans statics and VFs are rebuilt with the equal-ink recipe when Sans inputs
  change. Both VF production snapshots and Google Fonts candidate packages are
  rebuilt from open sources on Linux on every PR. Byte equality, package reproducibility and
  the candidate QA regression gate are mandatory. Known open submission findings
  remain visible in QA_STATUS.json; a green candidate build is not GF acceptance.
- Fontspector runs only for families affected by the PR. Full proofs, release
  ZIPs, npm artifacts, Pages assets, and the complete cross-family build run on
  `main`, tags, or manual dispatches.
- This repository is public and uses GitHub-hosted runners only. Namche
  self-hosted runners are reserved for private repositories.
- Keep the required workflow itself unconditional. Use job/step conditions for
  expensive work so path filtering cannot leave the required check pending.
- PR concurrency must cancel superseded runs; a new push should not wait behind
  obsolete font builds from the same pull request.
- Keep Changesets major versions compatible: `@changesets/cli` v3 requires
  `changesets/action` v2. The v1 action parses the old CLI v2 tag output and can
  silently leave a successful npm publish without its GitHub release or font
  ZIP. Preserve the v2 input names and the post-publish ZIP upload gate.

## Validation before a PR

Run the checks relevant to the change, preferably all of these for a font
source update:

```sh
make build
make test
make proof
make check-source-copies
venv/bin/python scripts/rename_font_metadata.py --check fonts
cd packages/next && npm pack --dry-run
```

Additionally, inspect representative inner corners (`H`, `E`, `a`, diagonals,
and figures) in every changed weight. Confirm the family names and credits in
the built name tables, verify that the Sans statics contain no `fvar` table,
and run `venv/bin/python scripts/check_latin_core.py`.

Do not dismiss Fontspector output merely because CI currently marks the step as
non-blocking. Summarize new warnings in the PR, distinguish upstream/pre-existing
warnings from regressions, and fix regressions before merge. See
`documentation/FONTSPECTOR.md` for the maintained baseline.
`scripts/check_language_shaping.py` is the blocking exception: every Sans and
Mono TTF/VF must pass `soft_dotted`, and language-shaping warnings may contain
only documented auxiliary omissions.
