import { parseSetCommands } from "./output.js";

/**
 * Extract a Betaflight semver from a CLI dump's header line, if present.
 *
 * Recognizes headers like:
 *   # Betaflight / STM32F745 (S745) 4.4.0 Nov  1 2022 / 01:00:00 (abc) MSP API: 1.45
 *
 * @param {string} text
 * @returns {string|null} Semver string (e.g. "4.5.1"), or null if not found.
 */
export function extractVersion(text) {
  if (!text) return null;
  const match = text.match(
    /Betaflight\s*\/\s*\S+(?:\s+\(\S+\))?\s+(\d+\.\d+\.\d+)/i,
  );
  return match ? match[1] : null;
}

/**
 * Collect the set of `set` keys defined anywhere in a parsed section array.
 * @param {Array<{lines: string[]}>} sections
 * @returns {Set<string>}
 */
function collectSetKeys(sections) {
  const keys = new Set();
  for (const sec of sections ?? []) {
    const { sets } = parseSetCommands(sec.lines);
    for (const k of sets.keys()) keys.add(k);
  }
  return keys;
}

/**
 * Memoize the A/B key sets per `sections` array instance. `sections` is a
 * fresh array on every Compare, so caching by reference is sufficient to
 * avoid re-parsing every finding refresh (which fires on each selection
 * toggle) without needing manual invalidation.
 * @type {WeakMap<object, {keysA: Set<string>, keysB: Set<string>}>}
 */
const keyCache = new WeakMap();

function keySetsFor(sections) {
  if (!sections || sections.length === 0) {
    return { keysA: new Set(), keysB: new Set() };
  }
  const cached = keyCache.get(sections);
  if (cached) return cached;
  const secA = sections.map((s) => ({ lines: s.linesA ?? [] }));
  const secB = sections.map((s) => ({ lines: s.linesB ?? [] }));
  const entry = { keysA: collectSetKeys(secA), keysB: collectSetKeys(secB) };
  keyCache.set(sections, entry);
  return entry;
}

/**
 * Validate a merged CLI output against the two source dumps.
 *
 * Convention: CLI A is the *base* (its firmware version is treated as the
 * validation target) and CLI B is the *import*. Keys that only appear in B
 * are flagged when the merged output contains them, because A's firmware
 * may not recognize them.
 *
 * @param {{
 *   mergedText: string,
 *   sections?: Array<{id: string, linesA: string[], linesB: string[]}>,
 *   versionA?: string|null,
 *   versionB?: string|null,
 * }} input
 * @returns {Array<{category: string, severity: 'error'|'warning'|'info', message: string, key?: string, line?: number}>}
 */
export function validate({ mergedText, sections = [], versionA, versionB }) {
  const findings = [];

  if (!versionA && (versionB || mergedText.trim())) {
    findings.push({
      category: "missing-version",
      severity: "warning",
      message:
        "Couldn't detect a Betaflight version in CLI A's header — key-drift check is disabled.",
    });
  }

  if (versionA && versionB && versionA !== versionB) {
    findings.push({
      category: "version-mismatch",
      severity: "info",
      message:
        `CLI A is ${versionA} and CLI B is ${versionB}. Keys that only exist in B may not be recognized by A's firmware.`,
    });
  }

  const { keysA, keysB } = keySetsFor(sections);

  const lines = mergedText.split("\n");
  const seenKeys = new Map(); // key -> first line index

  for (let i = 0; i < lines.length; i++) {
    const trimmed = lines[i].trim();
    // Match only the `set` command itself — `set<whitespace>...` — so words
    // like `settings`, `setpoint`, `setup` don't fall into malformed-set.
    if (!/^set\s/.test(trimmed)) continue;

    // Malformed: missing "=" or empty value.
    const setMatch = /^set\s+(\S+)\s*=\s*(.*)$/.exec(trimmed);
    if (!setMatch) {
      findings.push({
        category: "malformed-set",
        severity: "error",
        message: `Malformed set line: "${trimmed}"`,
        line: i + 1,
      });
      continue;
    }
    const [, key, value] = setMatch;
    if (!value.trim()) {
      findings.push({
        category: "malformed-set",
        severity: "error",
        message: `Empty value for "${key}".`,
        key,
        line: i + 1,
      });
      continue;
    }

    // Duplicate key check.
    if (seenKeys.has(key)) {
      findings.push({
        category: "duplicate-key",
        severity: "error",
        message: `"${key}" is set more than once (first at line ${seenKeys.get(key) + 1}).`,
        key,
        line: i + 1,
      });
    } else {
      seenKeys.set(key, i);
    }

    // Key-drift heuristic: key came from B but A's firmware doesn't know it.
    if (versionA && !keysA.has(key) && keysB.has(key)) {
      findings.push({
        category: "unknown-key",
        severity: "warning",
        message:
          `"${key}" appears only in CLI B — CLI A (${versionA}) may not recognize it.`,
        key,
        line: i + 1,
      });
    }
  }

  // Missing save terminator.
  const hasSave = lines.some((l) => l.trim() === "save");
  if (mergedText.trim() && !hasSave) {
    findings.push({
      category: "missing-save",
      severity: "warning",
      message: "No `save` terminator — Betaflight won't persist these settings.",
    });
  }

  return findings;
}
