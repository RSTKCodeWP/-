import { describe, it, expect } from "vitest";
import {
  planResurvey,
  type Polygon,
  type ResurveyOptions,
} from "@/lib/ai/change-detection";
import { polygonArea } from "@/lib/drawing/geo-utils";

// Clipped vertices legitimately land ON the original's boundary edges, where
// ray-casting point-in-polygon is ambiguous, so assert the footprint bound
// (inside-or-on) instead: every vertex sits within the original square ±eps.
const EPS = 1e-9;
function withinOriginal(v: [number, number]): boolean {
  return (
    v[0] >= BASE_LAT - EPS &&
    v[0] <= BASE_LAT + D + EPS &&
    v[1] >= BASE_LON - EPS &&
    v[1] <= BASE_LON + D + EPS
  );
}

// A ~0.01deg square boundary near a base point (roughly a 1.1 km square).
const BASE_LAT = 12.9;
const BASE_LON = 77.6;
const D = 0.01;

const ORIGINAL: Polygon = [
  [BASE_LAT, BASE_LON],
  [BASE_LAT, BASE_LON + D],
  [BASE_LAT + D, BASE_LON + D],
  [BASE_LAT + D, BASE_LON],
];

const OPTS: ResurveyOptions = {
  gridAngle: 0,
  lineSpacing: 20,
  altitude: 60,
  speed: 8,
};

/** Axis-aligned square subarea from a corner offset, spanning `size` degrees. */
function square(latOff: number, lonOff: number, size: number): Polygon {
  const lat = BASE_LAT + latOff;
  const lon = BASE_LON + lonOff;
  return [
    [lat, lon],
    [lat, lon + size],
    [lat + size, lon + size],
    [lat + size, lon],
  ];
}

describe("planResurvey", () => {
  it("clips a fully-interior subarea to a smaller polygon inside the original", () => {
    const sub = square(D * 0.25, D * 0.25, D * 0.5); // centered, well inside
    const plan = planResurvey(ORIGINAL, [sub], OPTS);

    expect(plan.subareas).toHaveLength(1);
    const rs = plan.subareas[0];
    // Smaller than the original.
    expect(rs.areaSqMeters).toBeLessThan(plan.originalAreaSqMeters);
    expect(rs.areaSqMeters).toBeGreaterThan(0);
    // Every clipped vertex lies within the original footprint.
    for (const v of rs.polygon) {
      expect(withinOriginal(v)).toBe(true);
    }
    // Fraction reflects the reduced flight footprint.
    expect(plan.areaFraction).toBeLessThan(1);
    expect(plan.areaFraction).toBeGreaterThan(0);
  });

  it("trims a subarea that spills outside the original to the intersection", () => {
    // Overlaps the top-right corner and extends beyond it on both axes.
    const sub = square(D * 0.5, D * 0.5, D); // spans to BASE+1.5D, past the edge
    const plan = planResurvey(ORIGINAL, [sub], OPTS);

    expect(plan.subareas).toHaveLength(1);
    const rs = plan.subareas[0];
    const subArea = polygonArea(sub);

    // Intersection is smaller than both the raw subarea and the original.
    expect(rs.areaSqMeters).toBeLessThan(subArea);
    expect(rs.areaSqMeters).toBeLessThan(plan.originalAreaSqMeters);
    // Clipped result stays within the original footprint.
    for (const v of rs.polygon) {
      expect(withinOriginal(v)).toBe(true);
    }
    // Expected intersection area ≈ a quarter-size square (0.5D x 0.5D corner).
    const quarter = polygonArea(square(D * 0.5, D * 0.5, D * 0.5));
    expect(rs.areaSqMeters).toBeCloseTo(quarter, -1);
  });

  it("inherits the grid options into each generated survey config", () => {
    const sub = square(D * 0.25, D * 0.25, D * 0.5);
    const plan = planResurvey(ORIGINAL, [sub], {
      ...OPTS,
      cameraTriggerDistance: 15,
      turnAroundDistance: 10,
    });

    const survey = plan.subareas[0].survey;
    expect(survey.gridAngle).toBe(OPTS.gridAngle);
    expect(survey.lineSpacing).toBe(OPTS.lineSpacing);
    expect(survey.altitude).toBe(OPTS.altitude);
    expect(survey.speed).toBe(OPTS.speed);
    expect(survey.cameraTriggerDistance).toBe(15);
    expect(survey.turnAroundDistance).toBe(10);
    // Its boundary is exactly the clipped polygon.
    expect(survey.polygon).toBe(plan.subareas[0].polygon);
    // Sensible defaults for unspecified fields.
    expect(survey.entryLocation).toBe("topLeft");
    expect(survey.flyAlternateTransects).toBe(false);
  });

  it("skips a subarea that does not overlap the original", () => {
    const outside = square(D * 3, D * 3, D * 0.5); // entirely beyond the boundary
    const plan = planResurvey(ORIGINAL, [outside], OPTS);

    expect(plan.subareas).toHaveLength(0);
    expect(plan.skippedSubareaIndices).toEqual([0]);
    expect(plan.totalAreaSqMeters).toBe(0);
    expect(plan.areaFraction).toBe(0);
  });

  it("handles multiple subareas, keeping index provenance and totals", () => {
    const inside = square(D * 0.1, D * 0.1, D * 0.3);
    const outside = square(D * 5, D * 5, D * 0.5);
    const overlap = square(D * 0.6, D * 0.6, D); // spills past the corner
    const plan = planResurvey(ORIGINAL, [inside, outside, overlap], OPTS);

    // Two survive (0 and 2); the fully-outside one (1) is skipped.
    expect(plan.subareas.map((s) => s.subareaIndex)).toEqual([0, 2]);
    expect(plan.skippedSubareaIndices).toEqual([1]);
    const summed = plan.subareas.reduce((s, a) => s + a.areaSqMeters, 0);
    expect(plan.totalAreaSqMeters).toBeCloseTo(summed, 3);
    expect(plan.totalAreaSqMeters).toBeLessThan(plan.originalAreaSqMeters);
  });

  it("drops slivers below minSubareaArea", () => {
    const tiny = square(D * 0.4, D * 0.4, D * 0.02); // very small square
    const tinyArea = polygonArea(tiny);
    const plan = planResurvey(ORIGINAL, [tiny], {
      ...OPTS,
      minSubareaArea: tinyArea * 2, // threshold above the sliver
    });

    expect(plan.subareas).toHaveLength(0);
    expect(plan.skippedSubareaIndices).toEqual([0]);
  });

  it("skips degenerate subareas (fewer than 3 distinct vertices)", () => {
    const degenerate: Polygon = [
      [BASE_LAT + D * 0.3, BASE_LON + D * 0.3],
      [BASE_LAT + D * 0.4, BASE_LON + D * 0.4],
    ];
    const plan = planResurvey(ORIGINAL, [degenerate], OPTS);
    expect(plan.subareas).toHaveLength(0);
    expect(plan.skippedSubareaIndices).toEqual([0]);
  });

  it("returns an empty plan when the original polygon is degenerate", () => {
    const badOriginal: Polygon = [
      [BASE_LAT, BASE_LON],
      [BASE_LAT, BASE_LON + D],
    ];
    const sub = square(D * 0.25, D * 0.25, D * 0.5);
    const plan = planResurvey(badOriginal, [sub], OPTS);

    expect(plan.subareas).toHaveLength(0);
    expect(plan.skippedSubareaIndices).toEqual([0]);
    expect(plan.areaFraction).toBe(0);
  });
});
