#!/usr/bin/env node
/**
 * Backfill missing keys from `locales/en.json` into every other locale
 * file. Existing translated values are preserved; only missing keys are
 * added with the English value as a placeholder so the i18n parity test
 * stays green and translators can find unfinished strings later.
 *
 * Usage: node scripts/i18n-merge-missing.mjs
 */
import { readFileSync, writeFileSync, readdirSync } from "node:fs";
import { resolve, dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const root = resolve(here, "..");
const localesDir = join(root, "locales");
const en = JSON.parse(readFileSync(join(localesDir, "en.json"), "utf8"));

function mergeMissing(source, target) {
  if (typeof source !== "object" || source === null) return target;
  if (typeof target !== "object" || target === null) return source;
  const out = Array.isArray(target) ? [...target] : { ...target };
  for (const key of Object.keys(source)) {
    if (!(key in out)) {
      out[key] = source[key];
    } else if (
      typeof source[key] === "object"
      && source[key] !== null
      && !Array.isArray(source[key])
    ) {
      out[key] = mergeMissing(source[key], out[key]);
    }
  }
  return out;
}

const files = readdirSync(localesDir).filter(
  (f) => f.endsWith(".json") && f !== "en.json",
);

for (const file of files) {
  const path = join(localesDir, file);
  const target = JSON.parse(readFileSync(path, "utf8"));
  const merged = mergeMissing(en, target);
  writeFileSync(path, JSON.stringify(merged, null, 2) + "\n", "utf8");
  console.log(`merged ${file}`);
}
console.log("done");
