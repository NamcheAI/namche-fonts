# Google Fonts readiness: Namche Shadow Sans

Checked 2026-10-22 against **v0.6.2**, commit
`039e0efdd5c404df38491ef4d676af5331e02da9`.

**Ready for an initial Google Fonts onboarding discussion, not yet ready for a
production submission PR.** The upright reproducibility blocker is resolved.
Acceptance of its recovered source representation, the complete italic source
build, naming, submission metadata, and administrative evidence remain open.

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
| **Acceptance of recovered upright sources** | The open build is reproducible, but its original cubic masters were not recovered. Quadratic UFO plus indexed TTX is a production representation with point-topology constraints. No GF acceptance is recorded. | Present the sources, build command and maintenance contract to GF. Obtain agreement on this representation, or migrate to an accepted maintainable source/designspace while preserving reviewed rendering and interpolation. Do not describe this as a proven rejection or assume that using UFO alone establishes acceptance. |
| **Complete italic source build** | `config-NamcheShadowSans-Italic.yaml` builds static outlines openly. `build-sans-italic-variable` still consumes compiled OTFs plus release statics, and the outline-refresh workflow preserves tables from committed binaries. The release job restores the italic VF. #105's mandatory byte check covers upright only. | Provide a documented clean command that builds both submission VFs entirely from text sources with pinned tools. Include italic layout/metadata/hinting inputs and variation compilation; remove committed binaries as required build inputs. Run twice in Linux CI and validate geometry, shaping and the intended outputs. Open italic outline feasibility is not yet this integrated full-build proof. |
| **Italic instance-name length** | Current QA fails `name/family_and_style_max_length`: `ExtraLight Italic` gives 36 characters, `SemiBold Italic` 34, `ExtraBold Italic` 35 including family and separator. `googlefonts/fvar_instances` passes. | Obtain an explicit GF exception or agree a compliant naming plan. Abbreviating only the instance names would reintroduce the fvar/STAT mismatch. A shorter GF family name changes public naming and needs an explicit decision. The repository's local exemption is not GF approval. |
| **Google Fonts family package and complete QA** | No `METADATA.pb`, `upstream.yaml`, or complete `ofl/namcheshadowsans` submission package is committed. Metadata checks currently SKIP. Existing description also discusses companion families. | Assemble the two TTFs, OFL, Sans-focused description/article and designer attribution; generate and review METADATA.pb and upstream.yaml with source commit/build mapping. Confirm subsets, axes, designer record and repository links. Run the current googlefonts profile on all package inputs, not only TTFs. Fix FAILs or record GF-approved exceptions; classify every remaining warning. |
| **CLA, rights representation and curator intake** | OFL and credits exist, but no project-specific CLA confirmation or GF source/naming decision is recorded. A search for Namche in `google/fonts` issues found no existing intake issue on 2026-10-22. This does not establish that individual contributors have never signed a CLA. | Confirm applicable corporate/individual CLA coverage and authorized contribution for the derivative, with GF handling the inherited Geist attribution appropriately. Prepare the designer entry/credits for Michael Marte and Ruhm etc. Open the initial new-family issue, explain the Geist derivation and distinctive design, and obtain curator feedback before a submission PR. Inclusion is curated, not guaranteed by passing CI. |

The initial issue can be opened before these production gates are all closed;
its purpose is to resolve source acceptance and naming early. This audit does
not contact Google, submit a CLA, rename the family, or change font binaries.

## Fresh QA evidence

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
- **License formatting:** OFL is present and the license checks pass when it is
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
  upright production source are not automatically synchronized. The onboarding
  build/maintenance documentation must explain which source is changed for which
  output and how point/delta changes are reviewed.

## Recommended sequence

1. Prepare an intake issue with 0.6.2, the exact open-build proof, source-format
   question, naming exception request/alternative, and designer attribution.
2. Resolve CLA coverage and the source/naming decisions with GF before spending
   effort on a source conversion or public family rename.
3. Complete the italic source-only build and mandatory two-VF CI gate.
4. Assemble the family package, resolve license formatting, generate metadata,
   review warnings and run the complete current QA/proof workflow.
5. Submit the reviewed package PR to `google/fonts`, referencing the intake issue.

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
