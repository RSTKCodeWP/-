/**
 * Verifies the agent poll backoff curve: a healthy agent stays at the
 * base 3 s cadence, and once it is declared offline the delay ramps
 * geometrically toward a ceiling with jitter, so a dead host is not
 * hammered. The first success resets the failure count, which snaps the
 * cadence straight back to the base.
 *
 * @license GPL-3.0-only
 */

import { describe, it, expect } from "vitest";
import { nextPollDelay } from "@/stores/agent-connection/poll-backoff";

describe("nextPollDelay", () => {
  it("holds the base cadence below the offline threshold", () => {
    for (let f = 0; f < 6; f++) {
      expect(nextPollDelay(f)).toBe(3000);
    }
  });

  it("ramps geometrically once the agent is declared offline", () => {
    // At the threshold the first backoff step is 6 s, then 12 s, 24 s …
    expect(nextPollDelay(6)).toBeGreaterThanOrEqual(6000);
    expect(nextPollDelay(6)).toBeLessThan(7000); // 6s + <1s jitter
    expect(nextPollDelay(7)).toBeGreaterThanOrEqual(12000);
    expect(nextPollDelay(7)).toBeLessThan(13000);
    expect(nextPollDelay(8)).toBeGreaterThanOrEqual(24000);
    expect(nextPollDelay(8)).toBeLessThan(25000);
  });

  it("caps the backoff at the ceiling (plus jitter)", () => {
    // Far past the threshold every step saturates at the 30 s ceiling.
    for (const f of [9, 12, 50, 1000]) {
      const d = nextPollDelay(f);
      expect(d).toBeGreaterThanOrEqual(30000);
      expect(d).toBeLessThan(31000);
    }
  });

  it("monotonically backs off until the cap", () => {
    expect(nextPollDelay(6)).toBeLessThan(nextPollDelay(7));
    expect(nextPollDelay(7)).toBeLessThan(nextPollDelay(8));
  });
});
