import localFont from "next/font/local";

export const NamcheShadowMono = localFont({
  src: "./fonts/namche-shadow-mono/subsets/NamcheShadowMono-Variable-latin.woff2",
  variable: "--font-namche-shadow-mono",
  adjustFontFallback: false,
  fallback: [
    "ui-monospace",
    "SFMono-Regular",
    "Roboto Mono",
    "Menlo",
    "Monaco",
    "Liberation Mono",
    "DejaVu Sans Mono",
    "Courier New",
    "monospace",
  ],
  weight: "100 900",
});
