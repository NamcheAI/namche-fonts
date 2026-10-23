# Reader prototype — proposal for Jodok

Related: #112. Design direction and font design: [Michael Marte](https://github.com/fizzybubbele). Existing Geist/Vercel and Namche attribution and root OFL.txt remain applicable.

For Inkling long-form reading, compare the current Medium 500 at 18/24 px with Reader Regular 400 at 18/28 px. Reader keeps the seven RoundCorner tiers and include/exclude lists, with radii -60/-80/-60/-50/-40/-50/-10 changed to -30/-40/-30/-25/-20/-25/-5. No metrics or spacing changes were requested.

## Review locally

From the repository root: `python3 -m http.server 4326 --bind 127.0.0.1`, then open http://127.0.0.1:4326/documentation/reader-prototype/. The two buttons switch the reading setting. The enlarged pairs always compare Original/Reader Regular 400 to isolate corner treatment. No capability links, private document identifiers or credentials are included.

## Reproduce the source

Run `python3 scripts/prepare_reader_prototype.py`. Open the resulting package in Glyphs and export statics with RoundCorner enabled, overlap removal on and autohinting off. The supplied OTF/WOFF2 Regular prototype was exported natively with licensed Glyphs 3.4.1 (3436); Glyphs 4 was unavailable due to an expired trial. This differs from the required Glyphs 4 production path and is explicitly a review artifact. Do not promote it to a release without that verification.

## Validation and limits

975 exported glyphs. Regular has weight 400, the Reader family name and four cubic curves in H. Representative Latin forms, numerals and German umlauts carry ink and have the same advance widths as the current original Regular; results are in validation.json. Seven filter lists preserved, 63 radius values changed across nine source instances. Complete language/shaping, hinting and cross-platform QA have not been performed. Existing release fonts, npm outputs and default typography remain unchanged.

## Decision requested

Jodok: please compare the reading settings and enlarged pairs. If this direction works, agree the Reader role and radius strength with Michael, then validate a Glyphs 4 export and define packaging before shipping. The repository now contains a variable Sans, so true 450 is possible in the existing family; this proposal deliberately uses static Regular 400 to keep the Reader experiment focused.
