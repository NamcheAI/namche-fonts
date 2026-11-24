# Documentation

This directory contains maintained release text, quality-assurance policy, and
reviewed visual evidence. Generated build reports belong in `out/`; transient
design experiments belong in an issue or pull request rather than here.

## Maintained documents

- [`GOOGLE_FONTS_READINESS.md`](GOOGLE_FONTS_READINESS.md) records the 0.6.2
  submission blockers, open-build evidence and current Google Fonts QA.

- [`FONTSPECTOR.md`](FONTSPECTOR.md) records the accepted Fontspector baseline
  and explains which warnings are regressions.
- [`LANGUAGE_SUPPORT.md`](LANGUAGE_SUPPORT.md) defines the supported shaping
  contract and intentional auxiliary omissions.
- [`TRUSTED_PUBLISHING.md`](TRUSTED_PUBLISHING.md) documents the npm OIDC
  publisher configuration and recovery procedure.
- [`PROJECT_HISTORY.md`](PROJECT_HISTORY.md) summarizes the decisions made
  before and during the Geist-style repository migration.
- [`DESCRIPTION.en_us.html`](DESCRIPTION.en_us.html) and
  [`article/ARTICLE.en_us.html`](article/ARTICLE.en_us.html) are release
  metadata copied into font distribution archives.
- [`ASSET_LICENSES.md`](ASSET_LICENSES.md) records the licensing and ownership
  of documentation visuals.

## Reviewed proofs

[`proofs/`](proofs/README.md) contains visual records that are still cited by
the QA baseline. The issue-specific panels are indexed in
[`proofs/issues/README.md`](proofs/issues/README.md).

Proof images support human review; they are not test fixtures. Automated
invariants belong in `tests/` and the maintained `scripts/check_*.py` checks.
Obsolete exploratory images remain recoverable from Git history and should not
be retained in the current tree solely as an archive.

The canonical README banners live in `.docs/img/` and are regenerated with
`make images`.

## Current character scope

All Namche families now use exactly GF Latin Core (319 characters). Bundled
upstream Geist is unchanged. See [migration and character review](LATIN_CORE_REVIEW.md)
for every-character proofs, compatibility impact and current QA findings.
