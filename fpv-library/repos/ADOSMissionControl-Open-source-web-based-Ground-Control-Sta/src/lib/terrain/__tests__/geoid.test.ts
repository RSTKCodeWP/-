/**
 * @module terrain/geoid.test
 * @description Unit tests for the EGM96 geoid-separation module. Pins the
 * MSL<->ellipsoidal sign (h = MSL + N), bilinear interpolation, longitude wrap,
 * pole clamp, and — critically — the honest NaN-passthrough when the grid asset
 * is absent (this passes whether or not the bundled asset was generated).
 * @license GPL-3.0-only
 */

import { describe, it, expect, afterEach, vi } from "vitest";
import { readFileSync, existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const HERE = dirname(fileURLToPath(import.meta.url));
// src/lib/terrain/__tests__ -> repo root is four levels up.
const ASSET = join(HERE, "..", "..", "..", "..", "public", "geoid", "egm96-1deg.i16.gz");
const assetExists = existsSync(ASSET);
const assetBytes = assetExists ? readFileSync(ASSET) : null;

/**
 * Official EGM96 test vectors from `WW15MGH.GRD` (`input.dat` / `outintpt.dat`).
 * Undulation `n` in metres. Bilinear over the 1-deg subsample matches these to
 * well under 1 m; the sign is the load-bearing assertion (a +N/-N flip is ~2N).
 */
const CONTROL_POINTS: Array<{ lat: number; lon: number; n: number }> = [
  { lat: 38.628155, lon: 269.779155, n: -31.628 },
  { lat: -14.621217, lon: 305.021114, n: -2.969 },
  { lat: 46.874319, lon: 102.448729, n: -43.575 },
  { lat: -23.617446, lon: 133.874712, n: 15.871 },
  { lat: 38.625473, lon: 359.9995, n: 50.066 },
  { lat: -0.466744, lon: 0.0023, n: 17.329 },
];

/** Stub `fetch` so the module's loader receives the on-disk bundled asset. */
function stubFetchWithAsset(bytes: Buffer): void {
  const ab = bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength);
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => ({ ok: true, arrayBuffer: async () => ab }) as unknown as Response),
  );
}

/** Fresh module instance (resets the memory-cached grid singleton). */
async function importFresh() {
  vi.resetModules();
  return import("../geoid");
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("geoid passthrough (grid absent)", () => {
  it("returns NaN and passes altitudes through unchanged before any load", async () => {
    const g = await importFresh();
    expect(Number.isNaN(g.geoidSeparation(12.97, 77.59))).toBe(true);
    // The MSL-only-correct rule: no grid -> conversions are identity.
    expect(g.mslToEllipsoidal(100, 12.97, 77.59)).toBe(100);
    expect(g.ellipsoidalToMsl(100, 12.97, 77.59)).toBe(100);
  });

  it("stays passthrough when the asset 404s", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => ({ ok: false }) as Response));
    const g = await importFresh();
    await g.loadGeoidGrid();
    expect(Number.isNaN(g.geoidSeparation(0, 0))).toBe(true);
    expect(g.mslToEllipsoidal(50, 0, 0)).toBe(50);
    expect(g.ellipsoidalToMsl(50, 0, 0)).toBe(50);
  });

  it("stays passthrough when fetch throws (offline)", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        throw new Error("network down");
      }),
    );
    const g = await importFresh();
    await g.loadGeoidGrid();
    expect(Number.isNaN(g.geoidSeparation(0, 0))).toBe(true);
    expect(g.mslToEllipsoidal(50, 0, 0)).toBe(50);
  });
});

const withAsset = assetExists ? describe : describe.skip;

withAsset("geoid with the bundled EGM96 grid", () => {
  it("matches official control points and pins the sign (h = MSL + N)", async () => {
    stubFetchWithAsset(assetBytes!);
    const g = await importFresh();
    await g.loadGeoidGrid();
    for (const cp of CONTROL_POINTS) {
      const got = g.geoidSeparation(cp.lat, cp.lon);
      expect(Number.isFinite(got)).toBe(true);
      // Bilinear-on-subsample stays under ~0.5 m of the spline reference.
      expect(Math.abs(got - cp.n)).toBeLessThan(1.0);
      // Sign pin — the whole point. A flipped conversion is ~2N metres off.
      expect(Math.sign(got)).toBe(Math.sign(cp.n));
    }
  });

  it("mslToEllipsoidal adds +N, ellipsoidalToMsl subtracts it", async () => {
    stubFetchWithAsset(assetBytes!);
    const g = await importFresh();
    await g.loadGeoidGrid();
    const lat = 38.625473;
    const lon = 359.9995; // control point 5, N ~ +50 m
    const n = g.geoidSeparation(lat, lon);
    expect(n).toBeGreaterThan(40); // strongly positive here
    expect(g.mslToEllipsoidal(100, lat, lon)).toBeCloseTo(100 + n, 6);
    expect(g.ellipsoidalToMsl(100, lat, lon)).toBeCloseTo(100 - n, 6);
    // Round-trip identity.
    expect(g.ellipsoidalToMsl(g.mslToEllipsoidal(100, lat, lon), lat, lon)).toBeCloseTo(100, 6);
  });

  it("bilinear interpolates linearly along a cell edge and to the cell centre", async () => {
    stubFetchWithAsset(assetBytes!);
    const g = await importFresh();
    await g.loadGeoidGrid();
    // Grid nodes at integer degrees (lat 45/46, lon 100/101).
    const a = g.geoidSeparation(45, 100);
    const b = g.geoidSeparation(46, 100);
    const c = g.geoidSeparation(45, 101);
    const d = g.geoidSeparation(46, 101);
    // Edge midpoint along latitude: exact average of the two nodes.
    expect(g.geoidSeparation(45.5, 100)).toBeCloseTo((a + b) / 2, 6);
    // Cell centre: exact average of the four surrounding nodes.
    expect(g.geoidSeparation(45.5, 100.5)).toBeCloseTo((a + b + c + d) / 4, 6);
  });

  it("wraps longitude (0 == 360, negative == +360)", async () => {
    stubFetchWithAsset(assetBytes!);
    const g = await importFresh();
    await g.loadGeoidGrid();
    const base = g.geoidSeparation(12.97, 77.59);
    expect(g.geoidSeparation(12.97, 77.59 + 360)).toBeCloseTo(base, 9);
    expect(g.geoidSeparation(12.97, 77.59 - 360)).toBeCloseTo(base, 9);
  });

  it("clamps out-of-range latitude to the poles", async () => {
    stubFetchWithAsset(assetBytes!);
    const g = await importFresh();
    await g.loadGeoidGrid();
    // Beyond +/-90 clamps to the pole row.
    expect(g.geoidSeparation(95, 10)).toBeCloseTo(g.geoidSeparation(90, 10), 9);
    expect(g.geoidSeparation(-95, 10)).toBeCloseTo(g.geoidSeparation(-90, 10), 9);
    // A pole is a single point: same undulation at every longitude.
    expect(g.geoidSeparation(90, 0)).toBeCloseTo(g.geoidSeparation(90, 180), 9);
    expect(g.geoidSeparation(-90, 0)).toBeCloseTo(g.geoidSeparation(-90, 250), 9);
  });
});
