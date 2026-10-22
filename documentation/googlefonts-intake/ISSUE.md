# Add Namche Shadow: source-format and coverage intake

<!-- Draft only. Destination: google/fonts, Add Font template.
Do not post without the maintainer checking the personal commitments below.
The family is an onboarding candidate, not a claim of passing all GF checks. -->

**Font Project Git Repo URL:**

https://github.com/NamcheAI/namche-fonts

**Super short description of the Font Family:**

Namche Shadow is a display sans-serif defined by rounded inner corners and
crisp outer forms. [Michael Marte](https://github.com/fizzybubbele) designed its
distinctive treatment for [Ruhm etc.](https://ruhmetc.com/). The candidate contains
two variable TTFs, upright and italic, both with `wght` 100–900 and default 400.
The proposed menu family is **Namche Shadow**. Its longest full instance name is
31 characters. The existing npm distribution is named **Namche Shadow Sans**;
the candidate changes names only, preserving all outlines, variations, shaping
and metrics.

We would like curator feedback before opening a font submission PR, especially
on the recovered production-source format and the coverage decisions below.

**Requirements:**

The evidence below is available now. Boxes representing maintainer commitments
or external acceptance remain unchecked deliberately.

- [x] Font sources and binaries are public in the repository under OFL 1.1, with all original copyright notices retained.
- [ ] Confirm that no larger proprietary/retail variant exists outside this repository.
- [x] Source files are available: both Glyphs design packages and quadratic UFO/indexed TTX production sources, with pinned open build tools.
- [ ] Maintainer to confirm authority to contribute and applicable CLA coverage for BTLG Holding GmbH and the inherited work.
- [ ] Confirm upstream Reserved Font Name obligations and name clearance before submission.
- [ ] Complete the family-name uniqueness check at https://namecheck.fontdata.com/ and obtain agreement on **Namche Shadow**.
- [x] The candidate passes the Fontspector 1.9.0 Google Fonts minimum glyph-coverage check.
- [ ] Obtain agreement on the source/build structure and resolve remaining QA findings.
- [ ] Maintainer to confirm the full Google Fonts contributing requirements and ongoing maintenance commitment.

Namche Shadow builds on Geist Sans. Original credits to Vercel, Basement Studio,
Andrés Briganti, Mateo Zaragoza and contributors are retained in the sources,
font metadata and license notices.

AI-assisted coding tools supported build recovery, automation and QA
investigation. The Namche design treatment is credited to Michael Marte.
No CLA coverage or legal clearance is asserted by this draft.

**Image:**

![Upright named instances](https://raw.githubusercontent.com/NamcheAI/namche-fonts/main/documentation/proofs/sans-variable-named-instances.png)

[Italic proof](https://github.com/NamcheAI/namche-fonts/blob/main/documentation/proofs/sans-italic-variable-named-instances.png).
These approved production proofs use the original Sans family label; the
candidate's outlines are identical.

## Build and evidence

The complete source-only VF build landed in [PR #107](https://github.com/NamcheAI/namche-fonts/pull/107),
commit `4b2e33263ce4377f2fd2b993f29d16e3b25e2245`. Both TTF/WOFF2 pairs reproduce
0.6.2 byte-for-byte. Italic uses pure FontTools layout packing and upright uses
the pinned HarfBuzz repacker. No compiled fonts or proprietary filters are build
inputs. Static upright exports remain a separate Glyphs workflow; they are not
part of this two-VF submission.

```sh
python3.11 -m venv venv
venv/bin/pip install -r requirements-open-build.txt
make check-sans-open PYTHON=venv/bin/python
make build-googlefonts PYTHON=venv/bin/python
```

The candidate archive contains two TTFs, OFL, a family description, METADATA.pb,
upstream.yaml and a source/output-hash manifest. CI uploads both ZIPs and the raw
QA report as `namche-shadow-googlefonts-candidate`.

- [Readiness and build instructions](https://github.com/NamcheAI/namche-fonts/blob/main/documentation/GOOGLE_FONTS_READINESS.md)
- [Production-source maintenance contract](https://github.com/NamcheAI/namche-fonts/blob/main/documentation/OPEN_BUILD.md)
- [Detailed investigation and reproduction](https://github.com/NamcheAI/namche-fonts/blob/main/documentation/googlefonts-intake/README.md)
- [Exact coverage, missing characters and input/output hashes](https://github.com/NamcheAI/namche-fonts/blob/main/documentation/googlefonts-intake/evidence.json)

Official Fontspector 1.9.0 remains at **five FAIL messages and two relevant subset
WARN messages**. The complete report also retains other existing warnings; we
are not presenting a green local regression gate as GF approval. The independent
HTML/link check passes, while the raw upstream link failure remains unchanged.

## Decisions requested

### 1. Recovered source representation and candidate name

Are editable quadratic UFO default masters plus readable indexed gvar/layout TTX,
with stable point identifiers and a documented maintenance contract, acceptable
for this initial onboarding? The original upright compatible cubic export masters
were not recovered. The separate Glyphs design sources do not automatically
regenerate this production snapshot. If a conventional interpolating designspace
is required, please confirm that before we migrate the exact reviewed geometry.

Is **Namche Shadow** acceptable as the definitive GF menu family, distinct from
the existing Namche Shadow Sans package naming?

### 2. Retain supported extended subsets despite the percentage heuristic

For both VFs, using the `google-fonts-subsets 0.202602.1` data pinned by Fontspector:

| Subset | Coverage after common-character exclusions | Supported characters lost from the declared union if removed |
| --- | --- | --- |
| latin-ext | 170/1140 = 14.9123% | 141, including Ā, Ł, Ő, Š and ẞ |
| cyrillic-ext | 33/346 = 9.5376% | 32, including Ғ, Қ, Ң, Ө and Ӯ |

Both are below the checker's 20% heuristic. May we retain these declarations with
an explicit exception, or is there a preferred serving configuration preserving
these characters? Full loss lists are in the linked evidence. We have not removed
subsets or added unrelated scripts to make the warning disappear.

### 3. Combining circumflex in Aleut after subsetting

Both candidate fonts contain U+0302 and cover the complete Aleut sample before
subsetting. U+0302 is absent from the union of the declared `latin`, `latin-ext`,
`cyrillic`, `cyrillic-ext` and `vietnamese` subset data. This causes the one
`missing-subsetted` failure. Can the Latin serving definition preserve U+0302,
or can you specify the correct serving arrangement for this family?

### 4. Three inferred languages require an absent combining macron below

U+0331 is absent in both VFs and is not present as an unencoded reusable glyph.
The checker infers language support from base exemplars alone:

| Language | U+0331 occurrences in specimen_16 | Language-data observation |
| --- | ---: | --- |
| Amarakaeri (`amr_Latn`) | 39 | No marks exemplar; base exemplars omit U+0331. |
| Otomi, Mezquital (`ote_Latn`) | 10 | Marks exemplar explicitly includes U+0331, but support inference ignores it. |
| Secoya (`sey_Latn`) | 4 | No marks exemplar; base exemplars omit U+0331. |

We do not claim complete support for those languages or that the samples are
linguistically incorrect. Can language-support inference/data be corrected so
these fonts are not advertised for unsupported samples, or is an independently
reviewed U+0331 addition required before onboarding? We have not aliased another
mark or altered these samples to hide the failures.

### 5. HTML/profile-link false positive in consistent_repo_urls

The checker uses `description_contents.split_whitespace()` and compares any token
containing `github.com/` against the repository URL without its scheme. Our valid
anchors produce these reported values:

```html
<a href="https://github.com/fizzybubbele">Michael Marte</a>
<a href="https://github.com/NamcheAI/namche-fonts">the project repository</a>
```

The actual project, designer and inherited copyright destinations pass an
independent HTML-aware check. Could the Fontspector check parse actual hrefs and
distinguish designer attribution from project repository links, or can this
specific false positive receive a documented onboarding exception? Earlier
[Fontspector #302](https://github.com/fonttools/fontspector/pull/302) fixed an OFL
parsing case, not this remaining HTML/profile-link case.

### 6. Attribution, CLA and final metadata

Please advise on the designer catalog entries for Michael Marte/Ruhm etc. and
retained upstream credits, the applicable CLA process for the project,
and final metadata language declarations. The generated `date_added` is a draft.
Other interpolation/geometry warnings and proofs remain listed in the readiness
document for review; this issue does not request blanket approval of them.
