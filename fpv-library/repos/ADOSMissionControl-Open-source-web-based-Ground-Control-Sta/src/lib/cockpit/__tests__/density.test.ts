import { describe, expect, it } from "vitest";

import {
  COCKPIT_DENSITIES,
  DEFAULT_DENSITY,
  isCockpitDensity,
} from "@/lib/cockpit/density";

describe("cockpit density", () => {
  it("defaults to standard and lists the three modes in order", () => {
    expect(DEFAULT_DENSITY).toBe("standard");
    expect(COCKPIT_DENSITIES).toEqual(["minimal", "standard", "full"]);
    expect(COCKPIT_DENSITIES).toContain(DEFAULT_DENSITY);
  });

  it("accepts only the known density modes", () => {
    expect(isCockpitDensity("minimal")).toBe(true);
    expect(isCockpitDensity("standard")).toBe(true);
    expect(isCockpitDensity("full")).toBe(true);
  });

  it("rejects unknown, wrong-type, and nullish values", () => {
    expect(isCockpitDensity("dense")).toBe(false);
    expect(isCockpitDensity("")).toBe(false);
    expect(isCockpitDensity(2)).toBe(false);
    expect(isCockpitDensity(null)).toBe(false);
    expect(isCockpitDensity(undefined)).toBe(false);
  });
});
