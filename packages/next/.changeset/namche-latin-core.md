---
"@namche/namche-shadow": major
---

Restrict Namche Shadow Sans, Namche Shadow Mono and Namche Shape to the 319
encoded characters in GF Latin Core. Cyrillic, Vietnamese-specific characters
and other out-of-scope characters are no longer included. Required internal
ligature, alternate and component glyphs remain. The `-latin` entry points now
provide the same character coverage as the default Namche entry points.
Bundled upstream Geist is unchanged.
