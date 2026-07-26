/**
 * Regression tests for the ArduPilot versioned-XML parser used by the
 * per-version snapshot generator. Covers both bitmask representations
 * (field-form and block-form), float enum codes, and range/units.
 *
 * @license GPL-3.0-only
 */

import { describe, it, expect } from "vitest";
import { parsePdefXml } from "../../scripts/param-metadata/_pdef-xml.mjs";

interface Meta {
  name: string;
  values?: [number, string][];
  bitmask?: [number, string][];
  range?: { min: number; max: number };
  units?: string;
  advanced?: boolean;
}

const XML = `<paramfile><vehicles><parameters name="ArduCopter">
  <param humanName="Acro Expo" name="ArduCopter:ACRO_RP_EXPO" documentation="Acro expo." user="Advanced">
    <field name="Values">0:Disabled,0.1:Very Low,0.2:Low</field>
  </param>
  <param humanName="Notch opts" name="ArduCopter:INS_HNTCH_OPTS" documentation="Notch options. More text here." user="Advanced">
    <field name="Bitmask">0:Double notch,1:Multi-Source,2:Update at loop rate</field>
  </param>
  <param humanName="Fence type" name="ArduCopter:FENCE_TYPE" documentation="Fence." user="Standard">
    <bitmask><bit code="0">Max altitude</bit><bit code="1">Circle</bit></bitmask>
  </param>
  <param humanName="RTL Alt" name="ArduCopter:RTL_ALT" documentation="RTL altitude in &amp;quot;cm&amp;quot;." user="Standard">
    <field name="Units">cm</field><field name="Range">200 300000</field>
  </param>
</parameters></vehicles></paramfile>`;

describe("parsePdefXml", () => {
  const params = parsePdefXml(XML) as Meta[];
  const m = new Map(params.map((p) => [p.name, p]));

  it("preserves non-integer enum codes (0.1)", () => {
    const v = new Map(m.get("ACRO_RP_EXPO")!.values);
    expect(v.get(0.1)).toBe("Very Low");
    expect(v.size).toBe(3);
  });

  it("parses the field-form bitmask (comma-separated)", () => {
    const b = new Map(m.get("INS_HNTCH_OPTS")!.bitmask);
    expect(b.get(0)).toBe("Double notch");
    expect(b.get(2)).toBe("Update at loop rate");
  });

  it("parses the block-form bitmask (<bit code=>)", () => {
    const b = new Map(m.get("FENCE_TYPE")!.bitmask);
    expect(b.get(0)).toBe("Max altitude");
    expect(b.get(1)).toBe("Circle");
  });

  it("parses range + units, strips the vehicle prefix, and decodes entities", () => {
    const p = m.get("RTL_ALT")!;
    expect(p.range).toEqual({ min: 200, max: 300000 });
    expect(p.units).toBe("cm");
    expect(p.name).toBe("RTL_ALT");
  });

  it("maps user → advanced", () => {
    expect(m.get("ACRO_RP_EXPO")!.advanced).toBe(true);
    expect(m.get("FENCE_TYPE")!.advanced).toBe(false);
  });
});
