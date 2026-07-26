/**
 * Generate the bundled EGM96 geoid-undulation snapshot.
 *
 * Produces `public/geoid/egm96-1deg.i16.gz` from the NGA/NASA EGM96
 * 15-arc-minute gridded geoid heights (`WW15MGH.GRD`, public domain). The
 * source 721x1441 grid (0.25 deg) is subsampled to a 361x181 (1 deg) grid,
 * quantized to Int16 centimetres (row-major, corner origin at +90 deg / 0 deg
 * longitude, latitude decreasing per row, longitude increasing per column),
 * and gzipped.
 *
 * Download WW15MGH.GRD first (see scripts/geoid/README.md), then run:
 *   node scripts/geoid/generate.mjs [path/to/WW15MGH.GRD]
 *
 * @license GPL-3.0-only
 */

import { readFileSync, writeFileSync, mkdirSync, existsSync } from "node:fs";
import { gzipSync } from "node:zlib";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = join(__dirname, "..", "..");
const OUT_DIR = join(REPO_ROOT, "public", "geoid");
const OUT_FILE = join(OUT_DIR, "egm96-1deg.i16.gz");

// Output grid geometry (1 deg). 361 columns (0..360 deg inclusive) x 181 rows
// (+90..-90 deg inclusive). MUST match GRID_LEN / NCOLS / NROWS in geoid.ts.
const OUT_NCOLS = 361;
const OUT_NROWS = 181;

// Locate the source grid: argv[2], else common local drop paths.
function resolveSource() {
  const candidates = [
    process.argv[2],
    join(__dirname, "WW15MGH.GRD"),
    join(REPO_ROOT, "WW15MGH.GRD"),
  ].filter(Boolean);
  for (const c of candidates) {
    if (existsSync(c)) return c;
  }
  return null;
}

const src = resolveSource();
if (!src) {
  console.error(
    "WW15MGH.GRD not found. Download it (see scripts/geoid/README.md) and pass\n" +
      "its path:  node scripts/geoid/generate.mjs path/to/WW15MGH.GRD"
  );
  process.exit(1);
}

const text = readFileSync(src, "utf8");
const lines = text.split("\n");

// Header: south north west east dlat dlon.
const header = lines[0].trim().split(/\s+/).map(Number);
const [south, north, west, east, dlat, dlon] = header;
if (![south, north, west, east, dlat, dlon].every(Number.isFinite)) {
  console.error("Malformed WW15MGH.GRD header:", lines[0]);
  process.exit(1);
}

const srcRows = Math.round((north - south) / dlat) + 1; // 721
const srcCols = Math.round((east - west) / dlon) + 1; // 1441

// All remaining whitespace-separated tokens are the grid values, row-major
// from NORTH (+90) to SOUTH (-90), WEST (0) to EAST (360).
const tokens = lines.slice(1).join(" ").trim().split(/\s+/);
if (tokens.length !== srcRows * srcCols) {
  console.error(
    `Unexpected value count: got ${tokens.length}, expected ${srcRows * srcCols} (${srcRows}x${srcCols}).`
  );
  process.exit(1);
}
const src2d = new Float32Array(tokens.length);
for (let i = 0; i < tokens.length; i++) src2d[i] = Number.parseFloat(tokens[i]);

// Subsample stride: how many source cells per output cell (0.25 -> 1.0 = 4).
const rowStride = Math.round(1 / dlat); // 4
const colStride = Math.round(1 / dlon); // 4

const out = new Int16Array(OUT_NROWS * OUT_NCOLS);
let minCm = Infinity;
let maxCm = -Infinity;
for (let R = 0; R < OUT_NROWS; R++) {
  // Output row R -> latitude (90 - R). Source is north-to-south, so source
  // row index r = R * rowStride (r = 0 is +90, r = srcRows-1 is -90).
  const r = R * rowStride;
  for (let C = 0; C < OUT_NCOLS; C++) {
    const k = C * colStride; // longitude C deg -> source column C * stride
    const metres = src2d[r * srcCols + k];
    let cm = Math.round(metres * 100);
    if (cm > 32767) cm = 32767;
    if (cm < -32768) cm = -32768;
    out[R * OUT_NCOLS + C] = cm;
    if (cm < minCm) minCm = cm;
    if (cm > maxCm) maxCm = cm;
  }
}

// Serialize little-endian Int16 (matches geoid.ts DataView getInt16(_, true)).
const buf = Buffer.alloc(out.length * 2);
for (let i = 0; i < out.length; i++) buf.writeInt16LE(out[i], i * 2);
const gz = gzipSync(buf, { level: 9 });

mkdirSync(OUT_DIR, { recursive: true });
writeFileSync(OUT_FILE, gz);

console.log(
  `Wrote ${OUT_FILE}\n` +
    `  source:   ${src} (${srcRows}x${srcCols} @ ${dlat} deg)\n` +
    `  output:   ${OUT_NROWS}x${OUT_NCOLS} @ 1 deg, Int16 cm\n` +
    `  range:    ${(minCm / 100).toFixed(3)} .. ${(maxCm / 100).toFixed(3)} m\n` +
    `  raw/gzip: ${buf.length} / ${gz.length} bytes`
);
