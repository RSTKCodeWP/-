/**
 * @module export-flight-brief.test
 * @description Tests for the pure parts of the flight-brief PDF export: the
 * plan-statistics derivation (`computeBriefStats`), the file-name slug
 * (`slugifyMissionName`), and the waypoint-row builder (`buildBriefRows`). The
 * actual `pdf().toBlob()` render needs a DOM/worker and is exercised in the app,
 * not here.
 * @license GPL-3.0-only
 */

import { describe, it, expect } from "vitest";
import {
  computeBriefStats,
  slugifyMissionName,
  buildBriefRows,
  DEFAULT_CRUISE_SPEED_MPS,
} from "@/lib/pdf/export-flight-brief";
import type { Waypoint } from "@/lib/types";

function wp(overrides: Partial<Waypoint>): Waypoint {
  return {
    id: Math.random().toString(36).slice(2),
    lat: 0,
    lon: 0,
    alt: 0,
    ...overrides,
  };
}

describe("computeBriefStats", () => {
  it("returns honest zeros for an empty plan", () => {
    const stats = computeBriefStats([]);
    expect(stats).toEqual({
      waypointCount: 0,
      distanceM: 0,
      durationS: 0,
      altMin: 0,
      altMax: 0,
    });
  });

  it("returns zero distance/duration but real alt range for a single waypoint", () => {
    const stats = computeBriefStats([wp({ alt: 42 })]);
    expect(stats.waypointCount).toBe(1);
    expect(stats.distanceM).toBe(0);
    expect(stats.durationS).toBe(0);
    expect(stats.altMin).toBe(42);
    expect(stats.altMax).toBe(42);
  });

  it("derives altitude min/max from the waypoint altitudes", () => {
    const stats = computeBriefStats([
      wp({ alt: 30 }),
      wp({ alt: 120 }),
      wp({ alt: 55 }),
    ]);
    expect(stats.altMin).toBe(30);
    expect(stats.altMax).toBe(120);
    expect(stats.waypointCount).toBe(3);
  });

  it("computes a positive distance and duration for a real leg", () => {
    // Two points ~1 km apart on the equator (0.009 deg lon ~= 1002 m).
    const wps = [wp({ lat: 0, lon: 0, alt: 50 }), wp({ lat: 0, lon: 0.009, alt: 50 })];
    const stats = computeBriefStats(wps, 10);
    expect(stats.distanceM).toBeGreaterThan(900);
    expect(stats.distanceM).toBeLessThan(1100);
    // duration = distance / speed (10 m/s) → ~100 s
    expect(stats.durationS).toBeCloseTo(stats.distanceM / 10, 3);
  });

  it("defaults the cruise speed when none is passed", () => {
    const wps = [wp({ lat: 0, lon: 0, alt: 0 }), wp({ lat: 0, lon: 0.009, alt: 0 })];
    const withDefault = computeBriefStats(wps);
    const explicit = computeBriefStats(wps, DEFAULT_CRUISE_SPEED_MPS);
    expect(withDefault.durationS).toBe(explicit.durationS);
    expect(withDefault.durationS).toBeGreaterThan(0);
  });
});

describe("slugifyMissionName", () => {
  it("lower-cases and hyphenates", () => {
    expect(slugifyMissionName("Perimeter Sweep")).toBe("perimeter-sweep");
  });

  it("collapses runs of non-alphanumeric characters to single hyphens", () => {
    expect(slugifyMissionName("Field  A / North_West!!")).toBe("field-a-north-west");
  });

  it("trims leading and trailing separators", () => {
    expect(slugifyMissionName("  --Survey--  ")).toBe("survey");
  });

  it("falls back to a stable default for empty or symbol-only names", () => {
    expect(slugifyMissionName("")).toBe("flight-brief");
    expect(slugifyMissionName("///")).toBe("flight-brief");
    expect(slugifyMissionName("   ")).toBe("flight-brief");
  });

  it("caps very long names and leaves no trailing hyphen", () => {
    const slug = slugifyMissionName("x".repeat(200));
    expect(slug.length).toBeLessThanOrEqual(64);
    expect(slug.endsWith("-")).toBe(false);
  });
});

describe("buildBriefRows", () => {
  it("assigns 1-based sequence numbers and defaults the command", () => {
    const rows = buildBriefRows([
      wp({ lat: 12.9, lon: 77.6, alt: 30, command: "TAKEOFF" }),
      wp({ lat: 12.91, lon: 77.61, alt: 40 }),
    ]);
    expect(rows).toHaveLength(2);
    expect(rows[0]).toEqual({ seq: 1, lat: 12.9, lon: 77.6, alt: 30, command: "TAKEOFF" });
    expect(rows[1].seq).toBe(2);
    expect(rows[1].command).toBe("WAYPOINT");
  });
});
