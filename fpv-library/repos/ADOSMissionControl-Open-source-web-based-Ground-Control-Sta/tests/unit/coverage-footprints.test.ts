/**
 * Coverage footprint geometry: each route point gets one camera-footprint rectangle
 * sized from the real camera + altitude and oriented along the leg. Empty/degenerate
 * inputs produce no footprints (never a fabricated coverage claim).
 * @license GPL-3.0-only
 */
import { describe, it, expect } from "vitest";
import { buildFootprintPolygon, buildFootprintPolygons } from "@/lib/patterns/coverage-footprints";
import type { CameraProfile } from "@/lib/patterns/gsd-calculator";

const CAMERA: CameraProfile = {
  name: "Test",
  sensorWidth: 17.3,
  sensorHeight: 13.0,
  focalLength: 12.29,
  imageWidth: 5280,
  imageHeight: 3956,
};

describe("buildFootprintPolygon", () => {
  it("returns four corners centred on the point", () => {
    const poly = buildFootprintPolygon(12.5, 77.5, 0, 100, 60);
    expect(poly).toHaveLength(4);
    // The centroid of the four corners is (approximately) the input point.
    const cLat = poly.reduce((s, p) => s + p[0], 0) / 4;
    const cLon = poly.reduce((s, p) => s + p[1], 0) / 4;
    expect(cLat).toBeCloseTo(12.5, 4);
    expect(cLon).toBeCloseTo(77.5, 4);
  });

  it("grows with a larger footprint", () => {
    const small = buildFootprintPolygon(0, 0, 0, 20, 20);
    const big = buildFootprintPolygon(0, 0, 0, 200, 200);
    const span = (p: [number, number][]) => Math.max(...p.map((c) => c[0])) - Math.min(...p.map((c) => c[0]));
    expect(span(big)).toBeGreaterThan(span(small));
  });
});

describe("buildFootprintPolygons", () => {
  const route = [
    { lat: 12.5, lon: 77.5 },
    { lat: 12.51, lon: 77.5 },
    { lat: 12.52, lon: 77.5 },
  ];

  it("builds one footprint per point", () => {
    const polys = buildFootprintPolygons(route, CAMERA, 50);
    expect(polys).toHaveLength(3);
    for (const p of polys) expect(p).toHaveLength(4);
  });

  it("returns nothing for an empty route", () => {
    expect(buildFootprintPolygons([], CAMERA, 50)).toEqual([]);
  });

  it("returns nothing for a non-positive altitude (no fabricated footprint)", () => {
    expect(buildFootprintPolygons(route, CAMERA, 0)).toEqual([]);
    expect(buildFootprintPolygons(route, CAMERA, -10)).toEqual([]);
    expect(buildFootprintPolygons(route, CAMERA, NaN)).toEqual([]);
  });

  it("respects the maxCount safety cap", () => {
    const many = Array.from({ length: 100 }, (_, i) => ({ lat: 12.5 + i * 0.001, lon: 77.5 }));
    expect(buildFootprintPolygons(many, CAMERA, 50, 10)).toHaveLength(10);
  });
});
