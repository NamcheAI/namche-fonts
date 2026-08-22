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

function parseArguments(arguments_) {
  const options = { cdn: false, check: false };

  for (let index = 0; index < arguments_.length; index += 1) {
    const argument = arguments_[index];
    if (argument === "--cdn") {
      options.cdn = true;
    } else if (argument === "--check") {
      options.check = true;
    } else if (argument === "--tag" || argument === "--out") {
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
    if (!options.tag || !options.out) {
      throw new Error("--cdn requires both --tag vX.Y.Z and --out <directory>");
    }
  } else if (options.tag || options.out) {
    throw new Error("--tag and --out may only be used with --cdn");
  }

  if (options.tag && !/^v\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?$/.test(options.tag)) {
    throw new Error(`Invalid release tag: ${options.tag}`);
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

async function collectFaces(family, directory, urlForFile) {
  const filenames = (await readdir(directory)).sort();
  const faces = filenames
    .map((filename) => parseFace(family, filename, filenames))
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

function faceDescriptors(facesByFamily) {
  return families.flatMap((family) =>
    facesByFamily.get(family.key).map(({ familyName, style, weight }) =>
      `${familyName}\t${style}\t${weight}`,
    ),
  );
}

function assertMatchingFaces(packageFaces, cdnFaces) {
  const packageDescriptors = faceDescriptors(packageFaces);
  const cdnDescriptors = faceDescriptors(cdnFaces);
  if (JSON.stringify(packageDescriptors) !== JSON.stringify(cdnDescriptors)) {
    throw new Error(
      "The npm and release font layouts select different faces; regenerate the npm font fixtures.",
    );
  }
}

function renderStylesheet(selectedFamilies, faces, mode) {
  const familyLabel =
    selectedFamilies.length === families.length
      ? "all Namche Shadow families"
      : selectedFamilies[0].familyName;
  const delivery = mode === "cdn"
    ? "URLs are pinned to an immutable CDN release."
    : "URLs resolve to font binaries inside the npm package.";
  const header = `/*
 * Generated by scripts/build-webfont-css.mjs for ${familyLabel}. Do not edit.
 * Licensed under the SIL Open Font License 1.1; see LICENSE.txt or OFL.txt.
 * Variable faces are preferred per style; statics are emitted only when no
 * matching variable face exists, avoiding duplicate downloads for one axis.
 * ${delivery}
 */`;

  const rules = faces.map(
    (face) => `@font-face {
  font-family: "${face.familyName}";
  src: url("${face.url}") format("woff2");
  font-style: ${face.style};
  font-weight: ${face.weight};
  font-display: swap;
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
  const cdnFaces = await collectCdnFaces(options.tag);
  stale = await writeOrCheck(
    renderOutputs(cdnFaces, "cdn"),
    path.resolve(options.out),
    options.check,
  );
} else {
  const manifest = JSON.parse(
    await readFile(path.join(packageRoot, "package.json"), "utf8"),
  );
  const tag = `v${manifest.version}`;
  const packageFaces = await collectPackageFaces();
  const cdnFaces = await collectCdnFaces(tag);
  assertMatchingFaces(packageFaces, cdnFaces);

  stale = await writeOrCheck(
    renderOutputs(packageFaces, "package"),
    packageRoot,
    options.check,
  );
  stale = (await writeOrCheck(
    renderOutputs(cdnFaces, "cdn", ".cdn"),
    packageRoot,
    options.check,
  )) || stale;

  const documentationOutput = new Map([
    ["fonts.css", renderOutputs(cdnFaces, "cdn").get("fonts.css")],
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
      ? "Regenerate the release CDN stylesheets with the same --cdn, --tag, and --out arguments."
      : "Run `npm run build:css` in packages/next and commit the generated files.",
  );
  process.exit(1);
}

if (options.check) {
  console.log(
    options.cdn
      ? `Generated CDN webfont CSS for ${options.tag} is up to date.`
      : "Generated package and CDN webfont CSS is up to date.",
  );
}
