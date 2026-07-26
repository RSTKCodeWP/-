/**
 * PX4 control-allocation constants tests.
 *
 * @license GPL-3.0-only
 */

import { describe, it, expect } from "vitest";
import {
  CA_ALL_PARAM_NAMES,
  CA_R_REV_BITS,
  CA_MAX_ROTORS,
  CA_MAX_SURFACES,
  CA_MAX_TILTS,
  caRotorFields,
  caSurfaceFields,
  caTiltFields,
} from "@/components/fc/px4/px4-control-allocation-constants";

describe("PX4 control-allocation constants", () => {
  it("builds the full CA_* param list without duplicates", () => {
    const set = new Set(CA_ALL_PARAM_NAMES);
    expect(set.size).toBe(CA_ALL_PARAM_NAMES.length); // no dupes
    for (const n of ["CA_AIRFRAME", "CA_METHOD", "CA_R_REV", "CA_ROTOR_COUNT", "CA_SV_CS_COUNT", "CA_SV_TL_COUNT"]) {
      expect(set.has(n)).toBe(true);
    }
    // one indexed slot per section present
    expect(set.has("CA_ROTOR0_CT")).toBe(true);
    expect(set.has(`CA_ROTOR${CA_MAX_ROTORS - 1}_KM`)).toBe(true);
    expect(set.has(`CA_SV_CS${CA_MAX_SURFACES - 1}_TYPE`)).toBe(true);
    expect(set.has(`CA_SV_TL${CA_MAX_TILTS - 1}_TD`)).toBe(true);
  });

  it("uses the per-motor slew name (CA_R{i}_SLEW), not CA_ROTOR{i}_SLEW", () => {
    const names = caRotorFields(3).map((f) => f.param);
    expect(names).toContain("CA_R3_SLEW");
    expect(names).toContain("CA_ROTOR3_CT");
    expect(names).not.toContain("CA_ROTOR3_SLEW");
  });

  it("marks enum fields for the params the metadata carries as enums", () => {
    expect(caRotorFields(0).find((f) => f.param === "CA_ROTOR0_TILT")?.kind).toBe("enum");
    expect(caSurfaceFields(0).find((f) => f.param === "CA_SV_CS0_TYPE")?.kind).toBe("enum");
    expect(caTiltFields(0).find((f) => f.param === "CA_SV_TL0_TD")?.kind).toBe("enum");
    expect(caTiltFields(0).find((f) => f.param === "CA_SV_TL0_CT")?.kind).toBe("enum");
  });

  it("labels CA_R_REV bits as Motor 1..12", () => {
    expect(CA_R_REV_BITS.size).toBe(12);
    expect(CA_R_REV_BITS.get(0)).toBe("Motor 1");
    expect(CA_R_REV_BITS.get(11)).toBe("Motor 12");
  });
});
