/**
 * @module patterns/__tests__/fixed-wing-turnaround
 * @description Unit tests for the fixed-wing turnaround / min-turn-radius geometry.
 * @license GPL-3.0-only
 */

import { describe, it, expect } from "vitest";
import {
  GRAVITY_MPS2,
  minTurnRadius,
  turnaroundExtension,
  needsTurnaround,
} from "../fixed-wing-turnaround";

describe("minTurnRadius", () => {
  it("matches the closed-form r = v^2 / (g * tan(bank))", () => {
    const v = 20;
    const bank = 30;
    const expected =
      (v * v) / (GRAVITY_MPS2 * Math.tan((bank * Math.PI) / 180));
    expect(minTurnRadius(v, bank)).toBeCloseTo(expected, 9);
  });

  it("computes a realistic small-UAV turn radius", () => {
    // 18 m/s at 35 deg bank -> ~47 m.
    const r = minTurnRadius(18, 35);
    expect(r).toBeGreaterThan(40);
    expect(r).toBeLessThan(55);
  });

  it("tightens with steeper bank at fixed speed", () => {
    expect(minTurnRadius(20, 45)).toBeLessThan(minTurnRadius(20, 20));
  });

  it("widens with the square of airspeed at fixed bank", () => {
    const r1 = minTurnRadius(10, 30);
    const r2 = minTurnRadius(20, 30);
    // Doubling speed quadruples the radius.
    expect(r2).toBeCloseTo(r1 * 4, 6);
  });

  it("returns Infinity when the aircraft cannot bank", () => {
    expect(minTurnRadius(20, 0)).toBe(Infinity);
    expect(minTurnRadius(20, -10)).toBe(Infinity);
  });

  it("returns 0 for non-positive speed", () => {
    expect(minTurnRadius(0, 30)).toBe(0);
    expect(minTurnRadius(-5, 30)).toBe(0);
  });

  it("clamps to 0 at or beyond 90 deg bank", () => {
    expect(minTurnRadius(20, 90)).toBe(0);
    expect(minTurnRadius(20, 120)).toBe(0);
  });

  it("returns 0 for NaN speed", () => {
    expect(minTurnRadius(NaN, 30)).toBe(0);
  });
});

describe("turnaroundExtension", () => {
  it("returns one turn radius as the lead-out apex distance", () => {
    expect(turnaroundExtension(50)).toBe(50);
    expect(turnaroundExtension(12.5)).toBe(12.5);
  });

  it("returns 0 for non-positive radius", () => {
    expect(turnaroundExtension(0)).toBe(0);
    expect(turnaroundExtension(-10)).toBe(0);
  });

  it("returns 0 for NaN radius", () => {
    expect(turnaroundExtension(NaN)).toBe(0);
  });

  it("propagates Infinity when the aircraft cannot turn", () => {
    expect(turnaroundExtension(Infinity)).toBe(Infinity);
  });

  it("composes with minTurnRadius", () => {
    const r = minTurnRadius(18, 35);
    expect(turnaroundExtension(r)).toBe(r);
  });
});

describe("needsTurnaround", () => {
  it("is true when spacing is tighter than the U-turn diameter", () => {
    // radius 50 -> diameter 100; 60 < 100.
    expect(needsTurnaround(60, 50)).toBe(true);
  });

  it("is false when spacing exactly equals the U-turn diameter", () => {
    expect(needsTurnaround(100, 50)).toBe(false);
  });

  it("is false when spacing comfortably fits the U-turn", () => {
    expect(needsTurnaround(150, 50)).toBe(false);
  });

  it("is false for degenerate radius", () => {
    expect(needsTurnaround(60, 0)).toBe(false);
    expect(needsTurnaround(60, -5)).toBe(false);
  });

  it("is false for degenerate spacing", () => {
    expect(needsTurnaround(0, 50)).toBe(false);
    expect(needsTurnaround(-10, 50)).toBe(false);
  });

  it("is true when the aircraft cannot turn at all", () => {
    // Infinite radius -> any finite spacing is too tight.
    expect(needsTurnaround(1000, Infinity)).toBe(true);
  });

  it("flags a tight-spacing survey built from real inputs", () => {
    const r = minTurnRadius(20, 25); // ~87 m
    const spacing = 80; // narrower than 2r (~175 m)
    expect(needsTurnaround(spacing, r)).toBe(true);
    expect(needsTurnaround(2 * r + 1, r)).toBe(false);
  });
});
