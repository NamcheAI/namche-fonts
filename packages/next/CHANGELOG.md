# @namche/namche-shadow

## 0.3.0

### Minor Changes

- 9b78e4c: Add generated, framework-agnostic `@font-face` CSS entry points for all three families and each family individually. New `.cdn.css` entry points pin immutable CDN URLs to the npm package version, while the existing `.css` entry points remain fully self-hosted.
- 4f5f6d2: Add generated Latin WOFF2 subsets with CSS, CDN, and Next.js entry points while preserving the complete existing font distributions.

## 0.2.1

### Patch Changes

- 7935443: Add Pixel dotted-circle coverage and correct soft-dotted shaping for į with top marks.
- 6c110af: Add a Pixel-native Indian rupee sign to every Namche Shadow Pixel style.
- c0b4e4a: Add spec-correct WWS metadata for Sans, Mono, and Pixel without changing their public typographic family or style names.
- e3e5ad0: Use Windows-compatible aliases for overlong Namche Shadow Mono italic variable-font instances.
- d007009: Preserve the source-defined text-cursor positions inside the Pixel fi and fl ligatures.
- e692620: Fix Cyrillic mark attachment and soft-dotted shaping in Namche Shadow Sans and Mono.
- e3fa8b3: Restore the inkless Unicode line and paragraph separators in all Namche Shadow Pixel webfonts.
- 4d8436a: Restore the intended Latin script/language tags and Namche vendor ID in Namche Shadow Pixel binaries.

## 0.2.0

### Minor Changes

- 327248b: Ship the true rounded Namche Shadow Sans upright variable font and use it in
  the default and `font/sans` Next.js entry points. Static italic files remain in
  those entry points, while `font/sans-non-variable` continues to provide only
  static files.

## 0.1.2

### Patch Changes

- 65bfe8b: Ship Namche Shadow Sans from Michael Marte's corrected multi-tier static
  instances and withhold the unfinished Sans variable font.

## 0.1.1

### Patch Changes

- b33e7d9: Restore the intended weight-specific `0` outlines in Namche Shadow Sans.
- e0d5ce6: Apply the Namche Shadow inner-corner treatment to the Sans italic static and
  variable fonts.

## 0.1.0

### Initial Namche release

- Renamed the three families and package API to Namche Shadow Sans.
- Added Michael Marte and ruhm design credit while preserving all original
  Geist copyright and contributor notices.
- Retained the upstream Geist package history below for provenance.

## Upstream Geist package history

## 1.7.2

### Patch Changes

- a4195ae: Update Geist Pixel webfonts with Google Fonts validation fixes.

  Resyncs the published Geist Pixel static webfonts (`Circle`, `Grid`, `Line`, `Square`, `Triangle`) with the source build, picking up the non-visual fixes made for the Google Fonts release (#229): ligature caret anchors (`fi`, `fl`, `f_i`, `A_I`, `U_I`), a `meta` table with ScriptLangTags, line/paragraph separator glyphs and removal of the visible soft hyphen, and 1-unit on-curve point alignment fixes on `e`, `eogonek`, and `hungarumlautcomb`. No visible letterforms change.

## 1.7.1

### Patch Changes

- c8ed578: Fix Geist Mono rendering source-code text with unintended programming ligatures.

  v1.7.0 unintentionally activated programming-ligature substitutions (`-->`, `==`, `!=`, `...`, `--`, etc.) under the `liga` (Standard Ligatures) OpenType feature, which is on by default in every renderer. As a result, text like `--debug-prerender`, `[id...]`, `[...id]`, or `NODE_OPTIONS='--debug-prerender' node` rendered with ligated glyphs and broke monospace alignment in code.

  The source-level fix is in #217; this release ships the rebuilt binaries.

## 1.7.0

### Minor Changes

- d7ef63c: We're excited to announce a new member to our font family: Geist Pixel

  It's a display typeface family featuring five unique pixel-based variants, each with a distinct visual style. It is designed for decorative use in headlines, logos, and other display contexts where a pixelated aesthetic is desired.

  It includes five distinct variants, each exported separately:

  | Export               | CSS Variable                  | Description              |
  | -------------------- | ----------------------------- | ------------------------ |
  | `GeistPixelSquare`   | `--font-geist-pixel-square`   | Square pixel shapes      |
  | `GeistPixelGrid`     | `--font-geist-pixel-grid`     | Grid-based pixel pattern |
  | `GeistPixelCircle`   | `--font-geist-pixel-circle`   | Circular pixel shapes    |
  | `GeistPixelTriangle` | `--font-geist-pixel-triangle` | Triangular pixel shapes  |
  | `GeistPixelLine`     | `--font-geist-pixel-line`     | Line-based pixel pattern |

  ```jsx
  import {
    GeistPixelSquare,
    GeistPixelGrid,
    GeistPixelCircle,
    GeistPixelTriangle,
    GeistPixelLine,
  } from "geist/font/pixel";
  ```
