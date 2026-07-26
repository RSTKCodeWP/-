/**
 * @module geotiff-loader.test
 * @description Unit tests for the GeoTIFF loader's CRS-aware bbox → lat/lon
 * mapping (`bboxToLatLonBounds`) and for `loadGeoTIFF` returning `null` on an
 * unreadable / non-georeferenced / unsupported-CRS file. `geotiff` is mocked so
 * no real raster decode or canvas is exercised. All fixtures are generic
 * synthetic coordinates.
 * @license GPL-3.0-only
 */

import { describe, it, expect, vi, beforeEach } from "vitest";

// Mock the geotiff module so loadGeoTIFF can be driven through fake images.
const fromArrayBuffer = vi.fn();
vi.mock("geotiff", () => ({ fromArrayBuffer: (...args: unknown[]) => fromArrayBuffer(...args) }));

import { bboxToLatLonBounds, loadGeoTIFF, type GeoKeyHints } from "@/lib/formats/geotiff-loader";

const GEOGRAPHIC: GeoKeyHints = { GTModelTypeGeoKey: 2, GeographicTypeGeoKey: 4326 };

/** Spherical Web Mercator inverse — mirrors the loader, for expected values. */
function mercatorToLonLat(x: number, y: number): [number, number] {
  const R = 6378137;
  return [
    (x / R) * (180 / Math.PI),
    (2 * Math.atan(Math.exp(y / R)) - Math.PI / 2) * (180 / Math.PI),
  ];
}

describe("bboxToLatLonBounds", () => {
  it("maps a geographic (EPSG:4326) bbox directly to [[south,west],[north,east]]", () => {
    // GeoTIFF bbox is [minLon, minLat, maxLon, maxLat].
    const bounds = bboxToLatLonBounds([77.1, 12.9, 77.3, 13.1], GEOGRAPHIC);
    expect(bounds).toEqual([
      [12.9, 77.1],
      [13.1, 77.3],
    ]);
  });

  it("treats a bbox with no CRS hints but in lon/lat range as geographic", () => {
    const bounds = bboxToLatLonBounds([10, 20, 11, 21], null);
    expect(bounds).toEqual([
      [20, 10],
      [21, 11],
    ]);
  });

  it("reprojects a Web Mercator (EPSG:3857) bbox from meters to lat/lon", () => {
    const bbox = [8_000_000, 1_000_000, 8_100_000, 1_100_000];
    const bounds = bboxToLatLonBounds(bbox, {
      GTModelTypeGeoKey: 1,
      ProjectedCSTypeGeoKey: 3857,
    });
    expect(bounds).not.toBeNull();
    const [[south, west], [north, east]] = bounds!;
    const [expWest, expSouth] = mercatorToLonLat(bbox[0], bbox[1]);
    const [expEast, expNorth] = mercatorToLonLat(bbox[2], bbox[3]);
    expect(west).toBeCloseTo(expWest, 6);
    expect(south).toBeCloseTo(expSouth, 6);
    expect(east).toBeCloseTo(expEast, 6);
    expect(north).toBeCloseTo(expNorth, 6);
    // Proves reprojection actually happened (not an identity pass-through).
    expect(west).not.toBeCloseTo(bbox[0], 0);
    expect(south).toBeGreaterThan(-90);
    expect(north).toBeLessThan(90);
  });

  it("returns null for a projected CRS it cannot reproject (e.g. UTM 43N)", () => {
    const bounds = bboxToLatLonBounds([700000, 1400000, 710000, 1410000], {
      GTModelTypeGeoKey: 1,
      ProjectedCSTypeGeoKey: 32643,
    });
    expect(bounds).toBeNull();
  });

  it("returns null for a degenerate (reversed) box", () => {
    expect(bboxToLatLonBounds([77.3, 13.1, 77.1, 12.9], GEOGRAPHIC)).toBeNull();
  });

  it("returns null when resolved bounds fall outside the WGS84 range", () => {
    expect(bboxToLatLonBounds([77, 12, 200, 95], GEOGRAPHIC)).toBeNull();
  });

  it("returns null for a malformed or non-finite bbox", () => {
    expect(bboxToLatLonBounds([1, 2, 3], GEOGRAPHIC)).toBeNull();
    expect(bboxToLatLonBounds([Number.NaN, 1, 2, 3], GEOGRAPHIC)).toBeNull();
    expect(bboxToLatLonBounds([], null)).toBeNull();
  });
});

describe("loadGeoTIFF", () => {
  beforeEach(() => {
    fromArrayBuffer.mockReset();
  });

  it("returns null for a non-georeferenced image (getBoundingBox throws)", async () => {
    fromArrayBuffer.mockResolvedValue({
      getImage: async () => ({
        getBoundingBox: () => {
          throw new Error("The image does not have an affine transformation.");
        },
        getGeoKeys: () => null,
      }),
    });
    expect(await loadGeoTIFF(new ArrayBuffer(8))).toBeNull();
  });

  it("returns null when the CRS cannot be resolved to lat/lon", async () => {
    fromArrayBuffer.mockResolvedValue({
      getImage: async () => ({
        getBoundingBox: () => [700000, 1400000, 710000, 1410000],
        getGeoKeys: () => ({ GTModelTypeGeoKey: 1, ProjectedCSTypeGeoKey: 32643 }),
      }),
    });
    expect(await loadGeoTIFF(new ArrayBuffer(8))).toBeNull();
  });

  it("returns null when the decoder itself throws", async () => {
    fromArrayBuffer.mockRejectedValue(new Error("corrupt file"));
    expect(await loadGeoTIFF(new ArrayBuffer(8))).toBeNull();
  });
});
