---
"@namche/namche-shadow": minor
---

**Breaking:** replace Namche Shadow Pixel with Namche Shape, a new display
family generated from the Geist Pixel grid in three static styles designed by
Michael Marte for Ruhm etc.:

- **Namche Shape Metaball**: every pixel is a circle, and some neighbouring
  pixels melt together through necks.
- **Namche Shape Origin**: every pixel is a square, half-round, or quarter disc
  from the original Namche system.
- **Namche Shape Skeleton**: only the connections between pixels remain, as a
  rounded trace.

Namche Shape keeps the Pixel metrics, spacing, kerning, OpenType features, ₹,
◌, separators, and ligature carets. Migrate `pixel.css`, `pixel-latin.css`,
`pixel.cdn.css`, and `pixel-latin.cdn.css` to the matching `shape*.css` entry
points, the `font/pixel` and `font/pixel-latin` Next.js exports to
`font/shape` and `font/shape-latin` (`NamcheShapeMetaball`,
`NamcheShapeOrigin`, `NamcheShapeSkeleton`), and the CSS families
`Namche Shadow Pixel *` to `Namche Shape Metaball`, `Namche Shape Origin`, and
`Namche Shape Skeleton`. The Square, Grid, Circle, Triangle, and Line styles
and the Pixel variable font are removed.
