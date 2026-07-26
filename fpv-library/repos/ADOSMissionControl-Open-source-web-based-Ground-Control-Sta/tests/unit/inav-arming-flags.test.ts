/**
 * Unit tests for decodeArmingFlags.
 * @license GPL-3.0-only
 */

import { describe, it, expect } from "vitest";
import { decodeArmingFlags } from "@/lib/protocol/msp/inav-arming-flags";

describe("decodeArmingFlags", () => {
  it("returns okToArm=true when bit 0 is set and no blockers are active", () => {
    const result = decodeArmingFlags(0b0001); // bit 0 only
    expect(result.okToArm).toBe(true);
    expect(result.blockers).toHaveLength(0);
  });

  it("returns okToArm=false when bit 0 is clear", () => {
    const result = decodeArmingFlags(0b0000);
    expect(result.okToArm).toBe(false);
  });

  it("returns okToArm=false when a blocker bit is set even if bit 0 is also set", () => {
    // bit 0 (OK_TO_ARM) + bit 8 (NOT_LEVEL)
    const result = decodeArmingFlags((1 << 0) | (1 << 8));
    expect(result.okToArm).toBe(false);
    expect(result.blockers).toContain("Not level");
  });

  it("decodes multiple blockers correctly", () => {
    // bit 8 (NOT_LEVEL) + bit 9 (SENSORS_CALIBRATING) + bit 18 (RC_LINK)
    const mask = (1 << 8) | (1 << 9) | (1 << 18);
    const result = decodeArmingFlags(mask);
    expect(result.blockers).toContain("Not level");
    expect(result.blockers).toContain("Sensors calibrating");
    expect(result.blockers).toContain("RC link");
    expect(result.blockers).toHaveLength(3);
  });

  it("puts ARMED bit into notes, not blockers", () => {
    // bit 2 (ARMED) + bit 0 (OK_TO_ARM)
    const result = decodeArmingFlags((1 << 2) | (1 << 0));
    expect(result.notes).toContain("Armed");
    expect(result.blockers).toHaveLength(0);
  });

  it("does not add bit 0 label to notes (handled separately)", () => {
    const result = decodeArmingFlags(0b0001);
    expect(result.notes).not.toContain("OK to arm");
  });

  it("returns empty blockers and notes for zero bitmask", () => {
    const result = decodeArmingFlags(0);
    expect(result.blockers).toHaveLength(0);
    expect(result.notes).toHaveLength(0);
    expect(result.okToArm).toBe(false);
  });

  it("decodes PREVENT_ARMING bit as a blocker", () => {
    const result = decodeArmingFlags(1 << 1);
    expect(result.blockers).toContain("Arming prevented");
  });

  it("decodes SIMULATOR_MODE into notes", () => {
    const result = decodeArmingFlags((1 << 4) | (1 << 0));
    expect(result.notes).toContain("Simulator mode");
  });

  it("ignores unknown bit positions gracefully", () => {
    // bit 31 has no entry in INAV_ARMING_FLAGS
    const result = decodeArmingFlags((1 << 31) >>> 0);
    expect(result.blockers).toHaveLength(0);
    expect(result.notes).toHaveLength(0);
  });
});
