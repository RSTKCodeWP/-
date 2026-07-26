/**
 * Generate the bundled PX4 parameter metadata snapshot.
 *
 * Produces `public/param-metadata/px4.json.gz` from the PX4 parameter
 * definitions (parameters.json). Run on demand to refresh the floor:
 *   node scripts/param-metadata/px4.mjs
 *
 * @license GPL-3.0-only
 */

import { join } from "node:path";
import { PUBLIC_DIR, httpsGetJson, trimDescription, compact, writeSnapshot } from "./_shared.mjs";

// Pinned to a stable PX4 release that publishes the board-agnostic definitions.
const TAG = "v1.16.2";
const URL = `https://px4-travis.s3.amazonaws.com/Firmware/${TAG}/_general/parameters.json`;

const TYPE_MAP = {
  int8: "int8", uint8: "uint8", int16: "int16", uint16: "uint16",
  int32: "int32", uint32: "uint32", float: "float",
};

function toMeta(p) {
  const range = p.min !== undefined && p.max !== undefined ? { min: p.min, max: p.max } : undefined;
  const values = Array.isArray(p.values)
    ? p.values.filter((v) => v.value !== undefined).map((v) => [v.value, String(v.description ?? "")])
    : undefined;
  const bitmask = Array.isArray(p.bitmask)
    ? p.bitmask.filter((b) => b.index !== undefined).map((b) => [b.index, String(b.description ?? "")])
    : undefined;
  return compact({
    name: p.name,
    humanName: p.shortDesc ?? "",
    description: trimDescription(p.longDesc ?? p.shortDesc ?? ""),
    range,
    units: p.units || undefined,
    values: values && values.length ? values : undefined,
    bitmask: bitmask && bitmask.length ? bitmask : undefined,
    increment: p.increment !== undefined ? p.increment : undefined,
    defaultValue: p.default !== undefined ? p.default : undefined,
    rebootRequired: p.rebootRequired === true ? true : undefined,
    volatile: p.volatile === true ? true : undefined,
    decimalPlaces: p.decimalPlaces !== undefined ? p.decimalPlaces : undefined,
    valueType: p.type ? TYPE_MAP[String(p.type).toLowerCase()] : undefined,
    category: p.category || undefined,
    group: p.group || undefined,
  });
}

const j = await httpsGetJson(URL);
const params = (j.parameters ?? [])
  .filter((p) => p && p.name)
  .map(toMeta)
  .sort((a, b) => a.name.localeCompare(b.name));

const count = await writeSnapshot(
  join(PUBLIC_DIR, "px4.json.gz"),
  { firmware: "px4", version: TAG.replace(/^v/, ""), sourceUrl: URL, generatedAt: new Date().toISOString() },
  params,
  1000,
);
console.log(`px4: ${count} params`);
