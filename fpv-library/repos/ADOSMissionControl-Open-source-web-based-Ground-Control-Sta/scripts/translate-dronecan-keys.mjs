#!/usr/bin/env node
/**
 * Batch-translate DroneCAN UI strings across the 15 non-English locale
 * files using the Anthropic API. Operates on a fixed namespace whitelist
 * so we never touch unrelated keys.
 *
 * The script is idempotent: a key is only translated when the locale value
 * is byte-identical to the English source (i.e. it is still a placeholder
 * left by `scripts/i18n-merge-missing.mjs`). Already-translated keys are
 * untouched. Missing keys are filled and translated in the same pass.
 *
 * Requirements:
 *   - `ANTHROPIC_API_KEY` env var, or `~/.config/anthropic/key` file.
 *   - `@anthropic-ai/sdk` installed as a dev dependency.
 *
 * If the API key is unavailable the script logs a clear message and exits
 * without modifying any locale file. The script can still be committed
 * to the repo in this state for a later run.
 *
 * Usage:
 *   node scripts/translate-dronecan-keys.mjs                # all locales
 *   node scripts/translate-dronecan-keys.mjs de fr es       # subset
 *   node scripts/translate-dronecan-keys.mjs --dry-run      # no API calls
 *
 * License: GPL-3.0-only
 */

import { readFileSync, writeFileSync, existsSync } from "node:fs";
import { resolve, dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { homedir } from "node:os";

const here = dirname(fileURLToPath(import.meta.url));
const root = resolve(here, "..");
const localesDir = join(root, "locales");

const TARGET_NAMESPACES = [
  "canConfig",
  "configNav.canConfig",
  "flashTool.apPeriph",
  "flashTool.ados.apPeriph",
];

const LOCALES = [
  "de", "fr", "es", "ja", "zh",
  "ko", "pt", "hi", "kn", "ta",
  "te", "mr", "pa", "gu", "id",
];

const LOCALE_NAMES = {
  de: "German",
  fr: "French",
  es: "Spanish",
  ja: "Japanese",
  zh: "Simplified Chinese",
  ko: "Korean",
  pt: "Portuguese (Brazil)",
  hi: "Hindi",
  kn: "Kannada",
  ta: "Tamil",
  te: "Telugu",
  mr: "Marathi",
  pa: "Punjabi (Gurmukhi)",
  gu: "Gujarati",
  id: "Indonesian",
};

const DO_NOT_TRANSLATE_EXACT = new Set([
  "DroneCAN", "MAVLink", "CAN1", "CAN2", "SLCAN", "MSP", "GPS", "ESC", "IMU",
  "UART", "USB", "VCP", "AP_Periph", "FLASH_BOOTLOADER",
  "OPERATIONAL", "MAINTENANCE", "INITIALIZATION", "SOFTWARE_UPDATE", "OFFLINE",
  "NodeStatus", "GetNodeInfo",
  "Mbit/s", "kbit/s", "kbps", "Mbps", "ms", "µs", "us", "dBm", "Hz", "fps",
  "RTT", "BEL", "CRC", "DSDL", "OTA", "RPC",
  "RX", "TX", "ACK", "NACK", "PWM", "I2C", "SPI", "ADC", "DAC",
  "AHRS", "EKF", "PID", "RTK", "SBAS", "BeiDou", "GLONASS", "Galileo",
]);

const DO_NOT_TRANSLATE_PATTERNS = [
  /\bCAN_[A-Z0-9_]+\b/g,
  /\bGPS_[A-Z0-9_]+\b/g,
  /\bBATT_[A-Z0-9_]+\b/g,
  /\bUAVCAN_[A-Z0-9_]+\b/g,
];

// Word stems that suggest a translation may have leaked English content.
// These are common English connectives that should never survive in a
// Hindi / Tamil / Telugu / Marathi / Punjabi / Gujarati / Kannada string.
const ENGLISH_LEAK_HINTS = [
  " the ", " with ", " from ", " and ", " for ", " this ", " that ",
  " between ", " using ", " when ", " while ",
];

const PRIMARY_MODEL = "claude-haiku-4-5-20251001";
const FALLBACK_MODEL = "claude-sonnet-4-6";

const args = process.argv.slice(2);
const dryRun = args.includes("--dry-run");
const requested = args.filter((a) => !a.startsWith("--"));
const targetLocales = requested.length > 0
  ? requested.filter((l) => LOCALES.includes(l))
  : LOCALES;

function loadApiKey() {
  const fromEnv = process.env.ANTHROPIC_API_KEY;
  if (fromEnv && fromEnv.trim()) return fromEnv.trim();
  const keyPath = join(homedir(), ".config", "anthropic", "key");
  if (existsSync(keyPath)) {
    const fromFile = readFileSync(keyPath, "utf8").trim();
    if (fromFile) return fromFile;
  }
  return null;
}

function readJson(path) {
  return JSON.parse(readFileSync(path, "utf8"));
}

function writeJson(path, obj) {
  writeFileSync(path, JSON.stringify(obj, null, 2) + "\n");
}

function getPath(obj, path) {
  if (!path) return obj;
  return path.split(".").reduce(
    (o, k) => (o && typeof o === "object" && k in o) ? o[k] : undefined,
    obj,
  );
}

function setPath(obj, path, value) {
  const parts = path.split(".");
  let cur = obj;
  for (let i = 0; i < parts.length - 1; i++) {
    const p = parts[i];
    if (typeof cur[p] !== "object" || cur[p] === null) cur[p] = {};
    cur = cur[p];
  }
  cur[parts[parts.length - 1]] = value;
}

function flatten(obj, prefix, acc) {
  if (typeof obj === "string") {
    acc[prefix] = obj;
    return;
  }
  if (typeof obj === "object" && obj !== null) {
    for (const k of Object.keys(obj)) {
      flatten(obj[k], prefix ? `${prefix}.${k}` : k, acc);
    }
  }
}

function collectPlaceholders(en, locale) {
  const out = {};
  for (const ns of TARGET_NAMESPACES) {
    const enSub = getPath(en, ns);
    const locSub = getPath(locale, ns);
    if (enSub === undefined) continue;
    const enFlat = {};
    flatten(enSub, "", enFlat);
    for (const [suffix, enValue] of Object.entries(enFlat)) {
      const fullPath = suffix ? `${ns}.${suffix}` : ns;
      const locValue = suffix ? getPath(locSub, suffix) : locSub;
      // Translate when the locale value is missing or byte-identical to en.
      if (locValue === undefined || locValue === enValue) {
        out[fullPath] = enValue;
      }
    }
  }
  return out;
}

function buildSystemPrompt(localeCode) {
  const name = LOCALE_NAMES[localeCode];
  return [
    `You are a professional UI translator working on a ground control station for autonomous drones.`,
    `Translate UI strings from English to ${name}.`,
    ``,
    `Rules:`,
    `1. Keep technical terms, acronyms, and protocol names in English exactly as given.`,
    `   Examples to keep verbatim: DroneCAN, MAVLink, CAN1, CAN2, SLCAN, MSP, GPS, ESC, IMU,`,
    `   UART, USB, VCP, AP_Periph, FLASH_BOOTLOADER, OPERATIONAL, MAINTENANCE,`,
    `   INITIALIZATION, SOFTWARE_UPDATE, OFFLINE, NodeStatus, GetNodeInfo,`,
    `   any parameter name matching CAN_*, GPS_*, BATT_*, UAVCAN_*,`,
    `   units like Mbit/s, kbit/s, kbps, Mbps, ms, µs, dBm, Hz, fps,`,
    `   acronyms RTT, BEL, CRC, DSDL, OTA, RPC, RX, TX, ACK, NACK, PWM,`,
    `   GNSS constellation names BeiDou, GLONASS, Galileo, SBAS, RTK.`,
    `2. Translate the surrounding natural-language text into ${name}.`,
    `3. Preserve placeholders like {count}, {value}, {name} exactly.`,
    `4. Preserve numeric values and punctuation.`,
    `5. Keep translations concise and suitable for a desktop UI (buttons, labels, help text).`,
    `6. Do not invent content. If a string is already in ${name} or contains only`,
    `   technical terms, return it unchanged.`,
    ``,
    `Output format:`,
    `- Return ONE JSON object only. No prose, no markdown fences, no commentary.`,
    `- Keys must exactly match the input keys.`,
    `- Values must be the translated strings.`,
  ].join("\n");
}

function estimateBudget(keyCounts) {
  // Rough USD estimate: Haiku 4.5 input ~$1/Mtok, output ~$5/Mtok.
  // Average ~6 tokens/key for input, ~8 tokens/key for output.
  const total = Object.values(keyCounts).reduce((a, b) => a + b, 0);
  const inTokens = total * 6;
  const outTokens = total * 8;
  const cost = (inTokens / 1_000_000) * 1.0 + (outTokens / 1_000_000) * 5.0;
  return { total, cost };
}

function looksLikeEnglishLeak(value, english) {
  const lower = ` ${value.toLowerCase()} `;
  for (const hint of ENGLISH_LEAK_HINTS) {
    if (lower.includes(hint) && !english.toLowerCase().includes(hint.trim())) {
      // hint connector appeared in translated value but not in source -> suspicious
      return hint.trim();
    }
  }
  return null;
}

async function translateBatch(client, model, localeCode, payload) {
  const userContent = JSON.stringify(payload, null, 2);
  const resp = await client.messages.create({
    model,
    max_tokens: 4096,
    system: buildSystemPrompt(localeCode),
    messages: [{ role: "user", content: userContent }],
  });
  const text = resp.content
    .filter((b) => b.type === "text")
    .map((b) => b.text)
    .join("")
    .trim();
  // Strip accidental code fences just in case.
  const cleaned = text
    .replace(/^```(?:json)?\s*/i, "")
    .replace(/\s*```\s*$/i, "")
    .trim();
  let parsed;
  try {
    parsed = JSON.parse(cleaned);
  } catch (err) {
    throw new Error(`JSON parse failed for ${localeCode} on ${model}: ${err.message}`);
  }
  if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed)) {
    throw new Error(`Expected object response for ${localeCode}, got ${typeof parsed}`);
  }
  return parsed;
}

function validateResponse(input, output, localeCode) {
  const issues = [];
  for (const key of Object.keys(input)) {
    if (!(key in output)) {
      issues.push(`missing key: ${key}`);
      continue;
    }
    const v = output[key];
    if (typeof v !== "string" || v.length === 0) {
      issues.push(`empty/non-string value: ${key}`);
      continue;
    }
    // Latin-script locales (de, fr, es, pt, id) legitimately contain English
    // connectives. Skip leak detection for those.
    const isLatin = ["de", "fr", "es", "pt", "id"].includes(localeCode);
    if (!isLatin) {
      const leak = looksLikeEnglishLeak(v, input[key]);
      if (leak) issues.push(`possible English leak (${leak}) in: ${key}`);
    }
  }
  return issues;
}

async function processLocale(client, en, localeCode) {
  const path = join(localesDir, `${localeCode}.json`);
  const locale = readJson(path);
  const placeholders = collectPlaceholders(en, locale);
  const keyCount = Object.keys(placeholders).length;
  if (keyCount === 0) {
    return { localeCode, keyCount: 0, status: "skipped-empty" };
  }
  if (dryRun || !client) {
    return { localeCode, keyCount, status: "dry-run" };
  }
  let translations;
  try {
    translations = await translateBatch(client, PRIMARY_MODEL, localeCode, placeholders);
  } catch (err) {
    console.warn(`  [${localeCode}] primary model failed: ${err.message}; retrying with fallback`);
    translations = await translateBatch(client, FALLBACK_MODEL, localeCode, placeholders);
  }
  const issues = validateResponse(placeholders, translations, localeCode);
  if (issues.length > 0) {
    console.warn(`  [${localeCode}] validation warnings (${issues.length}):`);
    for (const i of issues.slice(0, 5)) console.warn(`    - ${i}`);
  }
  // Merge translations back. Only write keys that came back as valid strings.
  let written = 0;
  for (const [key, value] of Object.entries(translations)) {
    if (typeof value !== "string" || value.length === 0) continue;
    if (!(key in placeholders)) continue; // ignore stray keys
    setPath(locale, key, value);
    written++;
  }
  writeJson(path, locale);
  return { localeCode, keyCount, written, status: "ok" };
}

async function main() {
  const en = readJson(join(localesDir, "en.json"));

  // Survey per-locale workload before any API calls.
  const counts = {};
  for (const code of targetLocales) {
    const locale = readJson(join(localesDir, `${code}.json`));
    counts[code] = Object.keys(collectPlaceholders(en, locale)).length;
  }
  const { total, cost } = estimateBudget(counts);
  console.log("DroneCAN translation pass");
  console.log("=========================");
  for (const code of targetLocales) {
    console.log(`  ${code.padEnd(4)} placeholder keys: ${counts[code]}`);
  }
  console.log(`  total keys: ${total}`);
  console.log(`  budget estimate: ~$${cost.toFixed(2)} (Haiku 4.5)`);
  console.log("");

  const apiKey = loadApiKey();
  if (!apiKey) {
    console.log("ANTHROPIC_API_KEY not set and ~/.config/anthropic/key missing.");
    console.log("Skipping LLM translation. Script committed to repo; run later with");
    console.log("  ANTHROPIC_API_KEY=sk-... node scripts/translate-dronecan-keys.mjs");
    process.exit(0);
  }

  if (dryRun) {
    console.log("--dry-run set, exiting without API calls");
    process.exit(0);
  }

  let Anthropic;
  try {
    ({ default: Anthropic } = await import("@anthropic-ai/sdk"));
  } catch (err) {
    console.error("Failed to import @anthropic-ai/sdk:", err.message);
    console.error("Install with: npm install --save-dev @anthropic-ai/sdk");
    process.exit(1);
  }
  const client = new Anthropic({ apiKey });

  const results = [];
  for (const code of targetLocales) {
    process.stdout.write(`Translating ${code} (${counts[code]} keys)... `);
    try {
      const r = await processLocale(client, en, code);
      results.push(r);
      console.log(r.status === "ok" ? `wrote ${r.written}/${r.keyCount}` : r.status);
    } catch (err) {
      results.push({ localeCode: code, keyCount: counts[code], status: "error", error: err.message });
      console.log(`FAILED (${err.message})`);
    }
  }

  console.log("");
  console.log("Summary");
  console.log("-------");
  for (const r of results) {
    const w = r.written !== undefined ? ` wrote=${r.written}` : "";
    const e = r.error ? ` error=${r.error}` : "";
    console.log(`  ${r.localeCode.padEnd(4)} keys=${r.keyCount} status=${r.status}${w}${e}`);
  }
}

main().catch((err) => {
  console.error("Fatal:", err);
  process.exit(1);
});
