#!/usr/bin/env node

import { mkdir, readdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import process from "node:process";
import { fileURLToPath } from "node:url";

const repositoryRoot = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "..",
);
const packageRoot = path.join(repositoryRoot, "packages", "next");
const packageFontsRoot = path.join(packageRoot, "dist", "fonts");
const releaseFontsRoot = path.join(repositoryRoot, "fonts");
const cdnBaseUrl = "https://cdn.namche.ai/fonts/namche-shadow";
const latinUnicodeFile = path.join(
  repositoryRoot,
  "sources",
  "subsets",
  "latin.txt",
);
const latinSubset = "latin";

async function readUnicodeRange(file) {
  const ranges = (await readFile(file, "utf8"))
    .split(/\r?\n/)
    .map((line) => line.split("#", 1)[0].trim())
    .filter(Boolean);
  if (ranges.length === 0 || ranges.some((range) =>
    !/^U\+[0-9A-F]{1,6}(?:-[0-9A-F]{1,6})?$/i.test(range)
  )) {
    throw new Error(`${file} contains an invalid or empty Unicode range`);
  }
  return ranges.join(", ").toUpperCase();
}

const latinUnicodeRange = await readUnicodeRange(latinUnicodeFile);

function parseArguments(arguments_) {
  const options = { cdn: false, check: false };

  for (let index = 0; index < arguments_.length; index += 1) {
    const argument = arguments_[index];
    if (argument === "--cdn") {
      options.cdn = true;
    } else if (argument === "--check") {
      options.check = true;
    } else if (argument === "--out") {
      const value = arguments_[index + 1];
      if (!value || value.startsWith("--")) {
        throw new Error(`${argument} requires a value`);
      }
      options[argument.slice(2)] = value;
      index += 1;
    } else {
      throw new Error(`Unknown argument: ${argument}`);
    }
  }

  if (options.cdn) {
    if (!options.out) {
      throw new Error("--cdn requires --out <directory>");
    }
  } else if (options.out) {
    throw new Error("--out may only be used with --cdn");
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

const families = [
  {
    key: "sans",
    packageDirectory: "namche-shadow-sans",
    releaseDirectory: "NamcheShadowSans",
    filenamePrefix: "NamcheShadowSans",
    familyName: "Namche Shadow Sans",
  },
  {
    key: "mono",
    packageDirectory: "namche-shadow-mono",
    releaseDirectory: "NamcheShadowMono",
    filenamePrefix: "NamcheShadowMono",
    familyName: "Namche Shadow Mono",
  },
  {
    key: "pixel",
    packageDirectory: "namche-shadow-pixel",
    releaseDirectory: "NamcheShadowPixel",
    filenamePrefix: "NamcheShadowPixel",
    familyName: "Namche Shadow Pixel",
    pixel: true,
  },
  // Byte-faithful upstream Geist Sans variable faces, vendored by
  // scripts/vendor_geist.py so applications can load their body font from
  // the same release. Geist Mono and Pixel are not bundled: Namche Shadow
  // Mono and Pixel are outline-identical renames of the same binaries.
  {
    key: "geist",
    packageDirectory: "geist",
    releaseDirectory: "Geist",
    filenamePrefix: "Geist",
    familyName: "Geist",
  },
];

const staticWeights = new Map([
  ["Thin", 100],
  ["ExtraLight", 200],
  ["UltraLight", 200],
  ["Light", 300],
  ["Regular", 400],
  ["Medium", 500],
  ["SemiBold", 600],
  ["Bold", 700],
  ["ExtraBold", 800],
]);
const pixelVariants = new Set([
  "Circle",
  "Grid",
  "Line",
  "Square",
  "Triangle",
]);

function packageRelativeUrl(file) {
  return `./${path.relative(packageRoot, file).split(path.sep).join("/")}`;
}

function cdnUrl(tag, family, filename) {
  return `${cdnBaseUrl}/${tag}/${family.releaseDirectory}/webfonts/${filename}`;
}

function releaseRelativeUrl(family, filename) {
  return `./${family.releaseDirectory}/webfonts/${filename}`;
}

function subsetFilename(filename, subset) {
  return `${filename.slice(0, -".woff2".length)}-${subset}.woff2`;
}

function subsetSourceFilename(filename, subset) {
  if (!subset || !filename.endsWith(".woff2")) return filename;
  const suffix = `-${subset}.woff2`;
  if (!filename.endsWith(suffix)) {
    throw new Error(`Unexpected ${subset} subset filename: ${filename}`);
  }
  return `${filename.slice(0, -suffix.length)}.woff2`;
}

function parseFace(family, filename, allFilenames) {
  if (!filename.endsWith(".woff2")) return null;

  const stem = filename.slice(0, -".woff2".length);
  if (!stem.startsWith(family.filenamePrefix)) {
    throw new Error(
      `Unexpected file ${family.key}/${filename}: expected prefix ${family.filenamePrefix}`,
    );
  }

  const suffix = stem
    .slice(family.filenamePrefix.length)
    .replace(/^-/, "");

  if (family.pixel) {
    if (!pixelVariants.has(suffix)) {
      throw new Error(
        `Unknown Namche Shadow Pixel variant in ${family.key}/${filename}`,
      );
    }
    return {
      familyName: `${family.familyName} ${suffix}`,
      filename,
      style: "normal",
      weight: "500",
      variable: false,
    };
  }

  const variable =
    suffix === "Variable" ||
    suffix === "[wght]" ||
    suffix === "Italic[wght]";
  if (variable) {
    return {
      familyName: family.familyName,
      filename,
      style: suffix === "Italic[wght]" ? "italic" : "normal",
      weight: "100 900",
      variable: true,
    };
  }

  const italic = suffix.endsWith("Italic");
  const weightName = italic ? suffix.slice(0, -"Italic".length) : suffix;
  let weight;
  if (weightName === "Italic" || weightName === "") {
    weight = 400;
  } else if (weightName === "UltraBlack") {
    weight = 900;
  } else if (weightName === "Black") {
    // The npm Sans copy uses Black for release ExtraBold and UltraBlack for
    // release Black. Raw release directories use ExtraBold and Black.
    weight = family.key === "sans" && allFilenames.some((name) => name.includes("UltraBlack"))
      ? 800
      : 900;
  } else {
    weight = staticWeights.get(weightName);
  }

  if (!weight) {
    throw new Error(`Unknown weight or style in ${family.key}/${filename}`);
  }

  return {
    familyName: family.familyName,
    filename,
    style: italic || suffix === "Italic" ? "italic" : "normal",
    weight: String(weight),
    variable: false,
  };
}

async function collectFaces(family, directory, urlForFile, subset = null) {
  const filenames = (await readdir(directory)).sort();
  const sourceFilenames = filenames.map((filename) =>
    subsetSourceFilename(filename, subset)
  );
  const faces = filenames
    .map((filename, index) => {
      const face = parseFace(
        family,
        sourceFilenames[index],
        sourceFilenames,
      );
      if (!face) return null;
      return {
        ...face,
        filename,
        subset,
        unicodeRange: subset ? latinUnicodeRange : null,
      };
    })
    .filter(Boolean);

  if (faces.length === 0) {
    throw new Error(`No WOFF2 files found in ${directory}`);
  }

  const variableStyles = new Set(
    faces.filter((face) => face.variable).map((face) => face.style),
  );
  return faces
    .filter((face) => face.variable || !variableStyles.has(face.style))
    .sort((a, b) => {
      const styleOrder =
        (a.style === "normal" ? 0 : 1) - (b.style === "normal" ? 0 : 1);
      if (styleOrder !== 0) return styleOrder;
      const weightOrder = Number.parseInt(a.weight, 10) - Number.parseInt(b.weight, 10);
      if (weightOrder !== 0) return weightOrder;
      return a.familyName.localeCompare(b.familyName);
    })
    .map((face) => ({
      ...face,
      url: urlForFile(face.filename),
    }));
}

async function collectPackageFaces() {
  const facesByFamily = new Map();
  for (const family of families) {
    const directory = path.join(packageFontsRoot, family.packageDirectory);
    facesByFamily.set(
      family.key,
      await collectFaces(
        family,
        directory,
        (filename) => packageRelativeUrl(path.join(directory, filename)),
      ),
    );
  }
  return facesByFamily;
}

async function collectPackageSubsetFaces(subset) {
  const facesByFamily = new Map();
  for (const family of families) {
    const directory = path.join(
      packageFontsRoot,
      family.packageDirectory,
      "subsets",
    );
    facesByFamily.set(
      family.key,
      await collectFaces(
        family,
        directory,
        (filename) => packageRelativeUrl(path.join(directory, filename)),
        subset,
      ),
    );
  }
  return facesByFamily;
}

function deriveSubsetFaces(faces, subset, urlForFile) {
  return faces.map((face) => {
    const filename = subsetFilename(face.filename, subset);
    return {
      ...face,
      filename,
      subset,
      unicodeRange: latinUnicodeRange,
      url: urlForFile(`subsets/${filename}`),
    };
  });
}

async function collectCdnFaces(tag) {
  const facesByFamily = new Map();
  for (const family of families) {
    const directory = path.join(releaseFontsRoot, family.releaseDirectory, "webfonts");
    facesByFamily.set(
      family.key,
      await collectFaces(
        family,
        directory,
        (filename) => cdnUrl(tag, family, filename),
      ),
    );
  }
  return facesByFamily;
}

async function collectCdnSubsetFaces(tag, subset) {
  const fullFaces = await collectCdnFaces(tag);
  return new Map(families.map((family) => [
    family.key,
    deriveSubsetFaces(
      fullFaces.get(family.key),
      subset,
      (filename) => cdnUrl(tag, family, filename),
    ),
  ]));
}

async function collectReleaseFaces(root = releaseFontsRoot) {
  const facesByFamily = new Map();
  for (const family of families) {
    const directory = path.join(root, family.releaseDirectory, "webfonts");
    facesByFamily.set(
      family.key,
      await collectFaces(
        family,
        directory,
        (filename) => releaseRelativeUrl(family, filename),
      ),
    );
  }
  return facesByFamily;
}

async function collectReleaseSubsetFaces(root, subset) {
  const fullFaces = await collectReleaseFaces(root);
  return new Map(families.map((family) => [
    family.key,
    deriveSubsetFaces(
      fullFaces.get(family.key),
      subset,
      (filename) => releaseRelativeUrl(family, filename),
    ),
  ]));
}

function faceDescriptors(facesByFamily) {
  return families.flatMap((family) =>
    facesByFamily.get(family.key).map(({ familyName, style, weight }) =>
      `${familyName}\t${style}\t${weight}`,
    ),
  );
}

function assertMatchingFaces(...faceSets) {
  const [expected, ...others] = faceSets.map(faceDescriptors);
  if (others.some((descriptors) =>
    JSON.stringify(descriptors) !== JSON.stringify(expected)
  )) {
    throw new Error(
      "The npm, release-relative, and absolute CDN font layouts select different faces; regenerate the npm font fixtures.",
    );
  }
}

function renderStylesheet(selectedFamilies, faces, mode) {
  const familyLabel =
    selectedFamilies.length === families.length
      ? "all Namche Shadow families and Geist"
      : selectedFamilies[0].familyName;
  const delivery = mode === "cdn"
    ? "URLs are pinned to an immutable CDN release."
    : mode === "release"
      ? "URLs resolve relative to the release root for version-agnostic CDN deployment."
      : "URLs resolve to font binaries inside the npm package.";
  const subsetDescription = faces.every((face) => face.subset === latinSubset)
    ? " This entry point contains the opt-in Latin web subset."
    : "";
  const header = `/*
 * Generated by scripts/build-webfont-css.mjs for ${familyLabel}. Do not edit.
 * Licensed under the SIL Open Font License 1.1; see LICENSE.txt or OFL.txt.
 * Variable faces are preferred per style; statics are emitted only when no
 * matching variable face exists, avoiding duplicate downloads for one axis.
 * ${delivery}${subsetDescription}
 */`;

  const rules = faces.map(
    (face) => `@font-face {
  font-family: "${face.familyName}";
  src: url("${face.url}") format("woff2");
  font-style: ${face.style};
  font-weight: ${face.weight};
  font-display: swap;${face.unicodeRange ? `
  unicode-range: ${face.unicodeRange};` : ""}
}`,
  );

  return `${header}\n\n${rules.join("\n\n")}\n`;
}

function renderOutputs(facesByFamily, mode, suffix = "") {
  return new Map([
    [
      `fonts${suffix}.css`,
      renderStylesheet(
        families,
        families.flatMap((family) => facesByFamily.get(family.key)),
        mode,
      ),
    ],
    ...families.map((family) => [
      `${family.key}${suffix}.css`,
      renderStylesheet([family], facesByFamily.get(family.key), mode),
    ]),
  ]);
}

async function writeOrCheck(outputs, destinationRoot, check) {
  if (!check) await mkdir(destinationRoot, { recursive: true });

  let stale = false;
  for (const [filename, contents] of outputs) {
    const destination = path.join(destinationRoot, filename);
    if (check) {
      let current;
      try {
        current = await readFile(destination, "utf8");
      } catch (error) {
        if (error.code !== "ENOENT") throw error;
      }
      if (current !== contents) {
        console.error(`${path.relative(repositoryRoot, destination)} is stale or missing`);
        stale = true;
      }
    } else {
      await writeFile(destination, contents);
      console.log(`Wrote ${path.relative(repositoryRoot, destination)}`);
    }
  }
  return stale;
}

let stale = false;
if (options.cdn) {
  const outputRoot = path.resolve(options.out);
  const releaseFaces = await collectReleaseFaces(outputRoot);
  const releaseLatinFaces = await collectReleaseSubsetFaces(
    outputRoot,
    latinSubset,
  );
  stale = await writeOrCheck(
    new Map([
      ...renderOutputs(releaseFaces, "release"),
      ...renderOutputs(releaseLatinFaces, "release", "-latin"),
    ]),
    outputRoot,
    options.check,
  );
} else {
  const manifest = JSON.parse(
    await readFile(path.join(packageRoot, "package.json"), "utf8"),
  );
  const tag = `v${manifest.version}`;
  const packageFaces = await collectPackageFaces();
  const packageLatinFaces = await collectPackageSubsetFaces(latinSubset);
  const releaseFaces = await collectReleaseFaces();
  const releaseLatinFaces = await collectReleaseSubsetFaces(
    releaseFontsRoot,
    latinSubset,
  );
  const cdnFaces = await collectCdnFaces(tag);
  const cdnLatinFaces = await collectCdnSubsetFaces(tag, latinSubset);
  assertMatchingFaces(packageFaces, releaseFaces, cdnFaces);
  assertMatchingFaces(packageLatinFaces, releaseLatinFaces, cdnLatinFaces);

  stale = await writeOrCheck(
    new Map([
      ...renderOutputs(packageFaces, "package"),
      ...renderOutputs(packageLatinFaces, "package", "-latin"),
    ]),
    packageRoot,
    options.check,
  );
  stale = (await writeOrCheck(
    new Map([
      ...renderOutputs(cdnFaces, "cdn", ".cdn"),
      ...renderOutputs(cdnLatinFaces, "cdn", "-latin.cdn"),
    ]),
    packageRoot,
    options.check,
  )) || stale;

  const documentationOutput = new Map([
    ["fonts.css", renderOutputs(releaseFaces, "release").get("fonts.css")],
    [
      "fonts-latin.css",
      renderOutputs(releaseLatinFaces, "release", "-latin").get(
        "fonts-latin.css",
      ),
    ],
  ]);
  stale = (await writeOrCheck(
    documentationOutput,
    path.join(repositoryRoot, "documentation", "cdn"),
    options.check,
  )) || stale;
}

if (stale) {
  console.error(
    options.cdn
      ? "Regenerate the release-relative CDN stylesheets with the same --cdn and --out arguments."
      : "Run `npm run build:css` in packages/next and commit the generated files.",
  );
  process.exit(1);
}

if (options.check) {
  console.log(
    options.cdn
      ? "Generated release-relative CDN webfont CSS is up to date."
      : "Generated package and CDN webfont CSS is up to date.",
  );
}
