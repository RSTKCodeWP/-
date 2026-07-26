/**
 * @license GPL-3.0-only
 */
import { describe, it, expect } from "vitest";
import { isAtEnd, quantizeElapsed } from "@/lib/sim-clock";

describe("isAtEnd", () => {
  it("is true when elapsed exactly equals the total duration", () => {
    expect(isAtEnd(60, 60)).toBe(true);
  });

  it("is true when elapsed is quantized just below the total duration", () => {
    // The clock syncs elapsed at millisecond precision, so a completed run can
    // land a sub-tick fraction below the end. This is the case the run-history
    // completion check must still treat as complete.
    const totalDuration = 47.3334;
    const elapsed = quantizeElapsed(totalDuration); // 47.333, still < totalDuration
    expect(elapsed).toBeLessThan(totalDuration);
    expect(elapsed >= totalDuration).toBe(false); // a strict >= would miss it
    expect(isAtEnd(elapsed, totalDuration)).toBe(true);
  });

  it("is true within the one-millisecond epsilon below the end", () => {
    expect(isAtEnd(59.9995, 60)).toBe(true);
  });

  it("is false partway through the timeline", () => {
    expect(isAtEnd(30, 60)).toBe(false);
    expect(isAtEnd(59.9, 60)).toBe(false);
  });

  it("is false for an empty timeline", () => {
    expect(isAtEnd(0, 0)).toBe(false);
    expect(isAtEnd(0, -0.001)).toBe(false);
  });
});
