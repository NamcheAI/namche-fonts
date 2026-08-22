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
`sans.cdn.css`, `mono.cdn.css`, and `pixel.cdn.css`.

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
