# Versioning and releases

Namche Shadow Sans uses Semantic Versioning. Before 1.0, outline and metric changes
may be substantial; after 1.0, incompatible family, metric, glyph, or API
changes require a major version.

## Release identity

- The canonical version is the one in `packages/next/package.json`.
- Git tags use `vMAJOR.MINOR.PATCH`.
- The npm package is `@namche/namche-shadow`.
- Release notes must identify the upstream Geist revision and describe any
  outline, metric, name-table, or packaging changes.

## Release checklist

1. Confirm `originals/geist/` is unchanged.
2. Build all families with `make build`.
3. Run `make test` and inspect the generated Fontspector reports.
4. Confirm the static Namche Shadow Sans files contain Michael's intended outlines.
5. Confirm the current variable-font limitation described in `readme.md` is
   still accurate.
6. Bump `packages/next/package.json` and update both changelogs.
7. Open a `codex/...` or `jodok/...` branch and merge it through a green,
   reviewed pull request. Never release directly from an unreviewed `main`.
8. Tag the merged commit and publish the GitHub release archive.
9. Publish `@namche/namche-shadow` from the same tag using npm provenance.

## Attribution requirements

Every release must include `OFL.txt` and carry the canonical two-statement
copyright in name ID 0 and the CFF Notice: the Namche Shadow project-authors
statement first, the original Geist statement second (the Google Fonts
"Project Authors" form; `scripts/rename_font_metadata.py` holds the canonical
strings and `--check` enforces them, including the `OFL.txt` header). The
legal parties are recorded in `AUTHORS.txt`; BTLG Holding GmbH remains
identified as derivative owner through the manufacturer record (name ID 8),
and Michael Marte remains credited as the Namche Shadow Sans designer for
Ruhm GmbH through the designer record (name ID 9) — both are enforced by
`--check`. Development tools and AI tools may be acknowledged as contributors
or commit co-authors, but are not font designers or copyright authors.
