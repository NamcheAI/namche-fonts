---
"@namche/namche-shadow": minor
---

Namche Shape now varies as you type: every glyph except combining marks ships
in four seeded variants, and the default-on `calt` feature rotates them so
repeated letters never look the same twice. Set
`font-feature-settings: "calt" 0` to pin the default variant. The larger
glyph set grows the WOFF2 files to about 200 KB (Metaball), 112 KB (Origin),
and 95 KB (Skeleton).

The same release refines the three styles: Origin turns its half-rounds and
quarter discs toward the open edges and corners of each stroke, Metaball melts
along strokes more often than across them, and Skeleton keeps every rail of a
stroke whole with random rungs, so every glyph reads more deliberately.
