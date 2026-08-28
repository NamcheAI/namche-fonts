# Namche Shadow Font development rules

This repository is the source, build, review, and release home for
`NamcheAI/namche-fonts`. It follows the Vercel Geist repository layout,
but Namche-specific source and release decisions take precedence over upstream
conventions.

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
  to enforce the byte match. Geist Mono and Pixel are deliberately not
  bundled: Namche Shadow Mono and Pixel are outline-identical renames of the
  same binaries.
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

- The corrected `Namche-Shadow-Edited.glyphspackage` received from Michael on
  2026-08-13 is the visual source of truth for upright statics.
- Import a replacement package with
  `python3 scripts/import_edited_sans.py /path/to/package`. The importer keeps
  repository naming and attribution; do not copy an incoming `fontinfo.plist`
  over the maintained one by hand.
- Ship static Thin through Black instances. RoundCorner filters must run in
  Glyphs 4 during export; `glyphs-cli` and a plain variable-font build do not
  reproduce this treatment reliably.
- Finalize the native Glyphs OTF/TTF exports with
  `make finalize-sans-statics GLYPHS_SANS_EXPORT=/path/to/export`: it keeps
  Glyphs' rounded outlines while preserving the current release's OpenType
  layout and metadata, flattens nested TrueType components, produces WOFF2,
  and refreshes the npm font directory. The export path must contain `otf/`
  and `ttf/` subdirectories.
- Keep the complete ordered seven-filter stack. The final tier is
  `RoundCorner;-10;include:Yusbig-cy,yusbig-cy,mu,baht,peso` (Glyphs may
  serialize spaces after commas).
- `Yusbig-cy`, `yusbig-cy`, `mu`, `baht`, and `peso` must export in every
  static. Do not add `Remove Glyphs` to static instances.
- Build the upright variable font only from native Glyphs OTF exports whose
  seven RoundCorner filters use the `compatible` option. Run
  `make build-sans-variable GLYPHS_SANS_EXPORT=/path/to/export`; the builder
  preserves the post-rounding curves, makes the remaining segmentation
  compatible, converts all masters to TrueType curves together, and verifies
  every named instance against its rounded master. Never enable the sharp
  gftools/Glyphs VF as a substitute.
- Keep `Yusbig-cy`, `yusbig-cy`, `mu`, `baht`, and `peso` parked from the
  variable build until their rounded masters match. They must remain in every
  static.
- The italic package is the one Sans exception to the Glyphs-export rule: it
  carries no RoundCorner filters, so its Shadow treatment lives in the masters
  and `gftools builder sources/config-NamcheShadowSans-Italic.yaml` reproduces
  the committed italic outlines exactly. Land an italic source correction with
  `make refresh-sans-italic-outlines`; `scripts/refresh_sans_italic_outlines.py`
  replaces only the glyph outlines that changed, refuses a metric change, and
  leaves metadata, layout, and hinting byte-identical. Never rebuild the italic
  release wholesale — that also rewrites metadata the release already carries.
- `scripts/round_inner_corners.py` bakes those italic masters. Its defaults have
  since been retuned for upright work; pass `--italic-recipe` to reproduce the
  profile the shipped italics were baked with. `make check-sans-counters` blocks
  the boolean-topology regression that collapsed the italic `A` counter (#78).
- Namche Shadow Mono remains an outline-identical renamed Geist derivative.
  Pixel may diverge only through a focused issue and reviewed design proof;
  U+20B9 **₹** is the first approved addition and follows the inherited Geist
  rupee construction on Pixel's existing 38-unit component grid. U+25CC **◌**
  is the second approved addition: a 16-component ring on the same grid with
  `top`, `topright`, `center`, `bottom`, and `ogonek` anchors.
- `scripts/finalize_pixel_statics.py` restores the source's inkless U+2028 and
  U+2029 glyphs and all source-defined `caret_*` positions (including `fi` and
  `fl`) after native Pixel statics are restored. It also merges reviewed new
  Pixel glyphs from the reproducible gftools staging build without replacing
  existing native outlines. It may refresh only `GDEF`, `GSUB`, and `GPOS`
  from that same build. `make check-pixel-separators`,
  `make check-pixel-ligature-carets`, `make check-pixel-rupee`, and
  `make check-pixel-shaping` block regressions across release and npm binaries.
- Every release and npm binary uses OS/2 version 4 or later. Sans and Mono set
  `fsSelection` WWS bit 8 and omit name IDs 21/22. Pixel keeps bit 8 clear and
  mirrors its legacy family/subfamily names into WWS IDs 21/22 because the
  Element Shape styles are not weight/width/slope qualifiers. Preserve the
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
- Pull requests rebuild Mono or Pixel only when that family's source or a
  shared build input changes. A Pixel-only change must not pay for a Mono
  rebuild, and vice versa. Sans remains based on reviewed native Glyphs
  exports and is validated rather than rebuilt on Linux.
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
and verify that the five temporarily parked variable glyphs are present in all
Sans statics.

Do not dismiss Fontspector output merely because CI currently marks the step as
non-blocking. Summarize new warnings in the PR, distinguish upstream/pre-existing
warnings from regressions, and fix regressions before merge. See
`documentation/FONTSPECTOR.md` for the maintained baseline.
`scripts/check_language_shaping.py` is the blocking exception: every Sans and
Mono TTF/VF must pass `soft_dotted`, and language-shaping warnings may contain
only documented auxiliary omissions.
