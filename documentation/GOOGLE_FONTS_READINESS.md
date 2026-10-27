# Google Fonts readiness: Namche Shadow Sans

## Current scope, 2026-10-27

Issue #118 restricts all Namche sources and outputs to the pinned 319-character
GF Latin Core set. Geist remains unchanged. Historical counts, hashes and
broader-coverage findings below describe earlier releases, not the current
branch. Current binary hashes live in each production source's provenance.json.
The candidate no longer adds U+0331. See [Latin Core review](LATIN_CORE_REVIEW.md)
for the current scope, preservation evidence, visual findings and QA limitations.


## Follow-up, 2026-10-25

[Source reconstruction and mark correction](googlefonts-intake/SOURCE_QA_FOLLOWUP.md)
supersedes the candidate-specific counts and missing-glyph status below. Eighteen
editable quadratic UFO masters now round-trip to the exact approved production
fonts. The candidate alone adds U+0331 with positioning and stacking, while all
existing glyph geometry and metrics remain unchanged. Raw Fontspector 1.9.0 now
reports 264 PASS, 112 WARN, 10 FAIL, 72 SKIP and 17 INFO: nine subset-serving
messages and the existing link-check message. There are no remaining missing
glyph/sample-text failures. The extended-subset warnings persist. Both candidate
ZIPs reproduce, and `submission_ready` remains false. Production sources and
release binaries retain their approved hashes.

The remaining sections record the October 22 assessment and historical evidence.

Checked 2026-10-22 against **v0.6.2**, commit
`039e0efdd5c404df38491ef4d676af5331e02da9`.

**Ready for an initial Google Fonts onboarding discussion, not yet ready for a
production submission PR.** Both VFs now build entirely from open text sources,
byte-identical to 0.6.2. The separate **Namche Shadow** candidate fits the name
limit and includes generated metadata. Source-format acceptance, five complete
package QA failures, subset/other warning decisions and administrative evidence
remain open. This update describes the candidate implementation after 0.6.2;
the historical 0.6.2 audit JSON remains unchanged.

Scope: the two full Sans variable TTFs, upright and italic, weight 100–900 with
400 as default. Do not submit npm-renamed files, Latin subsets, Mono, Shape, or
the Glyphs-exported static distribution as part of this initial family package.
Google Fonts can derive static instances from VFs; the existing upright static
RoundCorner export is therefore not by itself a blocker for this VF submission.
Do not promise that GF-generated statics will be byte-identical to native Glyphs
statics: the existing geometric comparison documents small differences.

## What 0.6.2 resolves

- `scripts/build_sans_open.py` builds upright from editable quadratic UFO,
  point-order metadata, variation TTX and layout TTX. It consumes no release
  font binary, Glyphs executable, or proprietary RoundCorner filter.
- `requirements-open-build.txt` pins the compiler, HarfBuzz serializer and Brotli.
  The mandatory Linux CI job builds twice and checks both approved hashes and
  committed output bytes. The full release job uses the same path.
- [Build PR #105](https://github.com/NamcheAI/namche-fonts/pull/105),
  [release PR #106](https://github.com/NamcheAI/namche-fonts/pull/106), and the
  [successful 0.6.2 release run](https://github.com/NamcheAI/namche-fonts/actions/runs/39689649827)
  establish the repository integration. The open-build check passed again for
  this audit. Public npm installation of 0.6.2 was also verified; its earlier
  transient 404 is no longer a readiness issue.
- Upright SHA-256: TTF
  `3cf41b789b5fcca787cb9db1adabacb1245e11c86a9ea34b99b76310641eb566`;
  WOFF2 `9be24264d6c984c344f73000a295030afcc3f60cf2c9720ced355d8f5297ed42`.
- Public sources, OFL 1.1, retained Geist attribution, author/contributor lists,
  canonical VF filenames, registered `wght` range, TTF output, and English
  descriptive text are present. Package version 0.6.2 is distinct from the
  embedded font version 1.800; the package release does not require an arbitrary
  rewrite of the font version.

## Remaining gates and concrete completion criteria

| Gate | Evidence at 0.6.2 | Work needed before production onboarding |
| --- | --- | --- |
| **Acceptance of recovered sources** | Both VFs compile without binary inputs from quadratic UFO plus indexed TTX. The historical upright cubic masters were not recovered. | Obtain GF agreement on the production representation and maintenance contract, or migrate to accepted maintainable sources without changing the reviewed fonts. Reproducibility alone is not source-format acceptance. |
| **Complete italic source build: implemented** | The default open build and italic-only target use `sources/NamcheShadowSans-Italic/`, including all layout/metadata. Both TTF and WOFF2 match 0.6.2 exactly. CI checks two builds for both styles. | Retain the topology guards, pinned tools and approved hashes. No further binary input is required for either VF. |
| **Instance-name length: implemented for candidate** | Candidate family **Namche Shadow** gives ExtraLight Italic 31, SemiBold Italic 29 and ExtraBold Italic 30 characters. Full style names, STAT and fvar stay consistent. Name-length, font-name and instance checks pass. | Confirm the candidate family name with GF during intake. Production/npm names remain Namche Shadow Sans; no public API rename is included. |
| **Family package: implemented; QA still open** | Two TTFs, OFL, Sans description, METADATA.pb and upstream.yaml are generated and zipped reproducibly. Complete Fontspector 1.9.0 QA runs in CI. | Resolve five FAIL messages plus subset warnings below. Review designer records, date, subsets, proofs and remaining warnings before submission. Local exact finding baselines are not GF waivers. |
| **CLA, rights representation and curator intake** | OFL and credits exist, but no project-specific CLA confirmation or GF source/naming decision is recorded. A search for Namche in `google/fonts` issues found no existing intake issue on 2026-10-22. This does not establish that individual contributors have never signed a CLA. | Confirm applicable corporate/individual CLA coverage and authorized contribution for the derivative, with GF handling the inherited Geist attribution appropriately. Prepare the designer entry/credits for [Michael Marte](https://github.com/fizzybubbele) and [Ruhm etc.](https://ruhmetc.com/). Open the initial new-family issue, explain the Geist derivation and distinctive design, and obtain curator feedback before a submission PR. Inclusion is curated, not guaranteed by passing CI. |

The initial issue can be opened before these production gates are all closed;
its purpose is to resolve source acceptance and naming early. This audit does
not contact Google or submit a CLA. Candidate names change only in the separate
package; shipped font binaries remain unchanged.

## Candidate package and CI

With Python 3.11 and `requirements-open-build.txt` installed:

```sh
make check-sans-open PYTHON=python
make build-googlefonts PYTHON=python
fontspector --profile googlefonts --full-lists \
  --json out/googlefonts/fontspector.json out/googlefonts/ofl/namcheshadow/*
# Fontspector currently exits 1; inspect its full report, then run:
python scripts/check_googlefonts_qa.py out/googlefonts/fontspector.json
```

`out/googlefonts/` contains two byte-reproducible ZIPs:

- `namche-shadow-open-fonts.zip`: both complete production VFs in TTF/WOFF2,
  preserving released names and bytes, plus OFL.
- `namche-shadow-googlefonts.zip`: `ofl/namcheshadow/` with the two renamed TTFs,
  metadata, license, description, upstream build mapping and a root `BUILD.json`.
  The report records the base checkout commit, exact build-input hashes and
  output hashes. Uncommitted local edits are identified by their input hashes;
  only a clean committed CI build is suitable for submission provenance.

`make build-googlefonts` compares two clean ZIP builds. Name rewriting compares
all raw font tables and permits changes only to `name` and `head` checksum
adjustment. Therefore outlines, variations, hinting, metrics and shaping are
byte-identical, not merely visually similar. Existing styles are not abbreviated.

The unconditional Linux job uploads `namche-shadow-googlefonts-candidate` with
both ZIPs, expanded package, full raw QA JSON and `QA_STATUS.json` on PRs, main
pushes and tags. It gates the required `Build and test` aggregate and release
build. The full release build also produces a separate package artifact. The
candidate ZIP itself is a build artifact; consult the sibling QA report before
using it. The proposed `date_added` is a draft, not an acceptance date. Designer
profile names and credit representation must be confirmed during onboarding.

## Complete candidate QA: open findings

The [follow-up investigation](googlefonts-intake/README.md) now identifies each
root cause and quantifies the consequences of removing subsets. The
[Google Fonts intake issue draft](googlefonts-intake/ISSUE.md) is prepared but
not submitted. A mandatory semantic HTML/link check protects correct URLs and
credits while preserving the official checker failure unchanged. Both font
binaries and the exact raw QA baseline remain unchanged.

Fontspector 1.9.0 reports **264 PASS, 112 WARN, 5 FAIL, 72 SKIP, 17 INFO messages**
with the full package. No ERROR/FATAL. Name lengths, fvar/STAT naming, minimum
coverage, axes, family names, metadata/font consistency and license checks pass.
The normalized candidate OFL combines both copyright notices on one line;
all attribution and the complete license body remain intact.

- **One repository-URL FAIL:** 1.9.0 compares whitespace tokens containing
  `github.com` to the repository path. This rejects HTML `href` markup and the
  required Michael Marte profile link. Preserve both credits and repository
  link; resolve the check with GF/tool maintainers rather than removing credits.
- **One subset/tofu FAIL:** Aleut's sample needs U+0302. The glyph exists, but the
  tested GF subset definitions do not serve it through the declared subsets.
- **Three sample-text FAILs:** Amarakaeri, Otomi (Mezquital) and Secoya samples
  require U+0331, absent in these fonts. Resolve the coverage/sample expectation
  with GF, or review a glyph addition separately. A new glyph is not part of a
  byte-identical build migration.
- **Two subset WARNs:** the tested `latin-ext` and `cyrillic-ext` definitions each
  have under 20% coverage. Removing them also drops supported served characters;
  agree the appropriate subset declarations instead of silently reducing support.
- **Other warnings:** existing interpolation/geometry findings still apply.
  Metadata additionally exposes missing designer catalog entries (Michael Marte,
  Ruhm etc. and Basement Studio), unreachable subset characters and sample
  validation skipped because explicit metadata languages have not been agreed.
  These remain review items, not acceptance implied by a green CI run.

`sources/googlefonts/qa-open-findings.json` records exact messages and counts for
these five FAILs and two subset WARNs. CI allows only those known candidate
findings, rejects new FAIL/ERROR/FATAL results and missing required PASS checks,
and emits `submission_ready: false` while any recorded issue remains. All other
warnings remain visible in the raw report and must be reviewed before submission.
This is a regression gate, not a claim that a failing GF profile passes.

## Historical 0.6.2 QA evidence

Used the latest released **Fontspector 1.9.0**, commit `d9d0f7b0` (release
2026-10-09), with `googlefonts`, full result lists and no exception configuration.
The maintained older baseline used 1.7.4; warning counts are not directly
comparable across tool versions.

Two runs distinguish font-only checks from a staged family with explicit OFL and
DESCRIPTION inputs. The staged run is not a complete submission because metadata
has not been generated. [Machine-readable findings](GOOGLE_FONTS_READINESS_0.6.2.json)
record hashes, check counts, skipped checks and individual warning/failure messages.

| Input | PASS checks | WARN checks | FAIL checks | SKIP checks | INFO checks |
| --- | ---: | ---: | ---: | ---: | ---: |
| Upright VF | 108 | 12 | 0 | 35 | 5 |
| Italic VF | 109 | 11 | 1 | 34 | 5 |
| Family | 22 | 1 | 0 | 17 | 2 |
| OFL | 1 | 1 | 0 | 0 | 0 |
| Description | 7 | 0 | 0 | 0 | 1 |

The tool's aggregate counts **messages**, not distinct failing checks:
247 PASS, 108 WARN, 6 FAIL, 86 SKIP, 15 INFO, no ERROR/FATAL. All six FAIL messages
are the same name-length check, duplicated across records for three italic
instances. Glyph coverage (including the profile's minimum coverage test),
canonical font names, fvar instances and license strings pass. Metadata-dependent
checks remain skipped, so “upright has no FAIL” is not “family accepted by GF”.

Reproduce the staged audit from the repository root (with Fontspector 1.9.0):

```sh
stage=$(mktemp -d)
mkdir -p "$stage/ofl/namcheshadowsans" out/readiness-062
cp fonts/NamcheShadowSans/variable/*.ttf OFL.txt \
  documentation/DESCRIPTION.en_us.html "$stage/ofl/namcheshadowsans/"
fontspector --profile googlefonts --full-lists \
  --json out/readiness-062/staged-1.9.0.json \
  "$stage/ofl/namcheshadowsans/"*
```

Exit 1 is expected until the name-length failure is addressed. Passing only the
TTFs excludes the license and description from relevant checks; include them
explicitly. Raw transient reports belong in `out/`.

## Warnings and uncertainties, not automatic rejection

- **Vendor ID:** `NMCH` is still absent from the checked Microsoft list.
  [Issue #24](https://github.com/NamcheAI/namche-fonts/issues/24) records that the
  registration request was already submitted on 2026-08-14. Follow up for
  confirmation; do not list “send first request” as remaining work. Current QA
  reports WARN, not FAIL.
- **Historical license formatting (resolved in candidate):** OFL is present and the license checks pass when it is
  supplied as input. `googlefonts/license/OFL_body_text` warns because the second
  copyright line retains the Geist notice. Agree template-compatible notice
  formatting with GF while preserving all required upstream attribution. Do not
  remove that notice merely to silence a warning.
- **Interpolation:** 1.9.0 reports 11 upright messages over the five previously
  reviewed glyphs and 67 italic messages over 17 glyphs. These include Oslash,
  tbar, uogonek, Cyrillic forms, arrows and figures. Reconcile the detailed current
  report with existing proofs and geometric guards; additional warnings from a
  newer checker are not evidence that 0.6.2 changed the fonts.
- **Other review items:** alternate carons, overlapping segments, contour counts,
  file size, linear-axis `avar`, math widths, unreachable glyphs/subsetting,
  legacy glyph names, auxiliary language omissions and one combining-mark
  sidebearing warning. Existing decisions in [FONTSPECTOR.md](FONTSPECTOR.md) and
  [LANGUAGE_SUPPORT.md](LANGUAGE_SUPPORT.md) are supporting evidence, not a GF
  waiver. Derive supported subsets from real coverage; do not add every auxiliary
  glyph or change visible outlines just to reduce warning counts.
- **Preferred source maintenance:** the public Glyphs design source and recovered
  production sources are not automatically synchronized. The onboarding
  build/maintenance documentation must explain which source is changed for which
  output and how point/delta changes are reviewed.

## Recommended sequence

1. Present the complete candidate build and source-maintenance contract in the
   intake issue; confirm **Namche Shadow**, source-format acceptance and CLA.
2. Resolve subset/sample failures and the repository-link checker issue with GF;
   finalize designer profiles, metadata and warning/proof decisions.
3. Rebuild the exact reviewed commit, inspect the uploaded raw QA and package
   hashes, then submit the package PR referencing the intake decision.

## Requirements consulted

- [New-family onboarding and CLA](https://googlefonts.github.io/gf-guide/onboarding.html)
- [Reproducible libre builds](https://googlefonts.github.io/gf-guide/build.html)
- [Naming requirements and approved exceptions](https://googlefonts.github.io/gf-guide/requirements.html)
- [Current Fontspector QA policy](https://googlefonts.github.io/gf-guide/qa.html)
- [Google Fonts family package](https://googlefonts.github.io/gf-guide/googlefonts.html)
- [Variable fonts and generated statics](https://googlefonts.github.io/gf-guide/variable.html)
- [Public upstream source requirements](https://googlefonts.github.io/gf-guide/upstream.html)
- [Issue before submission PR](https://googlefonts.github.io/gf-guide/making-pr.html)
- [Registered vendor IDs](https://learn.microsoft.com/en-us/typography/vendors/)
