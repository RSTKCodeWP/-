/**
 * @module protocol/param-metadata-provider.test
 * @license GPL-3.0-only
 */

import { describe, it, expect } from "vitest";
import { mergeMeta, mergeMetaMaps } from "../param-metadata/merge";
import { parseParamXml } from "../param-metadata/ardupilot";
import type { ParamMetadata } from "../param-metadata/types";

describe("mergeMeta", () => {
  it("layers overlay fields over the base without losing base fields", () => {
    const base: ParamMetadata = {
      name: "X", humanName: "x", description: "d",
      bitmask: new Map([[0, "A"], [1, "B"]]),
    };
    const overlay: ParamMetadata = {
      name: "X", humanName: "x", description: "d",
      range: { min: 0, max: 10 }, defaultValue: 3,
    };
    const out = mergeMeta(base, overlay);
    expect(out.range).toEqual({ min: 0, max: 10 });
    expect(out.defaultValue).toBe(3);
    expect(out.bitmask?.get(0)).toBe("A"); // base label preserved
  });

  it("does not let an empty overlay Map wipe the base Map", () => {
    const base: ParamMetadata = {
      name: "X", humanName: "", description: "",
      bitmask: new Map([[0, "A"]]),
    };
    const overlay: ParamMetadata = {
      name: "X", humanName: "", description: "", bitmask: new Map(),
    };
    expect(mergeMeta(base, overlay).bitmask?.get(0)).toBe("A");
  });
});

describe("mergeMetaMaps", () => {
  it("adds overlay-only params and field-merges shared ones", () => {
    const base = new Map<string, ParamMetadata>([
      ["A", { name: "A", humanName: "", description: "", units: "m" }],
    ]);
    const overlay = new Map<string, ParamMetadata>([
      ["A", { name: "A", humanName: "", description: "", range: { min: 0, max: 1 } }],
      ["B", { name: "B", humanName: "", description: "" }],
    ]);
    const out = mergeMetaMaps(base, overlay);
    expect(out.get("A")?.units).toBe("m");
    expect(out.get("A")?.range).toEqual({ min: 0, max: 1 });
    expect(out.has("B")).toBe(true);
  });
});

describe("parseParamXml — float enum codes", () => {
  it("preserves non-integer enum codes (does not collapse 0.1 to 0)", () => {
    const xml = `<paramfile><vehicles><parameters>
      <param name="ArduCopter:ACRO_RP_EXPO" humanName="Acro Expo"
             Values="0:Disabled,0.1:Very Low,0.2:Low,0.3:Medium" />
    </parameters></vehicles></paramfile>`;
    const map = parseParamXml(xml);
    const meta = map.get("ACRO_RP_EXPO");
    expect(meta).toBeDefined();
    expect(meta!.values?.size).toBe(4); // not collapsed
    expect(meta!.values?.get(0.1)).toBe("Very Low");
    expect(meta!.values?.get(0.2)).toBe("Low");
  });

  it("parses a Bitmask attribute into bit→label", () => {
    const xml = `<paramfile><vehicles><parameters>
      <param name="INS_HNTCH_OPTS" Bitmask="0:Double notch,1:Dynamic harmonic,2:Update at loop rate,3:EnableOnAllIMUs" />
    </parameters></vehicles></paramfile>`;
    const meta = parseParamXml(xml).get("INS_HNTCH_OPTS");
    expect(meta!.bitmask?.get(0)).toBe("Double notch");
    expect(meta!.bitmask?.get(3)).toBe("EnableOnAllIMUs");
  });
});
