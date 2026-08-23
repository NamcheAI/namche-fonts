import { NextFontWithVariable } from "next/dist/compiled/@next/font";

declare module "@namche/namche-shadow/font" {
  /**
   * @deprecated - Import from `@namche/namche-shadow/font/sans` instead.
   *
   * Namche Shadow Sans font family, with `className` and `variable` properties,
   * meant to be attached to DOM elements via `className`
   *
   * Uses the rounded upright variable font and Michael Marte's multi-tier
   * static italic exports.
   *
   * Included weights: 100 through 900
   * Included styles: normal and italic
   *
   * * {@link https://www.npmjs.com/package/@namche/namche-shadow?activeTab=readme#app-router View App Router Example}
   *
   * * {@link https://www.npmjs.com/package/@namche/namche-shadow?activeTab=readme#with-tailwind-css View Tailwind Example}
   *
   * * {@link https://www.npmjs.com/package/@namche/namche-shadow?activeTab=readme#pages-router View Pages Router Example}
   *
   * * {@link https://github.com/NamcheAI/namche-shadow-font/releases Download Font Files}
   */
  export const NamcheShadowSans: NextFontWithVariable;

  /**
   * @deprecated - Import from `@namche/namche-shadow/font/sans-non-variable` instead.
   *
   * Namche Shadow Sans font, with `className` and `variable` properties,
   * meant to be attached to DOM elements via `className`
   *
   * Uses static upright and italic files for browsers that do not support
   * variable fonts.
   *
   * Included weights: 100 through 900
   * Included styles: normal and italic
   *
   * * {@link https://www.npmjs.com/package/@namche/namche-shadow?activeTab=readme#app-router View App Router Example}
   *
   * * {@link https://www.npmjs.com/package/@namche/namche-shadow?activeTab=readme#with-tailwind-css View Tailwind Example}
   *
   * * {@link https://www.npmjs.com/package/@namche/namche-shadow?activeTab=readme#pages-router View Pages Router Example}
   *
   * * {@link https://github.com/NamcheAI/namche-shadow-font/releases Download Font Files}
   * @deprecated Use `NamcheShadowSans` instead
   */
  export const NamcheShadowSansNonVariable: NextFontWithVariable;

  /**
   * @deprecated - Import from `@namche/namche-shadow/font/mono` instead.
   *
   * Namche Shadow Mono variable font, with `className` and `variable` properties,
   * meant to be attached to DOM elements via `className`
   *
   * `NamcheShadowMono`—approximately 30kb—is preferred in almost all cases. Use `NamcheShadowMonoNonVariable`—approximately
   * 300kb—if you need to support browsers that {@link https://caniuse.com/variable-fonts cannot display variable fonts}
   *
   * Included weights: 100 through 900.
   *
   * * {@link https://www.npmjs.com/package/@namche/namche-shadow?activeTab=readme#app-router View App Router Example}
   *
   * * {@link https://www.npmjs.com/package/@namche/namche-shadow?activeTab=readme#with-tailwind-css View Tailwind Example}
   *
   * * {@link https://www.npmjs.com/package/@namche/namche-shadow?activeTab=readme#pages-router View Pages Router Example}
   *
   * * {@link https://github.com/NamcheAI/namche-shadow-font/releases Download Font Files}
   */
  export const NamcheShadowMono: NextFontWithVariable;

  /**
   * @deprecated - Import from `@namche/namche-shadow/font/mono-non-variable` instead.
   *
   * Namche Shadow Mono font, with `className` and `variable` properties,
   * meant to be attached to DOM elements via `className`
   *
   * `NamcheShadowMono`—approximately 30kb—is preferred in almost all cases. Use `NamcheShadowMonoNonVariable`—approximately
   * 300kb—if you need to support browsers that {@link https://caniuse.com/variable-fonts cannot display variable fonts}
   *
   * Included weights: 100 through 900.
   *
   * * {@link https://www.npmjs.com/package/@namche/namche-shadow?activeTab=readme#app-router View App Router Example}
   *
   * * {@link https://www.npmjs.com/package/@namche/namche-shadow?activeTab=readme#with-tailwind-css View Tailwind Example}
   *
   * * {@link https://www.npmjs.com/package/@namche/namche-shadow?activeTab=readme#pages-router View Pages Router Example}
   *
   * * {@link https://github.com/NamcheAI/namche-shadow-font/releases Download Font Files}
   */
  export const NamcheShadowMonoNonVariable: NextFontWithVariable;
}

declare module "@namche/namche-shadow/font/mono" {
  /**
   * Namche Shadow Mono variable font, with `className` and `variable` properties,
   * meant to be attached to DOM elements via `className`
   *
   * `NamcheShadowMono`—approximately 30kb—is preferred in almost all cases. Use `NamcheShadowMonoNonVariable`—approximately
   * 300kb—if you need to support browsers that {@link https://caniuse.com/variable-fonts cannot display variable fonts}
   *
   * Included weights: 100 through 900.
   *
   * * {@link https://www.npmjs.com/package/@namche/namche-shadow?activeTab=readme#app-router View App Router Example}
   *
   * * {@link https://www.npmjs.com/package/@namche/namche-shadow?activeTab=readme#with-tailwind-css View Tailwind Example}
   *
   * * {@link https://www.npmjs.com/package/@namche/namche-shadow?activeTab=readme#pages-router View Pages Router Example}
   *
   * * {@link https://github.com/NamcheAI/namche-shadow-font/releases Download Font Files}
   */
  export const NamcheShadowMono: NextFontWithVariable;
}

declare module "@namche/namche-shadow/font/mono-non-variable" {
  /**
   * Namche Shadow Mono font, with `className` and `variable` properties,
   * meant to be attached to DOM elements via `className`
   *
   * `NamcheShadowMono`—approximately 30kb—is preferred in almost all cases. Use `NamcheShadowMonoNonVariable`—approximately
   * 300kb—if you need to support browsers that {@link https://caniuse.com/variable-fonts cannot display variable fonts}
   *
   * Included weights: 100 through 900.
   *
   * * {@link https://www.npmjs.com/package/@namche/namche-shadow?activeTab=readme#app-router View App Router Example}
   *
   * * {@link https://www.npmjs.com/package/@namche/namche-shadow?activeTab=readme#with-tailwind-css View Tailwind Example}
   *
   * * {@link https://www.npmjs.com/package/@namche/namche-shadow?activeTab=readme#pages-router View Pages Router Example}
   *
   * * {@link https://github.com/NamcheAI/namche-shadow-font/releases Download Font Files}
   */
  export const NamcheShadowMonoNonVariable: NextFontWithVariable;
}

declare module "@namche/namche-shadow/font/sans" {
  /**
   * Namche Shadow Sans font, with `className` and `variable` properties,
   * meant to be attached to DOM elements via `className`
   *
   * Uses the rounded upright variable font and Michael Marte's multi-tier
   * static italic exports.
   *
   * Included weights: 100 through 900
   * Included styles: normal and italic
   *
   * * {@link https://www.npmjs.com/package/@namche/namche-shadow?activeTab=readme#app-router View App Router Example}
   *
   * * {@link https://www.npmjs.com/package/@namche/namche-shadow?activeTab=readme#with-tailwind-css View Tailwind Example}
   *
   * * {@link https://www.npmjs.com/package/@namche/namche-shadow?activeTab=readme#pages-router View Pages Router Example}
   *
   * * {@link https://github.com/NamcheAI/namche-shadow-font/releases Download Font Files}
   */
  export const NamcheShadowSans: NextFontWithVariable;
}

declare module "@namche/namche-shadow/font/sans-latin" {
  /**
   * Latin-only Namche Shadow Sans for controlled web properties.
   *
   * Uses the upright variable font and static italic weights. Text outside
   * the documented Latin subset falls through to the configured fallback.
   */
  export const NamcheShadowSans: NextFontWithVariable;
}

declare module "@namche/namche-shadow/font/mono-latin" {
  /** Latin-only Namche Shadow Mono variable font for controlled web properties. */
  export const NamcheShadowMono: NextFontWithVariable;
}

declare module "@namche/namche-shadow/font/sans-non-variable" {
  /**
   * Namche Shadow Sans font, with `className` and `variable` properties,
   * meant to be attached to DOM elements via `className`
   *
   * Uses static upright and italic files for browsers that do not support
   * variable fonts.
   *
   * Included weights: 100 through 900.
   * Included styles: normal and italic.
   *
   * * {@link https://www.npmjs.com/package/@namche/namche-shadow?activeTab=readme#app-router View App Router Example}
   *
   * * {@link https://www.npmjs.com/package/@namche/namche-shadow?activeTab=readme#with-tailwind-css View Tailwind Example}
   *
   * * {@link https://www.npmjs.com/package/@namche/namche-shadow?activeTab=readme#pages-router View Pages Router Example}
   *
   * * {@link https://github.com/NamcheAI/namche-shadow-font/releases Download Font Files}
   */
  export const NamcheShadowSansNonVariable: NextFontWithVariable;
}

declare module "@namche/namche-shadow/font/pixel" {
  /**
   * Namche Shadow Pixel Square font, with `className` and `variable` properties,
   * meant to be attached to DOM elements via `className`
   *
   * A pixelated display font with square-shaped pixels.
   *
   * * {@link https://github.com/NamcheAI/namche-shadow-font/releases Download Font Files}
   */
  export const NamcheShadowPixelSquare: NextFontWithVariable;

  /**
   * Namche Shadow Pixel Grid font, with `className` and `variable` properties,
   * meant to be attached to DOM elements via `className`
   *
   * A pixelated display font with grid-shaped pixels.
   *
   * * {@link https://github.com/NamcheAI/namche-shadow-font/releases Download Font Files}
   */
  export const NamcheShadowPixelGrid: NextFontWithVariable;

  /**
   * Namche Shadow Pixel Circle font, with `className` and `variable` properties,
   * meant to be attached to DOM elements via `className`
   *
   * A pixelated display font with circle-shaped pixels.
   *
   * * {@link https://github.com/NamcheAI/namche-shadow-font/releases Download Font Files}
   */
  export const NamcheShadowPixelCircle: NextFontWithVariable;

  /**
   * Namche Shadow Pixel Triangle font, with `className` and `variable` properties,
   * meant to be attached to DOM elements via `className`
   *
   * A pixelated display font with triangle-shaped pixels.
   *
   * * {@link https://github.com/NamcheAI/namche-shadow-font/releases Download Font Files}
   */
  export const NamcheShadowPixelTriangle: NextFontWithVariable;

  /**
   * Namche Shadow Pixel Line font, with `className` and `variable` properties,
   * meant to be attached to DOM elements via `className`
   *
   * A pixelated display font with line-shaped pixels.
   *
   * * {@link https://github.com/NamcheAI/namche-shadow-font/releases Download Font Files}
   */
  export const NamcheShadowPixelLine: NextFontWithVariable;
}

declare module "@namche/namche-shadow/font/pixel-latin" {
  export const NamcheShadowPixelSquare: NextFontWithVariable;
  export const NamcheShadowPixelGrid: NextFontWithVariable;
  export const NamcheShadowPixelCircle: NextFontWithVariable;
  export const NamcheShadowPixelTriangle: NextFontWithVariable;
  export const NamcheShadowPixelLine: NextFontWithVariable;
}
