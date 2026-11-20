# Issue #125 – equal-ink corner rule: prototype proofs

Before/after proofs for #125. Left or "current" is the submitted build
(`codex/gf-latin-core`, Cyrillic sample from `main`); right or "proposal" is the
prototype rule (c = 1.2, r_max 70 caps and figures / 53 rest).

- `01-simon-example-current-vs-proposal.png` – the sample from google/fonts#11180, wght 100–300
- `02-added-ink-per-corner.png` – added ink in red, Thin / Regular / Black
- `03-thin-c-variants.png` – Thin with c = 0.6, 0.9, 1.2 against current and plain Geist
- `04-words-all-weights.png` – word images, wght 100–900

`prototype/` holds the scripts that made them (see `LIESMICH.md`). The prototype
rebuilds corners from Geist instances; its outlines are not interpolation-
compatible and are for proofs only. The production change belongs in
`scripts/round_inner_corners.py` as described in the issue.
