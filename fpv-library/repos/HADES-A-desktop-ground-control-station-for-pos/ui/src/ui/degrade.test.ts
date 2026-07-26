import { describe, expect, it } from "vitest";

import { effectiveLocConf, isContactStale } from "./degrade";

/* Degrade-visibly (impl-plan Task 5.7c / M12). Localization confidence is DYNAMICALLY
 * coupled to telemetry freshness: as the pose goes stale, a contact's localization can no
 * longer be trusted, so its EFFECTIVE confidence visibly collapses (not a static value).
 * This is the anti-smug-filter guard at the UI layer. */

describe("effectiveLocConf", () => {
  it("equals the reported confidence when telemetry is fresh", () => {
    expect(effectiveLocConf(0.8, 0.2)).toBeCloseTo(0.8, 5);
  });

  it("collapses toward zero as telemetry ages past the stale threshold", () => {
    const fresh = effectiveLocConf(0.8, 0.2);
    const aging = effectiveLocConf(0.8, 2.5);
    const stale = effectiveLocConf(0.8, 8);
    expect(aging).toBeLessThan(fresh);
    expect(stale).toBeLessThan(aging);
    expect(stale).toBeLessThan(0.1); // essentially "do not trust this fix"
  });

  it("never goes negative", () => {
    expect(effectiveLocConf(0.8, 1000)).toBeGreaterThanOrEqual(0);
  });
});

describe("isContactStale", () => {
  it("is true once telemetry passes the stale threshold", () => {
    expect(isContactStale(0.3)).toBe(false);
    expect(isContactStale(8)).toBe(true);
  });
});
