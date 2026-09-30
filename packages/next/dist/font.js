import localFont from "next/font/local";

export const NamcheShadowSans = localFont({
  src: [
    {
      path: "./fonts/namche-shadow-sans/NamcheShadowSans-Variable.woff2",
      weight: "100 900",
      style: "normal",
    },
    {
      path: "./fonts/namche-shadow-sans/NamcheShadowSans-Thin.woff2",
      weight: "100",
      style: "normal",
    },
    {
      path: "./fonts/namche-shadow-sans/NamcheShadowSans-UltraLight.woff2",
      weight: "200",
      style: "normal",
    },
    {
      path: "./fonts/namche-shadow-sans/NamcheShadowSans-Light.woff2",
      weight: "300",
      style: "normal",
    },
    {
      path: "./fonts/namche-shadow-sans/NamcheShadowSans-Regular.woff2",
      weight: "400",
      style: "normal",
    },
    {
      path: "./fonts/namche-shadow-sans/NamcheShadowSans-Medium.woff2",
      weight: "500",
      style: "normal",
    },
    {
      path: "./fonts/namche-shadow-sans/NamcheShadowSans-SemiBold.woff2",
      weight: "600",
      style: "normal",
    },
    {
      path: "./fonts/namche-shadow-sans/NamcheShadowSans-Bold.woff2",
      weight: "700",
      style: "normal",
    },
    {
      path: "./fonts/namche-shadow-sans/NamcheShadowSans-Black.woff2",
      weight: "800",
      style: "normal",
    },
    {
      path: "./fonts/namche-shadow-sans/NamcheShadowSans-UltraBlack.woff2",
      weight: "900",
      style: "normal",
    },
    {
      path: "./fonts/namche-shadow-sans/NamcheShadowSans-Italic[wght].woff2",
      weight: "100 900",
      style: "italic",
    },
    {
      path: "./fonts/namche-shadow-sans/NamcheShadowSans-ThinItalic.woff2",
      weight: "100",
      style: "italic",
    },
    {
      path: "./fonts/namche-shadow-sans/NamcheShadowSans-UltraLightItalic.woff2",
      weight: "200",
      style: "italic",
    },
    {
      path: "./fonts/namche-shadow-sans/NamcheShadowSans-LightItalic.woff2",
      weight: "300",
      style: "italic",
    },
    {
      path: "./fonts/namche-shadow-sans/NamcheShadowSans-Italic.woff2",
      weight: "400",
      style: "italic",
    },
    {
      path: "./fonts/namche-shadow-sans/NamcheShadowSans-MediumItalic.woff2",
      weight: "500",
      style: "italic",
    },
    {
      path: "./fonts/namche-shadow-sans/NamcheShadowSans-SemiBoldItalic.woff2",
      weight: "600",
      style: "italic",
    },
    {
      path: "./fonts/namche-shadow-sans/NamcheShadowSans-BoldItalic.woff2",
      weight: "700",
      style: "italic",
    },
    {
      path: "./fonts/namche-shadow-sans/NamcheShadowSans-BlackItalic.woff2",
      weight: "800",
      style: "italic",
    },
    {
      path: "./fonts/namche-shadow-sans/NamcheShadowSans-UltraBlackItalic.woff2",
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

export const NamcheShadowMono = localFont({
  src: [
    {
      path: "./fonts/namche-shadow-mono/NamcheShadowMono-Thin.woff2",
      weight: "100",
      style: "normal",
    },
    {
      path: "./fonts/namche-shadow-mono/NamcheShadowMono-UltraLight.woff2",
      weight: "200",
      style: "normal",
    },
    {
      path: "./fonts/namche-shadow-mono/NamcheShadowMono-Light.woff2",
      weight: "300",
      style: "normal",
    },
    {
      path: "./fonts/namche-shadow-mono/NamcheShadowMono-Regular.woff2",
      weight: "400",
      style: "normal",
    },
    {
      path: "./fonts/namche-shadow-mono/NamcheShadowMono-Medium.woff2",
      weight: "500",
      style: "normal",
    },
    {
      path: "./fonts/namche-shadow-mono/NamcheShadowMono-SemiBold.woff2",
      weight: "600",
      style: "normal",
    },
    {
      path: "./fonts/namche-shadow-mono/NamcheShadowMono-Bold.woff2",
      weight: "700",
      style: "normal",
    },
    {
      path: "./fonts/namche-shadow-mono/NamcheShadowMono-Black.woff2",
      weight: "800",
      style: "normal",
    },
    {
      path: "./fonts/namche-shadow-mono/NamcheShadowMono-UltraBlack.woff2",
      weight: "900",
      style: "normal",
    },
  ],
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
});
