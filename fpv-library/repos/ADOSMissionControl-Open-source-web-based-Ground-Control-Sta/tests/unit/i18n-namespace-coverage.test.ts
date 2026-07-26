/**
 * @module i18n-namespace-coverage.test
 * @description Guards against the class of bug where a component calls
 * `useTranslations("X")` for a namespace that was never added to the locale
 * files. The parity test only compares locales to each other, so a namespace
 * missing from ALL locales passes it — but at runtime next-intl throws
 * `MISSING_MESSAGE` and the UI renders raw keys. This test statically scans
 * `src/` for `useTranslations("literal")` calls and asserts each namespace is a
 * top-level key in `en.json`. (Static namespace literals only; dynamic keys and
 * `useTranslations()` with no argument are out of scope.)
 * @license GPL-3.0-only
 */

import { describe, it, expect } from "vitest";
import { readFileSync, readdirSync } from "node:fs";
import { join, resolve } from "node:path";

const SRC_DIR = resolve(__dirname, "../../src");
const EN = resolve(__dirname, "../../locales/en.json");

/** Recursively collect `.ts`/`.tsx` source files (excluding test files). */
function sourceFiles(dir: string): string[] {
  const out: string[] = [];
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const full = join(dir, entry.name);
    if (entry.isDirectory()) {
      out.push(...sourceFiles(full));
    } else if (
      (entry.name.endsWith(".ts") || entry.name.endsWith(".tsx")) &&
      !entry.name.endsWith(".test.ts") &&
      !entry.name.endsWith(".test.tsx")
    ) {
      out.push(full);
    }
  }
  return out;
}

/** Every static namespace passed to `useTranslations("...")` across `src/`. */
function usedNamespaces(): Map<string, string> {
  const re = /useTranslations\(\s*["'`]([^"'`]+)["'`]\s*\)/g;
  const found = new Map<string, string>(); // namespace -> first file using it
  for (const file of sourceFiles(SRC_DIR)) {
    const text = readFileSync(file, "utf-8");
    let m: RegExpExecArray | null;
    while ((m = re.exec(text)) !== null) {
      const ns = m[1];
      if (!found.has(ns)) found.set(ns, file);
    }
  }
  return found;
}

/** Resolve a (possibly dotted) namespace path in the message tree and return it
 * only when it lands on an object — a `useTranslations("a.b")` namespace must be
 * an object whose keys the component then translates. `undefined` = the path is
 * absent or points at a leaf string (not a valid namespace). */
function resolveNamespace(root: Record<string, unknown>, ns: string): unknown {
  let cur: unknown = root;
  for (const part of ns.split(".")) {
    if (cur === null || typeof cur !== "object" || Array.isArray(cur)) return undefined;
    cur = (cur as Record<string, unknown>)[part];
  }
  return cur;
}

describe("i18n namespace coverage", () => {
  it("every useTranslations() namespace exists in en.json", () => {
    const en = JSON.parse(readFileSync(EN, "utf-8")) as Record<string, unknown>;
    const used = usedNamespaces();
    expect(used.size).toBeGreaterThan(0); // the scan actually found calls

    const missing = [...used.entries()]
      .filter(([ns]) => {
        const resolved = resolveNamespace(en, ns);
        return resolved === null || typeof resolved !== "object" || Array.isArray(resolved);
      })
      .map(([ns, file]) => `  "${ns}" (used in ${file.replace(SRC_DIR, "src")})`)
      .sort();

    if (missing.length > 0) {
      throw new Error(
        `useTranslations() namespaces missing from locales/en.json:\n${missing.join("\n")}`,
      );
    }
  });
});
