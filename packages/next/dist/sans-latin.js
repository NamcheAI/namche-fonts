import localFont from "next/font/local";

export const NamcheShadowSans = localFont({
  src: [
    {
      path: "./fonts/namche-shadow-sans/subsets/NamcheShadowSans-Variable-latin.woff2",
      weight: "100 900",
      style: "normal",
    },
    {
      path: "./fonts/namche-shadow-sans/subsets/NamcheShadowSans-Italic[wght]-latin.woff2",
      weight: "100 900",
      style: "italic",
    },
  ],
  variable: "--font-namche-shadow-sans",
  fallback: [
    "ui-sans-serif",
    "system-ui",
    "-apple-system",
    "BlinkMacSystemFont",
    "Inter",
    "Segoe UI",
    "Roboto",
    "sans-serif",
    "Apple Color Emoji",
    "Segoe UI Emoji",
    "Segoe UI Symbol",
    "Noto Color Emoji",
  ],
});
