import localFont from "next/font/local";

export const NamcheShadowSans = localFont({
  src: [
    {
      path: "./fonts/namche-shadow-sans/subsets/NamcheShadowSans-Variable-latin.woff2",
      weight: "100 900",
      style: "normal",
    },
    {
      path: "./fonts/namche-shadow-sans/subsets/NamcheShadowSans-ThinItalic-latin.woff2",
      weight: "100",
      style: "italic",
    },
    {
      path: "./fonts/namche-shadow-sans/subsets/NamcheShadowSans-UltraLightItalic-latin.woff2",
      weight: "200",
      style: "italic",
    },
    {
      path: "./fonts/namche-shadow-sans/subsets/NamcheShadowSans-LightItalic-latin.woff2",
      weight: "300",
      style: "italic",
    },
    {
      path: "./fonts/namche-shadow-sans/subsets/NamcheShadowSans-Italic-latin.woff2",
      weight: "400",
      style: "italic",
    },
    {
      path: "./fonts/namche-shadow-sans/subsets/NamcheShadowSans-MediumItalic-latin.woff2",
      weight: "500",
      style: "italic",
    },
    {
      path: "./fonts/namche-shadow-sans/subsets/NamcheShadowSans-SemiBoldItalic-latin.woff2",
      weight: "600",
      style: "italic",
    },
    {
      path: "./fonts/namche-shadow-sans/subsets/NamcheShadowSans-BoldItalic-latin.woff2",
      weight: "700",
      style: "italic",
    },
    {
      path: "./fonts/namche-shadow-sans/subsets/NamcheShadowSans-BlackItalic-latin.woff2",
      weight: "800",
      style: "italic",
    },
    {
      path: "./fonts/namche-shadow-sans/subsets/NamcheShadowSans-UltraBlackItalic-latin.woff2",
      weight: "900",
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
