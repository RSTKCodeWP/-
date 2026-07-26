/**
 * @module design-token-defined.test
 * @description Guards against undefined design-token utility classes. The
 * dark-first design system defines a fixed set of `--color-*` tokens in
 * `globals.css` (namespaces: accent / bg / border / gcs / status / text). A
 * class like `border-border-subtle` or `text-status-critical` whose token is
 * NOT defined resolves to an invalid `var(--color-…)`, which for a border falls
 * back to `currentColor` (the near-white text colour) — so the border renders
 * WHITE (and a bg → transparent, a text → inherited). This test fails, with a
 * per-class offender list, if ANY color utility (`text-`, `bg-`, `border[-trblxy]-`,
 * `ring-`, `stroke-`, `fill-`, `from-`, `to-`, `via-`, `divide-`, `outline-`,
 * `decoration-`, `caret-`, `accent-`, `placeholder-`, `shadow-`) references a
 * CUSTOM-namespaced token that `globals.css` does not define. Tailwind palette
 * colours (`text-blue-500`, `bg-white`) and dynamic (`bg-status-${x}`) classes
 * are out of scope by construction.
 * @license GPL-3.0-only
 */

import { describe, it, expect } from "vitest";
import { readFileSync, readdirSync } from "node:fs";
import { join, resolve } from "node:path";

const SRC = resolve(__dirname, "../../src");
const GLOBALS = resolve(SRC, "app/globals.css");

/** The `--color-<name>` tokens the design system actually defines. */
function definedColorTokens(): Set<string> {
  const css = readFileSync(GLOBALS, "utf8");
  const tokens = new Set<string>();
  for (const m of css.matchAll(/--color-([a-z0-9-]+)\s*:/g)) tokens.add(m[1]);
  return tokens;
}

/** Walk src for .ts/.tsx files (className strings live here, not in .css). */
function sourceFiles(dir: string, out: string[] = []): string[] {
  for (const ent of readdirSync(dir, { withFileTypes: true })) {
    const p = join(dir, ent.name);
    if (ent.isDirectory()) {
      if (ent.name === "node_modules" || ent.name === "generated") continue;
      sourceFiles(p, out);
    } else if (/\.tsx?$/.test(ent.name) && !ent.name.endsWith(".d.ts")) {
      out.push(p);
    }
  }
  return out;
}

// Color-bearing utility prefixes.
const UTIL =
  "text|bg|border(?:-[trblxy])?|ring(?:-offset)?|divide|outline|fill|stroke|from|via|to|decoration|caret|accent|placeholder|shadow";

describe("design tokens are all defined (no white-border fallback)", () => {
  it("every color utility referencing a custom token namespace uses a DEFINED --color-* token", () => {
    const defined = definedColorTokens();
    // Sanity: the core tokens must exist, else the regex extraction is wrong.
    for (const core of ["border-default", "bg-primary", "text-primary", "accent-primary", "status-error"]) {
      expect(defined.has(core), `globals.css must define --color-${core}`).toBe(true);
    }

    // Custom namespaces are derived from the defined tokens (future-proof: a new
    // `--color-node-*` tier automatically joins the check). Only classes whose
    // token part starts with one of these namespaces are in scope — a Tailwind
    // palette colour (`blue-500`, `white`) is not, and is skipped.
    const namespaces = [...new Set([...defined].map((t) => t.split("-")[0]))];
    const re = new RegExp(
      `(?<![a-zA-Z0-9-])(?:${UTIL})-((?:${namespaces.join("|")})-[a-z0-9-]+)`,
      "g",
    );

    const offenders: string[] = [];
    for (const file of sourceFiles(SRC)) {
      const text = readFileSync(file, "utf8");
      for (const m of text.matchAll(re)) {
        const token = m[1];
        if (token.endsWith("-")) continue; // dynamic (`bg-status-${x}`) — skip
        if (!defined.has(token)) {
          offenders.push(`${file.slice(SRC.length + 1)}: ${m[0]} (→ --color-${token} undefined)`);
        }
      }
    }

    expect(
      offenders,
      `Undefined design-token classes render white/transparent. Remap to a defined token ` +
        `or define the token in globals.css. Defined: ${[...defined].sort().join(", ")}.\n` +
        `${[...new Set(offenders)].join("\n")}`,
    ).toEqual([]);
  });
});
