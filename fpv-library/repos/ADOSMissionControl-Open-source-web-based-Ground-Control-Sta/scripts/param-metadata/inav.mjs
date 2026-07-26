/**
 * Generate the bundled iNav parameter metadata (full named-settings registry).
 *
 * Sources iNav's `src/main/fc/settings.yaml` (the authoritative setting list:
 * enum tables + per-setting type/range/description) for all ~677 named settings,
 * keyed by lowercase setting name to match the live MSP enumeration, PLUS the
 * curated virtual-param entries (FEATURE_FLAGS / FAILSAFE_PROCEDURE / DISARM)
 * used when the MSP enumeration falls back to the legacy virtual-param list.
 * Run:  node scripts/param-metadata/inav.mjs
 *
 * @license GPL-3.0-only
 */

import { join } from "node:path";
import { parse as parseYaml } from "yaml";
import { PUBLIC_DIR, httpsGetBuffer, trimDescription, compact, writeSnapshot } from "./_shared.mjs";

const RAW = "https://raw.githubusercontent.com/iNavFlight/inav/master/src/main";
const text = async (path) => (await httpsGetBuffer(`${RAW}/${path}`)).toString("utf8");

const TYPE_MAP = {
  uint8_t: "uint8", int8_t: "int8", uint16_t: "uint16", int16_t: "int16",
  uint32_t: "uint32", float: "float", string: "string", bool: "bool",
};
const ON_OFF = [[0, "OFF"], [1, "ON"]];

/** Parse a numeric literal; undefined for symbolic macros / non-numbers. */
function numOrNull(v) {
  if (v === undefined || v === null) return undefined;
  if (typeof v === "number") return Number.isFinite(v) ? v : undefined;
  const s = String(v).trim();
  if (!/^-?\d+(\.\d+)?$/.test(s)) return undefined;
  const n = Number(s);
  return Number.isFinite(n) ? n : undefined;
}

// ── Full named-settings registry from settings.yaml ──
const doc = parseYaml(await text("fc/settings.yaml"), { uniqueKeys: false, strict: false });
const tables = new Map();
for (const t of doc.tables ?? []) {
  if (t?.name && Array.isArray(t.values)) {
    tables.set(t.name, t.values.map((label, i) => [i, String(label)]));
  }
}

const params = [];
for (const group of doc.groups ?? []) {
  for (const m of group.members ?? []) {
    if (!m?.name) continue;
    const valueType = TYPE_MAP[String(m.type ?? "").trim()] || undefined;
    let values;
    if (m.table && tables.has(m.table)) values = tables.get(m.table);
    else if (valueType === "bool") values = ON_OFF;
    const min = numOrNull(m.min);
    const max = numOrNull(m.max);
    const range = min !== undefined && max !== undefined ? { min, max } : undefined;
    // default_value: a literal number, or an enum-table label → its index.
    let defaultValue = numOrNull(m.default_value);
    if (defaultValue === undefined && values && m.default_value !== undefined) {
      const hit = values.find(([, label]) => label === String(m.default_value));
      if (hit) defaultValue = hit[0];
    }
    params.push(compact({
      name: m.name,
      humanName: "",
      description: trimDescription(String(m.description ?? "")),
      range,
      values: values && values.length ? values : undefined,
      defaultValue,
      valueType,
    }));
  }
}

// ── Curated virtual-param entries (fallback path) ──
const cli = await text("fc/cli.c");
const fm = cli.match(/featureNames\[\][^=]*=\s*\{([\s\S]*?)\}/);
const featureBits = fm
  ? fm[1].split(",").map((s) => s.trim().replace(/^"|"$/g, ""))
      .map((label, bit) => [bit, label]).filter(([, l]) => l && l !== "NULL" && l !== "")
  : undefined;
const failsafe = tables.get("failsafe_procedure");

if (featureBits?.length) {
  params.push(compact({ name: "FEATURE_FLAGS", humanName: "Features", description: "Enabled firmware features (bitmask).", bitmask: featureBits, valueType: "uint32" }));
}
if (failsafe) {
  params.push(compact({ name: "FAILSAFE_PROCEDURE", humanName: "Failsafe Procedure", description: "Action taken when the failsafe triggers.", values: failsafe, valueType: "uint8" }));
}
params.push(compact({ name: "DISARM_KILL_SWITCH", humanName: "Disarm Kill Switch", description: "Instantly disarm on the arm switch regardless of throttle.", values: ON_OFF, valueType: "uint8" }));

params.sort((a, b) => a.name.localeCompare(b.name));
const count = await writeSnapshot(
  join(PUBLIC_DIR, "inav.json.gz"),
  { firmware: "inav", version: "latest", sourceUrl: "iNav firmware settings.yaml", generatedAt: new Date().toISOString() },
  params,
  300,
);
console.log(`inav: ${count} params (${tables.size} enum tables)`);
