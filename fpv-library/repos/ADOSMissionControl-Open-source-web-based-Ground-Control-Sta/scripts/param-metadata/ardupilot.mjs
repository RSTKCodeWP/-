/**
 * Generate the bundled ArduPilot parameter metadata snapshots.
 *
 * Produces `public/param-metadata/ardupilot-{copter,plane,rover,sub}.json` from
 * the public ArduPilot parameter definitions. Run on demand to refresh the
 * floor:  `node scripts/param-metadata/ardupilot.mjs`
 *
 * @license GPL-3.0-only
 */

import { join } from "node:path";
import {
  PUBLIC_DIR, httpsGetJson, trimDescription, codeLabelEntries, compact, writeSnapshot,
} from "./_shared.mjs";

const BASE = "https://autotest.ardupilot.org/Parameters";
const VEHICLES = [
  { vehicle: "ArduCopter", file: "ardupilot-copter", min: 800 },
  { vehicle: "ArduPlane",  file: "ardupilot-plane",  min: 800 },
  { vehicle: "Rover",      file: "ardupilot-rover",  min: 600 },
  { vehicle: "ArduSub",    file: "ardupilot-sub",    min: 600 },
];

function toMeta(name, p) {
  const range = p.Range && p.Range.low !== undefined
    ? { min: parseFloat(p.Range.low), max: parseFloat(p.Range.high) }
    : undefined;
  const increment = p.Increment !== undefined ? parseFloat(p.Increment) : undefined;
  return compact({
    name,
    humanName: p.DisplayName ?? "",
    description: trimDescription(p.Description ?? ""),
    range: range && !Number.isNaN(range.min) && !Number.isNaN(range.max) ? range : undefined,
    units: p.Units || undefined,
    values: codeLabelEntries(p.Values),
    bitmask: codeLabelEntries(p.Bitmask, true),
    increment: increment !== undefined && !Number.isNaN(increment) ? increment : undefined,
    rebootRequired: p.RebootRequired === "True" ? true : undefined,
    readOnly: p.ReadOnly === "True" ? true : undefined,
    volatile: p.Volatile === "True" ? true : undefined,
    calibration: p.Calibration === "True" ? true : undefined,
    advanced: p.User === "Advanced" ? true : (p.User === "Standard" ? false : undefined),
  });
}

async function generate({ vehicle, file, min }) {
  const url = `${BASE}/${vehicle}/apm.pdef.json`;
  const j = await httpsGetJson(url);
  const byName = new Map();
  for (const group of Object.keys(j)) {
    const grp = j[group];
    if (!grp || typeof grp !== "object") continue;
    for (const name of Object.keys(grp)) {
      const p = grp[name];
      if (!p || typeof p !== "object" || (!p.Description && !p.DisplayName)) continue;
      // Dedup by name; prefer the entry that carries enum/bitmask labels.
      const prev = byName.get(name);
      const meta = toMeta(name, p);
      if (!prev || (!prev.values && !prev.bitmask && (meta.values || meta.bitmask))) {
        byName.set(name, meta);
      }
    }
  }
  const params = [...byName.values()].sort((a, b) => a.name.localeCompare(b.name));
  const count = await writeSnapshot(
    join(PUBLIC_DIR, `${file}.json.gz`),
    { firmware: file, version: "latest", sourceUrl: url, generatedAt: new Date().toISOString() },
    params,
    min,
  );
  console.log(`${file}: ${count} params`);
}

for (const v of VEHICLES) {
  await generate(v);
}
