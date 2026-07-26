/**
 * @module patterns/__tests__/landing-generators
 * @description Unit tests for the fixed-wing and VTOL landing pattern generators.
 * @license GPL-3.0-only
 */

import { describe, it, expect } from "vitest";
import { generateFixedWingLanding } from "../landing-generator";
import { generateVtolLanding } from "../vtol-landing-generator";
import type { FixedWingLandingConfig, VtolLandingConfig } from "../types";

const LANDING: [number, number] = [12.95, 77.668];

describe("generateFixedWingLanding", () => {
  const config: FixedWingLandingConfig = {
    landingPoint: LANDING,
    approachHeading: 90,
    approachDistance: 400,
    glideSlopeAngle: 5,
    loiterAltitude: 60,
    speed: 15,
  };

  it("produces an approach -> land-start -> land sequence", () => {
    const result = generateFixedWingLanding(config);
    const commands = result.waypoints.map((wp) => wp.command);
    expect(commands[0]).toBe("WAYPOINT");
    expect(commands).toContain("DO_LAND_START");
    expect(commands[commands.length - 1]).toBe("LAND");
  });

  it("ends at the configured landing point on the ground", () => {
    const result = generateFixedWingLanding(config);
    const last = result.waypoints[result.waypoints.length - 1];
    expect(last.lat).toBeCloseTo(LANDING[0], 6);
    expect(last.lon).toBeCloseTo(LANDING[1], 6);
    expect(last.alt).toBe(0);
  });

  it("projects the approach start away from the landing point and previews it", () => {
    const result = generateFixedWingLanding(config);
    const start = result.waypoints[0];
    expect(start.alt).toBe(config.loiterAltitude);
    // Approach start is offset from the landing point, not coincident with it.
    expect(start.lat !== LANDING[0] || start.lon !== LANDING[1]).toBe(true);
    expect(result.previewLines?.length).toBeGreaterThanOrEqual(1);
    expect(result.stats.totalDistance).toBeGreaterThan(0);
  });

  it("returns no waypoints when the geometry is invalid", () => {
    const result = generateFixedWingLanding({ ...config, approachDistance: 0 });
    expect(result.waypoints).toHaveLength(0);
  });
});

describe("generateVtolLanding", () => {
  const config: VtolLandingConfig = {
    landingPoint: LANDING,
    approachHeading: 180,
    transitionDistance: 150,
    approachAltitude: 50,
    descentSpeed: 2,
    speed: 8,
  };

  it("produces a cruise-approach descent ending in a vertical land", () => {
    const result = generateVtolLanding(config);
    const commands = result.waypoints.map((wp) => wp.command);
    expect(commands[0]).toBe("WAYPOINT");
    expect(commands[commands.length - 1]).toBe("VTOL_LAND");
  });

  it("descends toward the ground at the configured landing point", () => {
    const result = generateVtolLanding(config);
    const first = result.waypoints[0];
    const last = result.waypoints[result.waypoints.length - 1];
    expect(first.alt).toBe(config.approachAltitude);
    expect(last.lat).toBeCloseTo(LANDING[0], 6);
    expect(last.lon).toBeCloseTo(LANDING[1], 6);
    expect(last.alt).toBe(0);
    expect(result.previewLines?.length).toBeGreaterThanOrEqual(1);
  });

  it("returns no waypoints when the geometry is invalid", () => {
    const result = generateVtolLanding({ ...config, approachAltitude: 0 });
    expect(result.waypoints).toHaveLength(0);
  });
});
