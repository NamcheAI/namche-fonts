#!/usr/bin/env node

import { execFileSync } from "node:child_process";
import {
  existsSync,
  mkdtempSync,
  mkdirSync,
  readFileSync,
  readdirSync,
  rmSync,
} from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const repositoryRoot = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "..",
);
const packageRoot = path.join(repositoryRoot, "packages", "next");
const temporaryDirectory = mkdtempSync(
  path.join(tmpdir(), "namche-shadow-package-"),
);

const localCssFiles = ["fonts.css", "sans.css", "mono.css", "pixel.css"];
const cdnCssFiles = [
  "fonts.cdn.css",
  "sans.cdn.css",
  "mono.cdn.css",
  "pixel.cdn.css",
];
const existingExports = new Map([
  ["./font", { default: "./dist/font.js", types: "./dist/font.d.ts" }],
  ["./font/mono", { default: "./dist/mono.js", types: "./dist/mono.d.ts" }],
  [
    "./font/mono-non-variable",
    {
      default: "./dist/mono-non-variable.js",
      types: "./dist/mono-non-variable.d.ts",
    },
  ],
  ["./font/sans", { default: "./dist/sans.js", types: "./dist/sans.d.ts" }],
  [
    "./font/sans-non-variable",
    {
      default: "./dist/sans-non-variable.js",
      types: "./dist/sans-non-variable.d.ts",
    },
  ],
  ["./font/pixel", { default: "./dist/pixel.js", types: "./dist/pixel.d.ts" }],
]);

try {
  execFileSync(
    "npm",
    ["pack", "--silent", "--pack-destination", temporaryDirectory],
    {
      cwd: packageRoot,
      env: {
        ...process.env,
        npm_config_cache: path.join(temporaryDirectory, "npm-cache"),
      },
      stdio: "inherit",
    },
  );
  const tarballs = readdirSync(temporaryDirectory).filter((name) =>
    name.endsWith(".tgz"),
  );
  if (tarballs.length !== 1) {
    throw new Error(`Expected one npm tarball, found ${tarballs.length}`);
  }

  const tarball = path.join(temporaryDirectory, tarballs[0]);
  const extractionRoot = path.join(temporaryDirectory, "unpacked");
  mkdirSync(extractionRoot);
  execFileSync("tar", ["-xzf", tarball, "-C", extractionRoot]);
  const packedPackage = path.join(extractionRoot, "package");
  const manifest = JSON.parse(
    readFileSync(path.join(packedPackage, "package.json"), "utf8"),
  );

  for (const cssFilename of localCssFiles) {
    const cssPath = path.join(packedPackage, cssFilename);
    if (!existsSync(cssPath)) {
      throw new Error(`${cssFilename} is missing from the npm tarball`);
    }

    const css = readFileSync(cssPath, "utf8");
    const urls = [...css.matchAll(/url\(["']?([^"')]+)["']?\)/g)].map(
      (match) => match[1],
    );
    if (urls.length === 0) {
      throw new Error(`${cssFilename} contains no font URLs`);
    }

    for (const url of urls) {
      if (!url.startsWith("./")) {
        throw new Error(`${cssFilename} contains a non-relative URL: ${url}`);
      }
      const fontPath = path.resolve(path.dirname(cssPath), url);
      const relativePath = path.relative(packedPackage, fontPath);
      if (relativePath.startsWith("..") || path.isAbsolute(relativePath)) {
        throw new Error(`${cssFilename} URL escapes the package: ${url}`);
      }
      if (!existsSync(fontPath)) {
        throw new Error(`${cssFilename} URL is missing from the tarball: ${url}`);
      }
    }

    console.log(`Verified ${cssFilename}: ${urls.length} font URLs resolve.`);
  }

  const cdnPrefix =
    `https://cdn.namche.ai/fonts/namche-shadow/v${manifest.version}/`;
  for (const cssFilename of cdnCssFiles) {
    const cssPath = path.join(packedPackage, cssFilename);
    if (!existsSync(cssPath)) {
      throw new Error(`${cssFilename} is missing from the npm tarball`);
    }

    const css = readFileSync(cssPath, "utf8");
    const urls = [...css.matchAll(/url\(["']?([^"')]+)["']?\)/g)].map(
      (match) => match[1],
    );
    if (urls.length === 0) {
      throw new Error(`${cssFilename} contains no font URLs`);
    }
    for (const url of urls) {
      if (!url.startsWith(cdnPrefix)) {
        throw new Error(
          `${cssFilename} URL is not pinned to package version ${manifest.version}: ${url}`,
        );
      }
    }

    console.log(
      `Verified ${cssFilename}: ${urls.length} URLs are pinned to v${manifest.version}.`,
    );
  }

  for (const cssFilename of [...localCssFiles, ...cdnCssFiles]) {
    const exportName = `./${cssFilename}`;
    if (manifest.exports[exportName] !== exportName) {
      throw new Error(
        `${exportName} export changed: found ${manifest.exports[exportName]}`,
      );
    }
  }
  console.log("Verified all webfont CSS package exports.");

  for (const [exportName, expected] of existingExports) {
    const entry = manifest.exports[exportName];
    for (const [condition, expectedTarget] of Object.entries(expected)) {
      if (entry?.[condition] !== expectedTarget) {
        throw new Error(
          `${exportName} ${condition} changed: expected ${expectedTarget}, found ${entry?.[condition]}`,
        );
      }
      if (!existsSync(path.resolve(packedPackage, expectedTarget))) {
        throw new Error(`${exportName} target is missing: ${expectedTarget}`);
      }
    }

    const javascriptPath = path.resolve(packedPackage, expected.default);
    const javascript = readFileSync(javascriptPath, "utf8");
    const fontUrls = [
      ...javascript.matchAll(/["'](\.\/fonts\/[^"']+)["']/g),
    ].map((match) => match[1]);
    if (fontUrls.length === 0) {
      throw new Error(`${exportName} contains no local font references`);
    }
    for (const fontUrl of fontUrls) {
      const fontPath = path.resolve(path.dirname(javascriptPath), fontUrl);
      if (!existsSync(fontPath)) {
        throw new Error(`${exportName} font is missing: ${fontUrl}`);
      }
    }
  }
  console.log("Verified all existing Next.js exports and font URLs unchanged.");
  console.log(`Packed ${tarballs[0]} successfully.`);
} finally {
  rmSync(temporaryDirectory, { recursive: true, force: true });
}
