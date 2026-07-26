/**
 * @module protocol/param-display.test
 * @license GPL-3.0-only
 */

import { describe, it, expect } from "vitest";
import {
  decodeBitmaskFlags,
  summarizeBitmask,
  formatParamDisplayValue,
} from "../param-display";
import type { ParamMetadata } from "../param-metadata";

const bm = new Map<number, string>([
  [0, "Double notch"],
  [1, "Dynamic harmonic"],
  [2, "Update at loop rate"],
  [3, "EnableOnAllIMUs"],
]);

describe("decodeBitmaskFlags", () => {
  it("returns labels for set documented bits", () => {
    const { set, unknownBits } = decodeBitmaskFlags(5, bm); // bits 0 + 2
    expect(set).toEqual(["Double notch", "Update at loop rate"]);
    expect(unknownBits).toEqual([]);
  });

  it("reports bits that are set but undocumented", () => {
    const value = 5 | (1 << 20);
    const { set, unknownBits } = decodeBitmaskFlags(value, bm);
    expect(set).toEqual(["Double notch", "Update at loop rate"]);
    expect(unknownBits).toEqual([20]);
  });
});

describe("summarizeBitmask", () => {
  it("renders 0 as 0", () => {
    expect(summarizeBitmask(0, bm)).toBe("0");
  });
  it("joins a few labels with the raw value", () => {
    expect(summarizeBitmask(5, bm)).toBe("Double notch, Update at loop rate (5)");
  });
  it("collapses many labels to an overflow count", () => {
    expect(summarizeBitmask(15, bm)).toBe("Double notch, Dynamic harmonic +2 (15)");
  });
  it("counts unknown set bits in the overflow", () => {
    const value = 1 | (1 << 20); // bit0 documented + bit20 unknown
    expect(summarizeBitmask(value, bm)).toContain("bit20");
  });
});

describe("formatParamDisplayValue", () => {
  it("summarizes bitmask params", () => {
    const meta = { name: "X", humanName: "", description: "", bitmask: bm } as ParamMetadata;
    expect(formatParamDisplayValue(5, meta)).toBe("Double notch, Update at loop rate (5)");
  });
  it("labels enum params", () => {
    const meta = {
      name: "FLTMODE1", humanName: "", description: "",
      values: new Map([[5, "Loiter"]]),
    } as ParamMetadata;
    expect(formatParamDisplayValue(5, meta)).toBe("5 — Loiter");
  });
  it("falls back to the numeric string", () => {
    expect(formatParamDisplayValue(42)).toBe("42");
  });
});
