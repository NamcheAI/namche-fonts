# Namche families (RoundCorner)

Production path: **Glyphs RoundCorner export filters** on Geist Sans upright sources.

Operational findings (CLI failure, naming collisions, verification): [`LEARNINGS.md`](../../LEARNINGS.md). Outside Glyphs / interactive app options: [`ROUNDCORNER_OUTSIDE_GLYPHS.md`](ROUNDCORNER_OUTSIDE_GLYPHS.md).

**Both families ship** in the local specimen (`PREVIEW_FAMILIES`) and under `~/Library/Fonts/Namche-Shadow{,-Simple}/`.

| Family | Status | Recipe | Paste file |
|--------|--------|--------|------------|
| **Namche-Shadow** | Shipping (primary) | Multi-tier stack (2026-08-11d) — see below | `roundcorner_shadow_filters.txt` |
| **Namche-Shadow-Simple** | Shipping | Mild `−25` exclude + strong `−40` include (caps/figures set) | `roundcorner_caps_figs_filters.txt` |

> Naming note (2026-08-11): multi-tier was briefly called **Namche-Darth**; that name is retired. The old two-radius (−40/−25) family is **Namche-Shadow-Simple**.

### Namche-Shadow static filter stack (order matters)

On every **static** instance (Thin → Black) — **2026-08-11d**:

1. `RoundCorner;-60;compatible;exclude:…` — base / rest
2. `RoundCorner;-80;compatible;include:…` — most caps / figures
3. `RoundCorner;-60;compatible;include:A, V, Z, X, Germandbls`
4. `RoundCorner;-50;compatible;include:k, x, v, w`
5. `RoundCorner;-40;compatible;include:M, N, W, two, four, seven, six`
6. `RoundCorner;-50;compatible;include:nine`
7. `RoundCorner;-10;compatible;include:Yusbig-cy, yusbig-cy, mu, baht, peso`

The five glyphs in tier 7 export in every static instance; `Remove Glyphs`
must not be present on statics.

**Upright variable font:** `make build-sans-variable` rebuilds the approved VF
from `sources/NamcheShadowSans-Upright/`, the recovered quadratic UFO and indexed
TTX production sources. It does not consume Glyphs exports. The historical
compatible OTF masters are missing; the checked-in static OTFs are not equivalent.
See [open-build provenance and maintenance](../documentation/OPEN_BUILD.md).
`Yusbig-cy`, `yusbig-cy`, `mu`, `baht`, and `peso` remain absent from the VF.

### Namche-Shadow-Simple

Two-radius pair on statics: `−25` exclude + `−40` include (caps/figures set). Same VF rule (filters off).

## Paths

| Path | Role |
|------|------|
| `../originals/geist/` | **Immutable** pristine Geist Sans upright sources |
| `../sources/NamcheShadowSans.glyphspackage` | Working Namche Shadow Sans upright package |
| `apply_roundcorner_filters.py` | Writes **two-radius** Filter pairs (`--strong` / `--mild`) — for **Shadow-Simple** |
| `inner_round_app.py` | Local static specimen — both families when OTFs exist |
| `../exports/Namche-Shadow/` | Primary Shadow delivery + `Namche-Shadow.glyphspackage` + `_received` |
| `../exports/Namche-Shadow-Simple/` | Simple (−40/−25) delivery + package + `_received` |

## Apply filters

```bash
cd .

# Shadow-Simple (two-radius helper)
python3 scripts/apply_roundcorner_filters.py --strong -40 --mild -25

# Shadow (multi-tier): Glyphs UI or paste scripts/roundcorner_shadow_filters.txt onto statics.
# Do not use the two-radius helper for the multi-tier stack.
```

**Never edit files under `originals/geist/`.**

## Export from Glyphs

1. Open the family package (`exports/Namche-Shadow/Namche-Shadow.glyphspackage` or Simple package / `sources/…`).
2. Confirm the seven static RoundCorner filters and verify the five tier-7
   glyphs are not removed.
3. Export static OTFs and TTFs (Thin → Black). Files may still be named
   `Geist-*` — rename / fix name tables to **Namche-Shadow** or
   **Namche-Shadow-Simple** before delivery.
4. For Namche Shadow Sans, finalize the native OTF/TTF outputs against the
   maintained release tables and generate WOFF2/npm assets:

   ```sh
   make finalize-sans-statics GLYPHS_SANS_EXPORT=/path/to/NamcheShadowSans
   ```
5. Rebuild both unchanged approved VFs from their open production sources:

   ```sh
   make build-sans-variable
   ```

An edited Glyphs export updates statics only. To change the upright VF, migrate
its open quadratic source and indexed deltas together, review the resulting
proofs, then update the approved hashes and binaries. Exporting new statics does
not update these recovered VF sources automatically.

## Local specimen (static files)

```bash
cd .
python3 scripts/inner_round_app.py
# → http://127.0.0.1:8765
```

Serves fonts for families listed in `PREVIEW_FAMILIES` (Shadow + Shadow-Simple).

## Why Cursor / `glyphs-cli` RoundCorner export failed

Automated export from Cursor used [`glyphs-cli`](https://pypi.org/project/glyphs-cli/). That path **does not reliably apply Glyphs RoundCorner instance filters**, even when Filter custom parameters are present.

**Evidence (Regular `H`):**
| Export | `curveTo` count on `H` |
|--------|-------------------------|
| Glyphs GUI (known good) | **4** (inners rounded) |
| `glyphs-cli` (with/without native Filter string) | **0** (sharp) |

Prefer **File → Export… inside Glyphs.app**. Proof an inner-corner glyph (`H`, `E`, `a`) after any automated export.

### Manual drops

Archives live under each family’s `_received/` (formerly also under a `Namche-Darth/` folder name — that tree is now `exports/Namche-Shadow/`).

| Date | Archive | Notes |
|------|---------|--------|
| 2026-08-11d | `exports/Namche-Shadow/_received/2026-08-11d-*` | Current multi-tier (6 filters); Downloads `Namche-Shadow.glyphspackage` + `NamcheShadowSans-*.otf` |
| 2026-08-11c | `exports/Namche-Shadow/_received/2026-08-11c-*` | Prior GUI drop (5-filter era) |
| 2026-08-11b | `exports/Namche-Shadow/_received/2026-08-11b-multi-tier-gui-otf/` | Earlier multi-tier GUI OTFs |
| 2026-08-11 | `exports/Namche-Shadow/_received/2026-08-11-Geist.glyphspackage` | Early multi-tier source package |
| 2026-08-10 | `exports/Namche-Shadow-Simple/_received/2026-08-10-shadow-restored-from-manual/` | **Namche-Shadow-Simple** (−40/−25) restore source |

`Geist-*.otf` in Downloads may be either recipe depending on which package was exported — confirm before renaming into `exports/Namche-*/`.

## Future idea (not implemented)

Interactive radius sliders in the specimen would only swap pre-exported static packs (or rewrite plist + require Glyphs re-export). Browser cannot run Glyphs RoundCorner live.

The italic-only command is `make build-sans-italic-variable`; it also consumes
only recovered UFO/TTX sources. After a reviewed design change, migrate those
production sources explicitly, as described in `documentation/OPEN_BUILD.md`.
`make build-googlefonts` creates the separately named Namche Shadow submission
candidate without changing release/npm bytes.
