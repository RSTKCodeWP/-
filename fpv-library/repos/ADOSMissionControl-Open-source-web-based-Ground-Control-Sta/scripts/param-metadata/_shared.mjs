/**
 * Shared helpers for the parameter-metadata generators.
 *
 * The generators are maintainer-run tools that produce the bundled snapshots
 * under `public/param-metadata/` (the instant, offline floor) and the hosted
 * registry blobs. Output is committed; builds never fetch.
 *
 * @license GPL-3.0-only
 */

import { writeFile, mkdir } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import https from "node:https";
import { gunzipSync, gzipSync } from "node:zlib";

export const PUBLIC_DIR = resolve(process.cwd(), "public", "param-metadata");

/** HTTPS GET returning a Buffer (transparently gunzips .xz is NOT handled here). */
export function httpsGetBuffer(url) {
  return new Promise((res, rej) => {
    https.get(url, { headers: { "Accept-Encoding": "gzip" } }, (r) => {
      if (r.statusCode && r.statusCode >= 300 && r.statusCode < 400 && r.headers.location) {
        return httpsGetBuffer(r.headers.location).then(res, rej);
      }
      if (r.statusCode !== 200) return rej(new Error(`GET ${url} → ${r.statusCode}`));
      const chunks = [];
      r.on("data", (c) => chunks.push(c));
      r.on("end", () => {
        let buf = Buffer.concat(chunks);
        if (r.headers["content-encoding"] === "gzip") {
          try { buf = gunzipSync(buf); } catch { /* not gzipped */ }
        }
        res(buf);
      });
    }).on("error", rej);
  });
}

export async function httpsGetJson(url) {
  return JSON.parse((await httpsGetBuffer(url)).toString("utf8"));
}

/** Trim a long description to its first sentence (≤240 chars) for tooltips. */
export function trimDescription(d) {
  if (!d) return d;
  const m = d.match(/^(.+?[.!?])(\s|$)/);
  let s = m && m[1].length <= 240 ? m[1] : d;
  if (s.length > 240) s = s.slice(0, 239).trimEnd() + "…";
  return s;
}

/** Convert a `{ "0": "label", "0.1": "label" }` object to number-keyed entries.
 *  Codes are parsed as floats so non-integer enum codes are not collapsed. */
export function codeLabelEntries(obj, intOnly = false) {
  if (!obj || typeof obj !== "object") return undefined;
  const out = [];
  for (const [k, v] of Object.entries(obj)) {
    const n = intOnly ? parseInt(k, 10) : parseFloat(k);
    if (!Number.isNaN(n)) out.push([n, String(v)]);
  }
  return out.length ? out : undefined;
}

/** Strip undefined-valued keys so the JSON stays compact. */
export function compact(obj) {
  const out = {};
  for (const [k, v] of Object.entries(obj)) if (v !== undefined) out[k] = v;
  return out;
}

/**
 * Write a gzipped snapshot file ({ provenance, params }) after asserting a
 * minimum param count, so an upstream format change can never silently
 * overwrite a good snapshot with an empty one. `outPath` should end in
 * `.json.gz`; the runtime inflates it with pako.
 */
export async function writeSnapshot(outPath, provenance, params, minCount) {
  if (params.length < minCount) {
    throw new Error(`refusing to write ${outPath}: ${params.length} params < min ${minCount}`);
  }
  const snapshot = {
    provenance: { ...provenance, paramCount: params.length },
    params,
  };
  await mkdir(dirname(outPath), { recursive: true });
  await writeFile(outPath, gzipSync(Buffer.from(JSON.stringify(snapshot)), { level: 9 }));
  return params.length;
}

/** Read + parse a gzipped snapshot written by writeSnapshot (for verification). */
export function gunzipJson(buf) {
  return JSON.parse(gunzipSync(buf).toString("utf8"));
}
