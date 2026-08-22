#!/usr/bin/env node

import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import process from "node:process";

const cssFiles = ["fonts.css", "sans.css", "mono.css", "pixel.css"];
const cdnBaseUrl = "https://cdn.namche.ai/fonts/namche-shadow";

function parseArguments(arguments_) {
  const options = {};
  for (let index = 0; index < arguments_.length; index += 1) {
    const argument = arguments_[index];
    if (!["--tag", "--styles", "--fonts"].includes(argument)) {
      throw new Error(`Unknown argument: ${argument}`);
    }
    const value = arguments_[index + 1];
    if (!value || value.startsWith("--")) {
      throw new Error(`${argument} requires a value`);
    }
    options[argument.slice(2)] = value;
    index += 1;
  }

  for (const required of ["tag", "styles", "fonts"]) {
    if (!options[required]) throw new Error(`--${required} is required`);
  }
  return options;
}

let options;
try {
  options = parseArguments(process.argv.slice(2));
} catch (error) {
  console.error(error.message);
  process.exit(2);
}

const stylesRoot = path.resolve(options.styles);
const fontsRoot = path.resolve(options.fonts);
const expectedPrefix = `${cdnBaseUrl}/${options.tag}/`;

for (const cssFilename of cssFiles) {
  const cssPath = path.join(stylesRoot, cssFilename);
  if (!existsSync(cssPath)) {
    throw new Error(`${cssPath} is missing`);
  }

  const css = readFileSync(cssPath, "utf8");
  const urls = [...css.matchAll(/url\(["']?([^"')]+)["']?\)/g)].map(
    (match) => match[1],
  );
  if (urls.length === 0) {
    throw new Error(`${cssFilename} contains no font URLs`);
  }

  for (const url of urls) {
    if (!url.startsWith(expectedPrefix)) {
      throw new Error(
        `${cssFilename} URL is not pinned to ${options.tag}: ${url}`,
      );
    }

    const releasePath = decodeURIComponent(url.slice(expectedPrefix.length));
    const fontPath = path.resolve(fontsRoot, releasePath);
    const relativePath = path.relative(fontsRoot, fontPath);
    if (relativePath.startsWith("..") || path.isAbsolute(relativePath)) {
      throw new Error(`${cssFilename} URL escapes the release font root: ${url}`);
    }
    if (!existsSync(fontPath)) {
      throw new Error(
        `${cssFilename} URL has no matching file in the release archive: ${url}`,
      );
    }
  }

  console.log(
    `Verified ${cssFilename}: ${urls.length} CDN URLs exist in the release archive.`,
  );
}
