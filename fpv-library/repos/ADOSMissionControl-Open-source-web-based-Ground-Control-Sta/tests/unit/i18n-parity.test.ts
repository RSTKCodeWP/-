/**
 * @module i18n-parity.test
 * @description Ensures every non-English locale file has the same set of
 * translation keys as `en.json`. Fails with a per-locale list of missing
 * and extra keys so translators know exactly what to fix.
 * @license GPL-3.0-only
 */

import { describe, it, expect } from "vitest";
import { readFileSync, readdirSync } from "node:fs";
import { join, resolve } from "node:path";

const LOCALES_DIR = resolve(__dirname, "../../locales");
const CANONICAL = "en";

function flatten(obj: unknown, prefix = ""): string[] {
  if (obj === null || typeof obj !== "object" || Array.isArray(obj)) {
    return prefix ? [prefix] : [];
  }
  const keys: string[] = [];
  for (const [k, v] of Object.entries(obj as Record<string, unknown>)) {
    const path = prefix ? `${prefix}.${k}` : k;
    if (v !== null && typeof v === "object" && !Array.isArray(v)) {
      keys.push(...flatten(v, path));
    } else {
      keys.push(path);
    }
  }
  return keys;
}

function loadLocale(code: string): Record<string, unknown> {
  const raw = readFileSync(join(LOCALES_DIR, `${code}.json`), "utf-8");
  return JSON.parse(raw);
}

describe("i18n parity", () => {
  const canonicalKeys = new Set(flatten(loadLocale(CANONICAL)));
  const otherLocales = readdirSync(LOCALES_DIR)
    .filter((f) => f.endsWith(".json") && f !== `${CANONICAL}.json`)
    .map((f) => f.replace(/\.json$/, ""));

  it("canonical en.json has a non-empty key set", () => {
    expect(canonicalKeys.size).toBeGreaterThan(0);
  });

  for (const code of otherLocales) {
    it(`${code}.json matches en.json key set`, () => {
      const keys = new Set(flatten(loadLocale(code)));
      const missing = [...canonicalKeys].filter((k) => !keys.has(k)).sort();
      const extra = [...keys].filter((k) => !canonicalKeys.has(k)).sort();
      const report: string[] = [];
      if (missing.length > 0) {
        report.push(
          `  Missing ${missing.length} key(s) in ${code}.json:\n    - ${missing.join("\n    - ")}`,
        );
      }
      if (extra.length > 0) {
        report.push(
          `  Extra ${extra.length} key(s) in ${code}.json (not in en.json):\n    - ${extra.join("\n    - ")}`,
        );
      }
      if (report.length > 0) {
        throw new Error(`i18n parity mismatch for ${code}:\n${report.join("\n")}`);
      }
    });
  }
});
