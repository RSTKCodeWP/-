/**
 * @module tests/unit/flight-path-spline
 * @description Contract tests for the rounded-turns display preview used by
 * FlightPathEntity. The preview seeds `roundCorners` with the mission waypoints
 * and the component's own tension / samples-per-segment constants, then draws a
 * smoothed polyline. These tests pin the vertex count, waypoint preservation,
 * and the "rounded differs from straight at a corner" behavior that the toggle
 * is meant to produce, so a regression in the constants or the smoother is
 * caught. The smoothing is display-only: the flight controller flies its own
 * cornering, so the tests never assert anything about the flown trajectory.
 * @license GPL-3.0-only
 */

import { describe, expect, it } from "vitest";
import { roundCorners, type LatLonAlt } from "@/lib/simulation/spline-path";

// Mirrors the constants in src/components/simulation/FlightPathEntity.tsx.
// If those change, update here — the preview shape depends on them.
const ROUNDED_TURNS_TENSION = 0.5;
const ROUNDED_TURNS_SAMPLES_PER_SEG = 8;

// A mission-like ground track with two sharp corners (Bangalore-ish coords).
const MISSION: LatLonAlt[] = [
  { lat: 12.9000, lon: 77.6000, alt: 30 },
  { lat: 12.9100, lon: 77.6000, alt: 40 }, // north leg, then corner
  { lat: 12.9100, lon: 77.6120, alt: 40 }, // east leg, then corner
  { lat: 12.9000, lon: 77.6120, alt: 30 }, // south leg
];

/** Twice the signed area of triangle (a, b, c); ~0 means collinear. */
function collinearError(a: LatLonAlt, b: LatLonAlt, c: LatLonAlt): number {
  return Math.abs(
    (b.lon - a.lon) * (c.lat - a.lat) - (c.lon - a.lon) * (b.lat - a.lat),
  );
}

describe("rounded-turns display preview (FlightPathEntity contract)", () => {
  it("emits (segments * samplesPerSeg + 1) vertices, denser than the raw path", () => {
    const preview = roundCorners(
      MISSION,
      ROUNDED_TURNS_TENSION,
      ROUNDED_TURNS_SAMPLES_PER_SEG,
    );
    const segments = MISSION.length - 1;
    expect(preview.length).toBe(segments * ROUNDED_TURNS_SAMPLES_PER_SEG + 1);
    // The preview must be strictly denser than the straight waypoint polyline.
    expect(preview.length).toBeGreaterThan(MISSION.length);
  });

  it("still passes exactly through every original waypoint (no timing implied)", () => {
    const preview = roundCorners(
      MISSION,
      ROUNDED_TURNS_TENSION,
      ROUNDED_TURNS_SAMPLES_PER_SEG,
    );
    // Each waypoint lands at the start of its segment; the last is appended.
    for (let i = 0; i < MISSION.length; i++) {
      expect(preview[i * ROUNDED_TURNS_SAMPLES_PER_SEG]).toEqual(MISSION[i]);
    }
    expect(preview[preview.length - 1]).toEqual(MISSION[MISSION.length - 1]);
  });

  it("bends the drawn line away from the hard-corner path at the corners", () => {
    const straight = roundCorners(MISSION, 0, ROUNDED_TURNS_SAMPLES_PER_SEG);
    const rounded = roundCorners(
      MISSION,
      ROUNDED_TURNS_TENSION,
      ROUNDED_TURNS_SAMPLES_PER_SEG,
    );
    expect(rounded.length).toBe(straight.length);

    let maxDeviation = 0;
    for (let i = 0; i < rounded.length; i++) {
      maxDeviation = Math.max(
        maxDeviation,
        Math.hypot(
          rounded[i].lat - straight[i].lat,
          rounded[i].lon - straight[i].lon,
        ),
      );
    }
    // A visible displacement proves the smoothing actually rounds the corners.
    expect(maxDeviation).toBeGreaterThan(1e-4);
  });

  it("leaves a genuinely straight leg unbent even at the preview tension", () => {
    const straightLeg: LatLonAlt[] = [
      { lat: 12.90, lon: 77.60, alt: 50 },
      { lat: 12.90, lon: 77.61, alt: 50 },
      { lat: 12.90, lon: 77.62, alt: 50 },
    ];
    const preview = roundCorners(
      straightLeg,
      ROUNDED_TURNS_TENSION,
      ROUNDED_TURNS_SAMPLES_PER_SEG,
    );
    const a = preview[0];
    const b = preview[preview.length - 1];
    for (const pt of preview) {
      expect(collinearError(a, b, pt)).toBeLessThan(1e-12);
    }
  });

  it("interpolates absolute seed altitude between waypoints for the air path", () => {
    // FlightPathEntity seeds the smoother with absolute (terrain + AGL) altitude
    // so the drawn air line sits between the two waypoint heights on a climb.
    const climb: LatLonAlt[] = [
      { lat: 12.90, lon: 77.60, alt: 100 },
      { lat: 12.91, lon: 77.60, alt: 200 },
    ];
    const preview = roundCorners(
      climb,
      ROUNDED_TURNS_TENSION,
      ROUNDED_TURNS_SAMPLES_PER_SEG,
    );
    for (const pt of preview) {
      expect(pt.alt).toBeGreaterThanOrEqual(100);
      expect(pt.alt).toBeLessThanOrEqual(200);
    }
    // A mid vertex is strictly between the endpoints (a real ramp, not a step).
    const mid = preview[Math.floor(preview.length / 2)];
    expect(mid.alt).toBeGreaterThan(100);
    expect(mid.alt).toBeLessThan(200);
  });
});
