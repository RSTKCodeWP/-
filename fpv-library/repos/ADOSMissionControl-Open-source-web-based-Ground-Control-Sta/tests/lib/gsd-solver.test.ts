import { describe, it, expect } from "vitest";
import {
  solveAltitudeForGSD,
  maxSafeGroundSpeed,
  motionBlurPixels,
} from "@/lib/patterns/gsd-solver";
import { computeGSD, CAMERA_PROFILES } from "@/lib/patterns/gsd-calculator";

describe("solveAltitudeForGSD()", () => {
  it("round-trips against computeGSD within 1% for every camera profile", () => {
    for (const cam of CAMERA_PROFILES) {
      for (const altitude of [30, 75, 120, 300]) {
        const gsdMetres = computeGSD(
          altitude,
          cam.focalLength,
          cam.sensorWidth,
          cam.imageWidth,
        );
        const gsdCmPerPx = gsdMetres * 100;
        const solvedAltitude = solveAltitudeForGSD(gsdCmPerPx, cam);
        // within 1%
        expect(Math.abs(solvedAltitude - altitude) / altitude).toBeLessThan(0.01);
      }
    }
  });

  it("halving the target GSD halves the altitude", () => {
    const cam = CAMERA_PROFILES[0];
    const altFine = solveAltitudeForGSD(1, cam);
    const altCoarse = solveAltitudeForGSD(2, cam);
    expect(altCoarse).toBeCloseTo(altFine * 2, 6);
  });

  it("returns 0 for invalid inputs", () => {
    const cam = CAMERA_PROFILES[0];
    expect(solveAltitudeForGSD(0, cam)).toBe(0);
    expect(solveAltitudeForGSD(-3, cam)).toBe(0);
    expect(solveAltitudeForGSD(2, { ...cam, sensorWidth: 0 })).toBe(0);
    expect(solveAltitudeForGSD(2, { ...cam, focalLength: 0 })).toBe(0);
    expect(solveAltitudeForGSD(2, { ...cam, imageWidth: 0 })).toBe(0);
  });
});

describe("maxSafeGroundSpeed()", () => {
  it("increases monotonically with GSD (coarser pixels tolerate more speed)", () => {
    const exposure = 1 / 500; // 0.002 s
    let prev = -Infinity;
    for (const gsd of [1, 2, 3, 5, 10]) {
      const speed = maxSafeGroundSpeed(gsd, exposure);
      expect(speed).toBeGreaterThan(prev);
      prev = speed;
    }
  });

  it("decreases as exposure time grows (slower shutter needs slower flight)", () => {
    const gsd = 2;
    expect(maxSafeGroundSpeed(gsd, 1 / 1000)).toBeGreaterThan(
      maxSafeGroundSpeed(gsd, 1 / 250),
    );
  });

  it("scales linearly with the blur tolerance", () => {
    const s1 = maxSafeGroundSpeed(2, 0.002, 1);
    const s2 = maxSafeGroundSpeed(2, 0.002, 2);
    expect(s2).toBeCloseTo(s1 * 2, 6);
  });

  it("known value: gsd 2 cm/px, 1/500 s, 1 px tolerance => 10 m/s", () => {
    // speed = 1 * (2/100) / (1/500) = 0.02 * 500 = 10 m/s
    expect(maxSafeGroundSpeed(2, 1 / 500, 1)).toBeCloseTo(10, 9);
  });

  it("returns 0 for invalid inputs", () => {
    expect(maxSafeGroundSpeed(0, 0.002)).toBe(0);
    expect(maxSafeGroundSpeed(2, 0)).toBe(0);
    expect(maxSafeGroundSpeed(2, 0.002, 0)).toBe(0);
  });
});

describe("motionBlurPixels()", () => {
  it("known value: 5 m/s, 1/500 s exposure, 2 cm/px => 0.5 px", () => {
    // blurMetres = 5 * 0.002 = 0.01 m; gsd_m = 0.02; blurPx = 0.01 / 0.02 = 0.5
    expect(motionBlurPixels(5, 1 / 500, 2)).toBeCloseTo(0.5, 9);
  });

  it("is the exact inverse of maxSafeGroundSpeed at the tolerance limit", () => {
    const gsd = 3;
    const exposure = 1 / 400;
    const tolerance = 1.5;
    const maxSpeed = maxSafeGroundSpeed(gsd, exposure, tolerance);
    expect(motionBlurPixels(maxSpeed, exposure, gsd)).toBeCloseTo(tolerance, 9);
  });

  it("zero speed produces zero blur", () => {
    expect(motionBlurPixels(0, 0.002, 2)).toBe(0);
  });

  it("returns 0 for invalid inputs", () => {
    expect(motionBlurPixels(5, 0.002, 0)).toBe(0);
    expect(motionBlurPixels(5, 0, 2)).toBe(0);
    expect(motionBlurPixels(-5, 0.002, 2)).toBe(0);
  });
});
