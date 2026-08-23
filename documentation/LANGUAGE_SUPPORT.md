# Language support

Namche Shadow Sans and Namche Shadow Mono are designed for Latin text and ship
the inherited Geist Cyrillic character set. Their OpenType metadata therefore
declares `dlng=Latn` and `slng=Latn,Cyrl`. Namche Shadow Pixel currently
declares Latin only.

The supported shaping contract for Sans and Mono includes:

- combining acute, grave, and circumflex marks used with Russian, Ukrainian,
  Belarusian, Bulgarian, and Serbian Cyrillic;
- removal of the soft upper dot before top marks on Cyrillic `і` and `ј`,
  Latin `į`, and Vietnamese `ị`;
- the existing Latin, Latin Extended, Vietnamese, Cyrillic, and Cyrillic
  Extended codepoints present in the release fonts.

Namche does not claim every character that Google Fonts classifies as an
*auxiliary* orthography codepoint. The current deliberate omissions are:

- `Ǿ ǿ`;
- `Ĕ ĕ Ĭ ĭ Ŀ ŀ Ŏ ŏ`;
- `Ĳ ĳ`;
- `Ȟ ȟ Ʒ ʒ Ǯ ǯ`;
- `Ǔ ǔ ſ ʻ`.

Those omissions do not remove the primary orthography of the languages named
by Fontspector, but they mean the project does not promise exhaustive
historical, transliteration, or auxiliary coverage. Adding any of these
characters requires a separate design review rather than copying outlines from
another font solely to silence a distributor profile.

## Opt-in Latin web subset

The npm package and release archive also expose `-latin` CSS and Next.js entry
points for controlled web properties. This delivery subset does not change the
families' full language-support contract: desktop fonts and unsuffixed WOFF2
entry points retain the complete release coverage described above.

[`sources/subsets/latin.txt`](../sources/subsets/latin.txt) is the source of
truth for both physical WOFF2 subsetting and CSS `unicode-range` declarations.
It is based on the `gfsubsets` 2025.11.4 Latin set and includes core Latin,
Latin-1, combining marks needed by that set, typographic punctuation, the euro,
and a small set of common symbols. Text outside that explicit contract uses the
consumer's fallback font. Use the full or a future script-specific composite
entry point for multilingual, user-generated, or terminal-like content.

The upright Namche Shadow Sans variable font additionally parks `ѫ` until its
rounded masters are interpolation-compatible. This exception does not apply to
the Sans statics, which must continue to include the character in every weight.

Run the focused `soft_dotted` and
`googlefonts/glyphsets/shape_languages` Fontspector checks after any source or
OpenType-layout change. The retained language-shaping warning should contain
only the auxiliary omissions above; an attachment failure or a mandatory
soft-dot failure is a regression.
