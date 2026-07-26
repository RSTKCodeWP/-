import { describe, expect, it } from "vitest";

import { lerpLngLat, easeOutCubic, PinTweener } from "./tween";

/* Eased pin motion, never teleport (DESIGN-SYSTEM §4.5 hard rule): when a coordinate
 * refines, the pin GLIDES from its old position to the new one. These pure helpers drive
 * that interpolation; the MapView ticks them per frame. */

describe("easeOutCubic", () => {
  it("is 0 at t=0 and 1 at t=1", () => {
    expect(easeOutCubic(0)).toBe(0);
    expect(easeOutCubic(1)).toBe(1);
  });

  it("decelerates (past the midpoint of progress by t=0.5)", () => {
    expect(easeOutCubic(0.5)).toBeGreaterThan(0.5);
  });
});

describe("lerpLngLat", () => {
  it("returns the start at t=0 and the end at t=1", () => {
    expect(lerpLngLat([-88, 30], [-87, 31], 0)).toEqual([-88, 30]);
    expect(lerpLngLat([-88, 30], [-87, 31], 1)).toEqual([-87, 31]);
  });

  it("interpolates linearly in between", () => {
    expect(lerpLngLat([-88, 30], [-86, 32], 0.5)).toEqual([-87, 31]);
  });
});

describe("PinTweener", () => {
  it("a first sighting appears in place (no glide from nowhere)", () => {
    const tw = new PinTweener(400);
    tw.setTarget(1, [-88, 30], 0);
    expect(tw.positionAt(1, 0)).toEqual([-88, 30]);
    expect(tw.active).toBe(false);
  });

  it("a refined coordinate GLIDES (does not teleport) and lands on the new fix", () => {
    const tw = new PinTweener(400);
    tw.setTarget(1, [-88, 30], 0); // appear
    tw.setTarget(1, [-87, 31], 0); // refine
    expect(tw.active).toBe(true);
    const mid = tw.positionAt(1, 200)!; // partway
    expect(mid[0]).toBeGreaterThan(-88);
    expect(mid[0]).toBeLessThan(-87);
    const end = tw.positionAt(1, 400)!; // arrived
    expect(end).toEqual([-87, 31]);
    expect(tw.active).toBe(false);
  });

  it("a new fix mid-glide RETARGETS from the current point (never stacks)", () => {
    const tw = new PinTweener(400);
    tw.setTarget(1, [-88, 30], 0);
    tw.setTarget(1, [-86, 30], 0); // glide toward -86
    const mid = tw.positionAt(1, 200)!; // somewhere between -88 and -86
    tw.setTarget(1, [-90, 30], 200); // new fix mid-glide → retarget from `mid`
    const after = tw.positionAt(1, 200)!;
    expect(after).toEqual(mid); // starts the new glide at the current point, no jump
    const end = tw.positionAt(1, 600)!;
    expect(end[0]).toBeCloseTo(-90, 5);
  });
});
