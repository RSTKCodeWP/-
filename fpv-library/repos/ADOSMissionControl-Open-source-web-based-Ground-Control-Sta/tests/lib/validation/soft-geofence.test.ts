import { describe, it, expect } from "vitest";
import {
  checkSoftBuffer,
  DEFAULT_SOFT_BUFFER_M,
  type SoftGeofence,
} from "@/lib/validation/soft-geofence";
import type { Waypoint } from "@/lib/types";

function wp(
  overrides: Partial<Waypoint> & { lat: number; lon: number }
): Waypoint {
  return {
    id: Math.random().toString(36).slice(2, 10),
    alt: 50,
    command: "WAYPOINT",
    ...overrides,
  };
}

// Test site at 12N, 77E (Bangalore-ish). Metric offsets kept small so the
// local equirectangular approximation in the module is essentially exact.
const CENTER_LAT = 12.0;
const CENTER_LON = 77.0;
const COS_LAT = Math.cos((CENTER_LAT * Math.PI) / 180);
const M_PER_DEG = 111_320;

/** A point `north`/`east` meters from the test center. */
function offset(northM: number, eastM: number): { lat: number; lon: number } {
  return {
    lat: CENTER_LAT + northM / M_PER_DEG,
    lon: CENTER_LON + eastM / (M_PER_DEG * COS_LAT),
  };
}

// 400m x 400m square fence (half-side 200m) centered on the test site.
const HALF = 200;
const dLat = HALF / M_PER_DEG;
const dLon = HALF / (M_PER_DEG * COS_LAT);
const SQUARE: [number, number][] = [
  [CENTER_LAT - dLat, CENTER_LON - dLon],
  [CENTER_LAT - dLat, CENTER_LON + dLon],
  [CENTER_LAT + dLat, CENTER_LON + dLon],
  [CENTER_LAT + dLat, CENTER_LON - dLon],
];

describe("checkSoftBuffer — polygon fence", () => {
  it("warns for a waypoint inside but near an edge", () => {
    // 15m south of the north edge → ~15m from the boundary.
    const p = offset(HALF - 15, 0);
    const out = checkSoftBuffer([wp(p)], { polygonPoints: SQUARE });
    expect(out).toHaveLength(1);
    expect(out[0].waypointIndex).toBe(0);
    expect(out[0].distanceToEdgeM).toBeCloseTo(15, 0);
    expect(out[0].message).toContain("WP1");
    expect(out[0].message).toContain("15m");
  });

  it("does not warn for a deep-interior waypoint (200m from every edge)", () => {
    const out = checkSoftBuffer(
      [wp({ lat: CENTER_LAT, lon: CENTER_LON })],
      { polygonPoints: SQUARE }
    );
    expect(out).toEqual([]);
  });

  it("does not warn for a waypoint outside the fence (hard breach handled elsewhere)", () => {
    const p = offset(HALF + 50, 0); // 50m north of the north edge, outside
    const out = checkSoftBuffer([wp(p)], { polygonPoints: SQUARE });
    expect(out).toEqual([]);
  });

  it("reports the nearest edge distance for a corner-adjacent waypoint", () => {
    // 10m inside from both the north and east edges → nearest edge ~10m.
    const p = offset(HALF - 10, HALF - 10);
    const out = checkSoftBuffer([wp(p)], { polygonPoints: SQUARE });
    expect(out).toHaveLength(1);
    expect(out[0].distanceToEdgeM).toBeCloseTo(10, 0);
  });

  it("honors a custom buffer width", () => {
    const p = offset(HALF - 45, 0); // 45m from the boundary
    expect(checkSoftBuffer([wp(p)], { polygonPoints: SQUARE }, 30)).toEqual([]);
    const wide = checkSoftBuffer([wp(p)], { polygonPoints: SQUARE }, 60);
    expect(wide).toHaveLength(1);
    expect(wide[0].message).toContain("60m warning buffer");
  });

  it("flags each approaching waypoint with the correct index", () => {
    const deep = { lat: CENTER_LAT, lon: CENTER_LON };
    const near = offset(HALF - 5, 0);
    const out = checkSoftBuffer(
      [wp(deep), wp(near), wp(deep)],
      { polygonPoints: SQUARE }
    );
    expect(out).toHaveLength(1);
    expect(out[0].waypointIndex).toBe(1);
  });

  it("treats a polygon with fewer than 3 points as no fence", () => {
    const twoPt: SoftGeofence = {
      polygonPoints: [
        [CENTER_LAT, CENTER_LON],
        [CENTER_LAT + dLat, CENTER_LON],
      ],
    };
    expect(checkSoftBuffer([wp(offset(0, 0))], twoPt)).toEqual([]);
  });
});

describe("checkSoftBuffer — circle fence", () => {
  const CIRCLE: SoftGeofence = {
    circleCenter: [CENTER_LAT, CENTER_LON],
    circleRadius: 100,
  };

  it("warns for a waypoint inside but within the buffer of the radius", () => {
    const p = offset(80, 0); // 80m from center → 20m from the 100m edge
    const out = checkSoftBuffer([wp(p)], CIRCLE);
    expect(out).toHaveLength(1);
    expect(out[0].distanceToEdgeM).toBeCloseTo(20, 0);
  });

  it("does not warn for a waypoint well inside the circle", () => {
    const p = offset(5, 0); // 95m from the edge
    expect(checkSoftBuffer([wp(p)], CIRCLE)).toEqual([]);
  });

  it("does not warn for a waypoint outside the circle", () => {
    const p = offset(150, 0); // beyond the 100m radius
    expect(checkSoftBuffer([wp(p)], CIRCLE)).toEqual([]);
  });

  it("warns at the center when the whole radius fits inside the buffer", () => {
    const tight: SoftGeofence = {
      circleCenter: [CENTER_LAT, CENTER_LON],
      circleRadius: 20,
    };
    const out = checkSoftBuffer(
      [wp({ lat: CENTER_LAT, lon: CENTER_LON })],
      tight
    );
    expect(out).toHaveLength(1);
    expect(out[0].distanceToEdgeM).toBeCloseTo(20, 0);
  });

  it("ignores a circle with a non-positive radius", () => {
    const bad: SoftGeofence = { circleCenter: [CENTER_LAT, CENTER_LON], circleRadius: 0 };
    expect(checkSoftBuffer([wp(offset(0, 0))], bad)).toEqual([]);
  });
});

describe("checkSoftBuffer — precedence and guards", () => {
  it("uses the polygon when both polygon and circle are supplied", () => {
    const both: SoftGeofence = {
      polygonPoints: SQUARE,
      circleCenter: [CENTER_LAT, CENTER_LON],
      circleRadius: 5, // would flag the center if the circle were used
    };
    // Center is deep inside the polygon → no warning if polygon wins.
    const out = checkSoftBuffer(
      [wp({ lat: CENTER_LAT, lon: CENTER_LON })],
      both
    );
    expect(out).toEqual([]);
  });

  it("returns no warnings for an empty waypoint list", () => {
    expect(checkSoftBuffer([], { polygonPoints: SQUARE })).toEqual([]);
  });

  it("returns no warnings when the fence is empty", () => {
    expect(checkSoftBuffer([wp(offset(0, 0))], {})).toEqual([]);
  });

  it("returns no warnings when the buffer is zero or negative", () => {
    const near = offset(HALF - 5, 0);
    expect(checkSoftBuffer([wp(near)], { polygonPoints: SQUARE }, 0)).toEqual([]);
    expect(checkSoftBuffer([wp(near)], { polygonPoints: SQUARE }, -10)).toEqual([]);
  });

  it("skips waypoints with non-finite coordinates", () => {
    const out = checkSoftBuffer(
      [wp({ lat: Number.NaN, lon: CENTER_LON })],
      { polygonPoints: SQUARE }
    );
    expect(out).toEqual([]);
  });

  it("defaults the buffer to 30m", () => {
    expect(DEFAULT_SOFT_BUFFER_M).toBe(30);
    const p = offset(HALF - 25, 0); // 25m from the edge → within the 30m default
    const out = checkSoftBuffer([wp(p)], { polygonPoints: SQUARE });
    expect(out).toHaveLength(1);
    expect(out[0].message).toContain("30m warning buffer");
  });
});
