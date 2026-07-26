/**
 * @module tests/lib/spline-path
 * @description Unit tests for the Catmull-Rom corner-rounding display aid.
 * @license GPL-3.0-only
 */

import { describe, expect, it } from "vitest";
import {
  catmullRomPoint,
  roundCorners,
  type LatLonAlt,
  type SplinePoint,
} from "@/lib/simulation/spline-path";

const P = (lat: number, lon: number, alt = 0): SplinePoint => ({ lat, lon, alt });

/** Twice the signed area of triangle (a, b, c); ~0 means the three are collinear. */
function collinearError(a: SplinePoint, b: SplinePoint, c: SplinePoint): number {
  return Math.abs(
    (b.lon - a.lon) * (c.lat - a.lat) - (c.lon - a.lon) * (b.lat - a.lat),
  );
}

describe("catmullRomPoint", () => {
  it("passes through the segment endpoints at t=0 and t=1", () => {
    const p0 = P(0, 0);
    const p1 = P(1, 2, 10);
    const p2 = P(3, 5, 20);
    const p3 = P(4, 9);

    const start = catmullRomPoint(p0, p1, p2, p3, 0);
    const end = catmullRomPoint(p0, p1, p2, p3, 1);

    expect(start).toEqual(p1);
    expect(end).toEqual(p2);
  });

  it("clamps t to [0, 1]", () => {
    const p0 = P(0, 0);
    const p1 = P(1, 1);
    const p2 = P(2, 2);
    const p3 = P(3, 3);

    expect(catmullRomPoint(p0, p1, p2, p3, -5)).toEqual(p1);
    expect(catmullRomPoint(p0, p1, p2, p3, 5)).toEqual(p2);
  });

  it("interpolates altitude along the segment", () => {
    const mid = catmullRomPoint(P(0, 0, 0), P(0, 0, 0), P(0, 0, 100), P(0, 0, 100), 0.5);
    expect(mid.alt).toBeCloseTo(50, 6);
  });
});

describe("roundCorners", () => {
  it("keeps an axis-aligned straight line perfectly straight", () => {
    // Constant lat, increasing lon: every rounded vertex must keep that lat.
    const line: LatLonAlt[] = [
      { lat: 12.9, lon: 77.0, alt: 30 },
      { lat: 12.9, lon: 77.1, alt: 30 },
      { lat: 12.9, lon: 77.2, alt: 30 },
      { lat: 12.9, lon: 77.3, alt: 30 },
    ];

    const path = roundCorners(line, 1, 8);
    for (const pt of path) {
      expect(pt.lat).toBeCloseTo(12.9, 12);
    }
  });

  it("keeps a diagonal straight line straight (collinear output)", () => {
    // lat = 2 * lon along the whole run.
    const line: LatLonAlt[] = [
      { lat: 0, lon: 0, alt: 0 },
      { lat: 2, lon: 1, alt: 0 },
      { lat: 4, lon: 2, alt: 0 },
      { lat: 6, lon: 3, alt: 0 },
    ];

    const path = roundCorners(line, 1, 6);
    const a = path[0];
    const b = path[path.length - 1];
    for (const pt of path) {
      expect(collinearError(a, b, pt)).toBeLessThan(1e-9);
    }
  });

  it("rounds a sharp corner while staying within a bounded envelope", () => {
    const corner: LatLonAlt[] = [
      { lat: 0, lon: 0, alt: 0 },
      { lat: 0, lon: 1, alt: 0 }, // corner vertex
      { lat: 1, lon: 1, alt: 0 },
    ];

    const straight = roundCorners(corner, 0, 10);
    const rounded = roundCorners(corner, 0.5, 10);

    // Same vertex count for a fair per-index comparison.
    expect(rounded.length).toBe(straight.length);

    // At least one interior vertex must be displaced from the hard-corner path.
    let maxDeviation = 0;
    for (let i = 0; i < rounded.length; i++) {
      const d = Math.hypot(
        rounded[i].lat - straight[i].lat,
        rounded[i].lon - straight[i].lon,
      );
      maxDeviation = Math.max(maxDeviation, d);
    }
    expect(maxDeviation).toBeGreaterThan(1e-3);

    // Rounding must stay near the corner: bound the overshoot outside the
    // waypoint bounding box by a generous fraction of the leg length (1 unit).
    const margin = 0.25;
    for (const pt of rounded) {
      expect(pt.lat).toBeGreaterThanOrEqual(0 - margin);
      expect(pt.lat).toBeLessThanOrEqual(1 + margin);
      expect(pt.lon).toBeGreaterThanOrEqual(0 - margin);
      expect(pt.lon).toBeLessThanOrEqual(1 + margin);
    }
  });

  it("passes through every original waypoint", () => {
    const wps: LatLonAlt[] = [
      { lat: 0, lon: 0, alt: 5 },
      { lat: 0, lon: 1, alt: 10 },
      { lat: 1, lon: 1, alt: 15 },
    ];
    const samplesPerSeg = 4;

    const path = roundCorners(wps, 0.5, samplesPerSeg);

    // Each segment starts on its waypoint; the final waypoint is appended.
    expect(path[0]).toEqual({ lat: 0, lon: 0, alt: 5 });
    expect(path[samplesPerSeg]).toEqual({ lat: 0, lon: 1, alt: 10 });
    expect(path[path.length - 1]).toEqual({ lat: 1, lon: 1, alt: 15 });
    expect(path.length).toBe((wps.length - 1) * samplesPerSeg + 1);
  });

  it("tension 0 yields the plain densified straight-leg path", () => {
    const wps: LatLonAlt[] = [
      { lat: 0, lon: 0, alt: 0 },
      { lat: 0, lon: 2, alt: 0 },
    ];

    const path = roundCorners(wps, 0, 2);
    expect(path).toEqual([P(0, 0), P(0, 1), P(0, 2)]);
  });

  it("clamps samplesPerSeg to at least one", () => {
    const wps: LatLonAlt[] = [
      { lat: 0, lon: 0, alt: 0 },
      { lat: 0, lon: 1, alt: 0 },
    ];
    // 0 and negative both collapse to a single sample per segment.
    expect(roundCorners(wps, 1, 0).length).toBe(2);
    expect(roundCorners(wps, 1, -3).length).toBe(2);
  });

  it("returns the raw points when there is nothing to smooth", () => {
    expect(roundCorners([], 1, 5)).toEqual([]);
    expect(roundCorners([{ lat: 1, lon: 2, alt: 3 }], 1, 5)).toEqual([
      { lat: 1, lon: 2, alt: 3 },
    ]);
  });
});
