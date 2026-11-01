# Google Fonts intake investigation, 2026-10-22

See [the October 25 follow-up](SOURCE_QA_FOLLOWUP.md) for exact editable master
reconstruction, the candidate U+0331 addition, and the resulting subset-serving
findings. This document and `evidence.json` retain the original investigation.

[Ready-to-edit Add Font issue](ISSUE.md), **not submitted**.
[Machine-readable evidence](evidence.json) covers both VFs using the exact data
crates locked by Fontspector 1.9.0, commit
`d9d0f7b0b2f158b6950df61be97d3ccff3e1f7e8`. No font, source contour, variation,
metric, cmap or shaping table changed in this investigation.

## Disposition of all seven findings

| Official finding | Root cause and evidence | Safe action / remaining decision |
| --- | --- | --- |
| Repository URL FAIL | The checker compares whitespace HTML tokens with a scheme-stripped repository URL; it treats the Michael Marte account link as another repository. Actual HTML destinations and both copyright URLs are correct. | Added a mandatory semantic HTML/link and attribution check in CI. Raw official FAIL remains visible. Ask upstream to parse href values and distinguish credits from project repository links. |
| Aleut U+0302 FAIL | Both fonts contain U+0302, and the complete Aleut sample is covered before subsetting. The union of the five declared non-menu subsets in `google-fonts-subsets 0.202602.1` excludes it. | Keep the glyph and existing declarations. Request a serving/subset correction for combining circumflex in Latin text. Adding unrelated `math` or `cherokee` subsets would misrepresent coverage. |
| Amarakaeri U+0331 FAIL | Base exemplar characters are covered; U+0331 is absent but occurs 39 times in specimen_16. The language record has no marks exemplar. | Ask GF to reconcile support inference with sample requirements. Do not claim the sample is wrong or remove its marks. A real glyph addition requires separate design/shaping review. |
| Otomi, Mezquital U+0331 FAIL | U+0331 occurs 10 times in specimen_16 and is explicitly in the marks exemplar. The checker infers support from base exemplars alone. | Ask GF to include required marks in language support inference; record this language as not completely supported by the current fonts. |
| Secoya U+0331 FAIL | Base exemplars are covered; U+0331 occurs four times in specimen_16 but the language record has no marks exemplar. | Same support-data decision as Amarakaeri; no fabricated or aliased glyph. |
| latin-ext WARN | 170/1140 relevant codepoints, 14.9123%, below the 20% heuristic. Removing this declaration loses 141 currently supported codepoints from the declared subset union. | Request retention/exception despite the percentage. Removing it is not a harmless metadata fix. |
| cyrillic-ext WARN | 33/346 relevant codepoints, 9.5376%. Removing it loses 32 currently supported codepoints from that union. | Request retention/exception, with the exact codepoint list in evidence.json. |

Coverage percentages use the checker's ten common-codepoint exclusions. Loss
counts compare each subset with the union of all the other declared non-menu
subsets. They describe the pinned checker data, not a promise about future GF
production serving. Examples lost without latin-ext include Ā, Ł, Ő, Š and ẞ;
without cyrillic-ext they include Ғ, Қ, Ң, Ө and Ӯ. Both VFs give identical counts.

An independent [2026-10-22 Google Fonts CSS query for Geist](geist-serving-2026-10-22.css) (`wght=400`, Chrome UA)
listed the same five subsets and no unicode-range covering U+0302. This is a
supporting observation from another served family, not an acceptance decision for
Namche or a substitute for inspecting the future Namche serving result.

## Freshness check against upstream main

On 2026-10-22, nam-files main was
[`2a68014b16056e965c18fd47de1f3fde9a5b0095`](https://github.com/googlefonts/nam-files/commit/2a68014b16056e965c18fd47de1f3fde9a5b0095).
Four of the five relevant data files were byte-identical to the pinned crate.
The current latin-ext file adds U+20C1–20C4, U+A7CE, U+A7CF, U+A7D2, U+A7D4,
U+A7DD, U+A7E2 and U+A7F1; it still does not include U+0302 or U+0331.
All four examined language records are byte-identical at current lang main
[`eb4c076b6ebf5f9c461e62cdf941d71845feb97e`](https://github.com/googlefonts/lang/commit/eb4c076b6ebf5f9c461e62cdf941d71845feb97e).
Updating these data alone therefore does not resolve the reported failures.
The HTML whitespace-token logic also remains in Fontspector main at the time
of investigation. The evidence JSON intentionally describes the released tool,
not an unpinned mixture of newer data.

## What was fixed locally

`scripts/check_googlefonts_links.py` parses actual anchors, requires the project,
[Michael Marte](https://github.com/fizzybubbele) and [Ruhm etc.](https://ruhmetc.com/)
links, rejects unrelated GitHub destinations, and verifies the Namche and Geist
copyright URLs in both fonts and OFL. CI uploads `LINKS_STATUS.json` alongside
unchanged official `fontspector.json` and `QA_STATUS.json`. This is a separate,
explicit semantic validation, **not** a rewrite of an upstream FAIL into PASS.
Tests cover valid HTML/profile links, wrong repositories and missing credits.

No existing font or metadata change can honestly eliminate the other findings
without either changing supported rendering or relying on a GF data/policy
change. The exact raw finding baseline is therefore retained, not broadened.
`submission_ready` remains false. U+0331 cannot be repaired by aliasing U+0304,
U+0335 or underscore: those have different position/combining semantics. It has
no pre-existing unencoded macron-below glyph in either VF.

## Reproduce the evidence

Install `requirements-open-build.txt` in Python 3.11 and build the candidate with
`make build-googlefonts PYTHON=python`. Download the two immutable crate archives:

```sh
curl -fL https://crates.io/api/v1/crates/google-fonts-subsets/0.202602.1/download -o /tmp/gf-subsets.crate
curl -fL https://crates.io/api/v1/crates/google-fonts-languages/0.7.11/download -o /tmp/gf-languages.crate
python scripts/audit_googlefonts_intake.py \
  --subsets /tmp/gf-subsets.crate --languages /tmp/gf-languages.crate \
  --family out/googlefonts/ofl/namcheshadow --output /tmp/intake-evidence.json
python scripts/check_googlefonts_links.py out/googlefonts/ofl/namcheshadow \
  --output out/googlefonts/LINKS_STATUS.json
```

The audit verifies both archive SHA-256 values against the release Cargo.lock
before reading any data. It records per-input hashes, both candidate font hashes,
full lost-character lists and normalized sample coverage. No downloaded archive
is extracted to the filesystem by the audit script.

## Primary sources and prior issue search

- [Release dependency lock](https://github.com/fonttools/fontspector/blob/d9d0f7b0b2f158b6950df61be97d3ccff3e1f7e8/Cargo.lock)
- [URL check](https://github.com/fonttools/fontspector/blob/d9d0f7b0b2f158b6950df61be97d3ccff3e1f7e8/profile-googlefonts/src/checks/googlefonts/metadata/consistent_repo_urls.rs)
- [Subset coverage check](https://github.com/fonttools/fontspector/blob/d9d0f7b0b2f158b6950df61be97d3ccff3e1f7e8/profile-googlefonts/src/checks/googlefonts/metadata/subsets_correct.rs)
- [Language support and tofu check](https://github.com/fonttools/fontspector/blob/d9d0f7b0b2f158b6950df61be97d3ccff3e1f7e8/profile-googlefonts/src/checks/googlefonts/tofu.rs)
- [Subset definitions at the crate source commit](https://github.com/googlefonts/nam-files/tree/96ff58320a8a143f6884c3dc5ac2985ac36c4e5f/Lib/gfsubsets/data)
- [Language data at the crate source commit](https://github.com/googlefonts/lang/tree/92bb95ec14763e532b5528fd15ce9a6469417759/Lib/gflanguages/data/languages)
- [Earlier Fontspector #296](https://github.com/fonttools/fontspector/issues/296) and [#302](https://github.com/fonttools/fontspector/pull/302) concern an older URL/OFL parsing bug; they do not establish a fix or waiver for this HTML/profile-link case.
- Search `repo:google/fonts Namche` found no matching issue on 2026-10-22. Repeat before posting the draft.
