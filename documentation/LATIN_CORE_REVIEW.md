# GF Latin Core migration and character review

Branch: `codex/gf-latin-core`. Tracking: [issue #118](https://github.com/NamcheAI/namche-fonts/issues/118).
This is a breaking coverage change, not a new font variant or a redesign.

## Scope

Every Namche family encodes exactly the 319 codepoints in
[`GF_Latin_Core.nam`](../sources/charsets/GF_Latin_Core.nam), pinned to Google
Fonts glyphsets commit `0ac0e515473e39247683ed473fd74728671e2364`.
Necessary unencoded component, ligature and alternate glyphs remain.
The working Glyphs packages, recovered Sans production UFO/TTX, release binaries,
npm assets, CSS ranges and Google Fonts candidate use this contract.
The immutable Geist archive and bundled upstream Geist are unchanged.
Historical issue proofs and intake documents remain historical evidence.

Cyrillic, box drawing, U+0331, U+20B9 and U+25CC are outside the contract.
Existing `-latin` entry points remain available; Namche files now contain the
same Core repertoire as the unsuffixed files. Earlier published versions remain
unchanged. A major Changeset records the compatibility impact.

## Visual review

[Searchable character-by-character atlas](proofs/issues/issue-118/index.html),
[CSV](proofs/issues/issue-118/review.csv) and
[JSON](proofs/issues/issue-118/review.json) contain 957 observations: all 319
characters in Sans, Mono and Shape. All 48 linked sheets were inspected row by
row. Sans and Mono show all nine weights upright and italic. Shape shows all
three styles with four repeats to exercise contextual variation.

These are assistant observations, not Michael's approval. The 63 px atlas
checks recognizable shape, counter openness, local density, accents and style
progression. It is not an exhaustive browser/rasterizer, text-size, kerning or
mark-stacking review. Spaces are checked by metrics. Marks are shown on `n`.
Unencoded internal glyphs are outside this character-by-character visual claim.

Priority discussion points for Michael:

1. Sans `a` and `y`: local join darkening remains in light uprights. Removing
   Cyrillic does not resolve the corresponding Latin design question.
2. Sans intersecting strokes, especially `Ħ ħ Đ đ Ð ð Ł ł Ø ø` and currency
   symbols: strong ink buildup relative to neighboring hairlines. Also compare
   shoulders in `h m n r`, diagonal joins and their accented derivatives.
3. Heavy Sans `e` and compressed Mono `@ Æ æ Œ œ`: check counter/aperture
   legibility at real text sizes. They remain recognizable at atlas size.
4. Shape: small marks are visibly lighter in Origin/Skeleton; ogonek spacing
   can read detached. The trademark is stylistically less grid-like. Compare
   crossing density across contextual variants at intended display sizes.

No outline correction was made on the strength of these observations. The
scope migration preserves the existing design for this coordinated review.

## Preservation and build evidence

[`preservation.json`](proofs/issues/issue-118/preservation.json) compares all
125 Namche release files with the pre-migration snapshot from commit
`6f583790f713e6d71f90728522537ab22c47e9f9`: zero retained-outline or width
changes, and zero differences in tested Latin Core shaping. Variable checks
sample 100, 250, 400, 550, 700, 850 and 900. This sampled audit does not claim
exhaustive shaping equivalence for every possible string or axis location.

The exact-scope checker covers five design packages, two recovered production
sources and 294 generated release/npm files. Sans open builds reproduce their
pinned TTF/WOFF2 hashes twice. Mono and Shape were rebuilt from the reduced
sources; retained outlines compare equal. Geist matches pinned `geist@1.7.2`.

Validation: 40 repository tests and 23 open-build tests pass; Shape
regeneration matches committed outlines; metadata, source-copy, variable-font
and CSS checks pass. npm dry-run packages 181 files (5,153,105 compressed
bytes). The full destructive `make build` was not used on the uncommitted
migration because it restores Sans binaries from HEAD; its relevant family
builds and checks were run individually.

## Current Fontspector findings

The full candidate profile with Fontspector 1.9.0 reports **265 PASS, 56 WARN,
8 FAIL, 72 SKIP, 15 INFO**, no ERROR/FATAL. Raw output and
[`QA_STATUS.json`](proofs/issues/issue-118/QA_STATUS.json) are preserved.
`submission_ready` remains false. A passing local regression gate is not
Google Fonts acceptance.

Seven failures are real missing sample characters outside the newly requested
Core scope: U+0331 (Amarakaeri, Otomi Mezquital, Secoya), U+02BC (Qʼeqchiʼ,
Yapese, Yucateco), and U+014B (Purepecha). These are intentional scope omissions,
not fixed samples, shaping bugs or curator waivers. The description URL parser
failure remains. `latin-ext` still warns about less than 20% coverage, but it
serves retained Core characters; removing that declaration is not a solution.
The latest run does not report the previous circumflex subset failure; no
circumflex outline or encoding change was made to obtain that result.

All 40 Sans/Mono TTFs pass `soft_dotted`. Language shaping has only explicit
auxiliary omissions outside Core; the finite additional omission list is
`Ĩ ĩ Ŋ ŋ Ō ō Ŗ ŗ Ŝ ŝ Ţ ţ Ŧ ŧ Ũ ũ Ŭ ŭ Ǎ ǎ Ǥ ǥ Ǧ ǧ Ǩ ǩ Ẽ ẽ`.
Actual shaping errors, missing Core characters and unknown warnings remain
blocking. See the committed language-shaping report.

The Google Fonts intake has not been updated or replied to by this work.
Michael's artistic response and curator decisions remain separate next steps.
