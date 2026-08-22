#!/usr/bin/env node

import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import process from "node:process";

const cssFiles = ["fonts.css", "sans.css", "mono.css", "pixel.css"];

// One directory, deliberately. Separate --styles and --fonts roots let this
// script validate a layout that was not the one being shipped: the stylesheets
// sat at the archive root while the families sat under fonts/, and pointing the
// two flags at different directories made a broken archive pass. The stylesheet
// resolves its relative URLs against its own directory, so that is the only
// directory this check may look in.
function parseArguments(arguments_) {
  const options = {};
  for (let index = 0; index < arguments_.length; index += 1) {
    const argument = arguments_[index];
    if (argument !== "--release") {
      throw new Error(`Unknown argument: ${argument}`);
    }
    const value = arguments_[index + 1];
    if (!value || value.startsWith("--")) {
      throw new Error(`${argument} requires a value`);
    }
    options.release = value;
    index += 1;
  }

  if (!options.release) throw new Error("--release is required");
  return options;
}

let options;
try {
  options = parseArguments(process.argv.slice(2));
} catch (error) {
  console.error(error.message);
  process.exit(2);
}

const releaseRoot = path.resolve(options.release);
const stylesRoot = releaseRoot;
const fontsRoot = releaseRoot;

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
    if (!url.startsWith("./")) {
      throw new Error(`${cssFilename} contains a non-relative URL: ${url}`);
    }

    const releasePath = decodeURIComponent(url.slice(2));
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
    `Verified ${cssFilename}: ${urls.length} relative font URLs exist in the release archive.`,
  );
}
