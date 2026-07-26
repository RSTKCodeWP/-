/**
 * @module fc/parameters/param-filter.test
 * @license GPL-3.0-only
 */

import { describe, it, expect } from "vitest";
import { paramMatchesFilter, buildSearchHaystack } from "../parameter-grid-utils";
import type { ParamMetadata } from "@/lib/protocol/param-metadata";

const hnt: ParamMetadata = {
  name: "INS_HNTCH_OPTS",
  humanName: "Harmonic Notch Filter options",
  description: "Harmonic Notch Filter options.",
  bitmask: new Map([[0, "Double notch"], [2, "Update at loop rate"]]),
};
const fltmode: ParamMetadata = {
  name: "FLTMODE1",
  humanName: "Flight Mode 1",
  description: "",
  values: new Map([[5, "Loiter"]]),
};

describe("paramMatchesFilter", () => {
  it("matches the parameter name", () => {
    expect(paramMatchesFilter("INS_HNTCH_OPTS", hnt, "hntch")).toBe(true);
  });
  it("matches a bitmask bit label", () => {
    expect(paramMatchesFilter("INS_HNTCH_OPTS", hnt, "double notch")).toBe(true);
  });
  it("matches an enum value label", () => {
    expect(paramMatchesFilter("FLTMODE1", fltmode, "loiter")).toBe(true);
  });
  it("matches the human name", () => {
    expect(paramMatchesFilter("FLTMODE1", fltmode, "flight mode")).toBe(true);
  });
  it("returns false when nothing matches", () => {
    expect(paramMatchesFilter("FLTMODE1", fltmode, "zzz")).toBe(false);
  });
});

describe("buildSearchHaystack", () => {
  it("folds labels into a lowercased haystack", () => {
    const meta = new Map([["INS_HNTCH_OPTS", hnt]]);
    const hay = buildSearchHaystack(meta, ["INS_HNTCH_OPTS"]);
    const s = hay.get("INS_HNTCH_OPTS")!;
    expect(s).toContain("double notch");
    expect(s).toContain("update at loop rate");
    expect(s).toBe(s.toLowerCase());
  });
});
