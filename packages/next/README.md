# Namche Shadow fonts for npm

The package exposes Namche Shadow Sans, Namche Shadow Mono, and the five Namche
Shadow Pixel variants through `next/font/local`.

## Installation

```sh
pnpm add @namche/namche-shadow
```

## Usage

Framework-agnostic apps can use CDN-pinned CSS without serving font binaries
from the app’s own origin:

```css
@import "@namche/namche-shadow/fonts.cdn.css";
```

The URLs are generated from this package’s version, so updating the package
selects the matching immutable CDN release. Family-only entry points are
`sans.cdn.css`, `mono.cdn.css`, `pixel.cdn.css`, and `geist.cdn.css`.

Controlled Namche properties that only need the maintained Latin web set can
use `fonts-latin.cdn.css`, or one of `sans-latin.cdn.css`,
`mono-latin.cdn.css`, `pixel-latin.cdn.css`, and `geist-latin.cdn.css`. These
point to physically subsetted WOFF2 files and include matching
`unicode-range` descriptors.

The `geist` entry points expose upstream [Vercel Geist](https://vercel.com/font)
Sans variable faces, bundled byte for byte so Namche applications can load
their `Geist` body font from the same package or CDN release. Next.js apps
that want automatic font optimisation for Geist should keep using Vercel's
own [`geist`](https://www.npmjs.com/package/geist) package.

Projects that do not need the npm dependency can import the versioned CDN
stylesheet directly:

```css
@import url("https://cdn.namche.ai/fonts/namche-shadow/v0.2.1/fonts.css");
```

Its internal font URLs are relative to that version root, making the
stylesheet bytes reusable across release tags while each versioned import
remains immutable. The `current/` alias is only a preview pointer and must
never be pinned in production.

For fully self-hosted deployments, import all three families from
package-relative CSS:

```css
@import "@namche/namche-shadow/fonts.css";
```

Or import only the families they use:

```css
@import "@namche/namche-shadow/sans.css";
@import "@namche/namche-shadow/mono.css";
@import "@namche/namche-shadow/pixel.css";
```

The self-hosted Latin equivalents are `fonts-latin.css`, `sans-latin.css`,
`mono-latin.css`, and `pixel-latin.css`. Use the unsuffixed entry points for
user-generated or multilingual text and for Mono content that needs box
drawing or technical symbols.

This path includes the WOFF2 files in the application build and works offline
or in air-gapped environments.

Next.js apps should keep using the `next/font/local` entry points for automatic
font optimisation:

```tsx
import { NamcheShadowSans } from "@namche/namche-shadow/font/sans";
import { NamcheShadowMono } from "@namche/namche-shadow/font/mono";

export default function Layout({ children }) {
  return (
    <html className={`${NamcheShadowSans.variable} ${NamcheShadowMono.variable}`}>
      <body>{children}</body>
    </html>
  );
}
```

Latin-only Next.js entry points preserve the same named exports:

```tsx
import { NamcheShadowSans } from "@namche/namche-shadow/font/sans-latin";
import { NamcheShadowMono } from "@namche/namche-shadow/font/mono-latin";
```

`font/pixel-latin` similarly exports all five Pixel variants. The subset files
are generated from the full approved WOFF2 files during CI and release
assembly; full desktop and webfont files remain available unchanged.

The default export and `font/sans` use the rounded upright Namche Shadow Sans
variable font with static italic weights. `font/sans-non-variable` keeps the
static upright and italic files. The upright Thin through Black statics remain
Michael's approved multi-tier RoundCorner references. The Mono exports
currently provide upright styles.

Pixel variants are exported from `@namche/namche-shadow/font/pixel`:

- `NamcheShadowPixelSquare`
- `NamcheShadowPixelGrid`
- `NamcheShadowPixelCircle`
- `NamcheShadowPixelTriangle`
- `NamcheShadowPixelLine`

The Namche Shadow Sans design direction and implementation is done by
[Michael Marte](https://github.com/fizzybubbele) for
[Ruhm etc.](https://ruhmetc.com/).

This package is adapted from Vercel's
[`geist`](https://www.npmjs.com/package/geist) package. The fonts remain
licensed under the [SIL Open Font License 1.1](../../OFL.txt); see the root
[`AUTHORS.txt`](../../AUTHORS.txt) and [`CONTRIBUTORS.txt`](../../CONTRIBUTORS.txt)
for full credit.
