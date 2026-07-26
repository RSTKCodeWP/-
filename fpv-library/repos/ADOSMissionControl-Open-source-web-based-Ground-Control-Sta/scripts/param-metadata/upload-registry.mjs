/**
 * Seed the hosted parameter registry (Convex param_registry) from the bundled
 * snapshots + per-version generation. Run after `npx convex deploy`:
 *   node scripts/param-metadata/upload-registry.mjs
 *
 * Uploads the committed "latest" snapshots (every firmware) plus per-version
 * snapshots (PX4 per release tag — the version-matching proof). Each snapshot is
 * the gzipped {provenance,params} blob, base64-encoded, written via the
 * `paramRegistry:upsertSnapshot` internal mutation through the Convex CLI.
 *
 * @license GPL-3.0-only
 */

import { readFileSync, readdirSync } from "node:fs";
import { execFileSync } from "node:child_process";
import { join, resolve } from "node:path";
import { gzipSync, gunzipSync } from "node:zlib";
import { PUBLIC_DIR, httpsGetJson, httpsGetBuffer, trimDescription, compact } from "./_shared.mjs";
import { parsePdefXml } from "./_pdef-xml.mjs";

const WEBSITE = resolve(process.cwd(), "..", "website");
const text = async (url) => (await httpsGetBuffer(url)).toString("utf8");

function upsert(firmware, version, paramCount, gzBuf) {
  const args = JSON.stringify({ firmware, version, paramCount, gzB64: gzBuf.toString("base64") });
  execFileSync("npx", ["convex", "run", "paramRegistry:upsertSnapshot", args], {
    cwd: WEBSITE,
    stdio: ["ignore", "inherit", "inherit"],
  });
  console.log(`seeded ${firmware}@${version} (${paramCount} params, ${Math.round(gzBuf.length / 1024)} KB)`);
}

// ── "latest" snapshots (every committed bundled firmware) ──
for (const f of readdirSync(PUBLIC_DIR)) {
  if (!f.endsWith(".json.gz")) continue;
  const firmware = f.replace(".json.gz", "");
  const buf = readFileSync(join(PUBLIC_DIR, f));
  const snap = JSON.parse(gunzipSync(buf).toString("utf8"));
  upsert(firmware, "latest", snap.provenance.paramCount, buf);
}

// ── PX4 per-version (the version-matching proof) ──
const PX4_TYPE = { int8: "int8", uint8: "uint8", int16: "int16", uint16: "uint16", int32: "int32", uint32: "uint32", float: "float" };
function px4Meta(p) {
  const range = p.min !== undefined && p.max !== undefined ? { min: p.min, max: p.max } : undefined;
  const values = Array.isArray(p.values) ? p.values.filter((v) => v.value !== undefined).map((v) => [v.value, String(v.description ?? "")]) : undefined;
  const bitmask = Array.isArray(p.bitmask) ? p.bitmask.filter((b) => b.index !== undefined).map((b) => [b.index, String(b.description ?? "")]) : undefined;
  return compact({
    name: p.name, humanName: p.shortDesc ?? "", description: trimDescription(p.longDesc ?? p.shortDesc ?? ""),
    range, units: p.units || undefined,
    values: values && values.length ? values : undefined, bitmask: bitmask && bitmask.length ? bitmask : undefined,
    increment: p.increment, defaultValue: p.default, rebootRequired: p.rebootRequired === true ? true : undefined,
    volatile: p.volatile === true ? true : undefined, decimalPlaces: p.decimalPlaces,
    valueType: p.type ? PX4_TYPE[String(p.type).toLowerCase()] : undefined, category: p.category || undefined, group: p.group || undefined,
  });
}
for (const tag of ["v1.16.2", "v1.17.0"]) {
  const url = `https://px4-travis.s3.amazonaws.com/Firmware/${tag}/_general/parameters.json`;
  const j = await httpsGetJson(url);
  const params = (j.parameters ?? []).filter((p) => p && p.name).map(px4Meta).sort((a, b) => a.name.localeCompare(b.name));
  const snapshot = { provenance: { firmware: "px4", version: tag.replace(/^v/, ""), sourceUrl: url, paramCount: params.length }, params };
  const gz = gzipSync(Buffer.from(JSON.stringify(snapshot)), { level: 9 });
  upsert("px4", tag.replace(/^v/, "").replace(/\.\d+$/, ""), params.length, gz);
}

// ── ArduPilot per-version (versioned apm.pdef.xml tree) ──
const AP_VEHICLES = [
  ["Copter", "ardupilot-copter"], ["Plane", "ardupilot-plane"],
  ["Rover", "ardupilot-rover"], ["Sub", "ardupilot-sub"],
];
const WANT_MINORS = ["4.3", "4.4", "4.5", "4.6"];
for (const [dir, firmware] of AP_VEHICLES) {
  let listing;
  try { listing = await text(`https://autotest.ardupilot.org/Parameters/versioned/${dir}/`); }
  catch { console.log(`${firmware}: no versioned listing`); continue; }
  // Pick the latest patch of each wanted minor.
  const byMinor = new Map();
  for (const mm of listing.matchAll(/stable-(\d+)\.(\d+)\.(\d+)/g)) {
    const key = `${mm[1]}.${mm[2]}`;
    if (!WANT_MINORS.includes(key)) continue;
    const pat = Number(mm[3]);
    const prev = byMinor.get(key);
    if (!prev || pat > prev.pat) byMinor.set(key, { pat, full: `${mm[1]}.${mm[2]}.${mm[3]}` });
  }
  for (const [minor, { full }] of [...byMinor].sort()) {
    const url = `https://autotest.ardupilot.org/Parameters/versioned/${dir}/stable-${full}/apm.pdef.xml`;
    let params;
    try { params = parsePdefXml(await text(url)); }
    catch { console.log(`  ${firmware}@${minor}: fetch/parse failed`); continue; }
    if (params.length < 500) { console.log(`  ${firmware}@${minor}: only ${params.length} params, skipping`); continue; }
    params.sort((a, b) => a.name.localeCompare(b.name));
    const snapshot = { provenance: { firmware, version: minor, sourceUrl: url, paramCount: params.length }, params };
    upsert(firmware, minor, params.length, gzipSync(Buffer.from(JSON.stringify(snapshot)), { level: 9 }));
  }
}

console.log("done");
