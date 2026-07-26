/**
 * @module protocol/firmware/px4-flight-mode-slots.test
 * @license GPL-3.0-only
 *
 * PX4 RC mode slots (COM_FLTMODE1..6) hold a small mode-slot enum, NOT the
 * packed HEARTBEAT custom_mode. These golden values come from the PX4 commander
 * mode-slot enum and must never be the packed custom_mode.
 */

import { describe, it, expect } from "vitest";
import {
  px4ModeToSlot,
  px4SlotToMode,
  PX4_MODE_SLOT_UNASSIGNED,
  PX4_SLOT_TO_MODE,
} from "../px4-flight-mode-slots";
import { px4Handler } from "../px4";
import type { UnifiedFlightMode } from "../../types";

describe("PX4 flight-mode slot enum", () => {
  it("maps unified modes to the sourced slot enum value", () => {
    const cases: Array<[UnifiedFlightMode, number]> = [
      ["MANUAL", 0],
      ["ALT_HOLD", 1], // Altitude
      ["POSHOLD", 2], // Position
      ["MISSION", 3],
      ["AUTO", 3], // AUTO resolves to Mission
      ["LOITER", 4], // Hold
      ["RTL", 5], // Return
      ["ACRO", 6],
      ["OFFBOARD", 7],
      ["STABILIZE", 8], // Stabilized
      ["TAKEOFF", 10],
      ["LAND", 11],
      ["FOLLOW_ME", 12],
      ["PRECLAND", 13],
    ];
    for (const [mode, slot] of cases) {
      expect(px4ModeToSlot(mode)).toBe(slot);
    }
  });

  it("slot values are the small enum, never the packed custom_mode", () => {
    // The packed custom_mode for Position (POSCTL) is >> 0xffff; the slot value
    // must be the tiny enum (2), proving we are not writing custom_mode.
    const packed = px4Handler.encodeFlightMode("POSHOLD").customMode;
    expect(packed).toBeGreaterThan(0xffff);
    expect(px4ModeToSlot("POSHOLD")).toBe(2);
    expect(px4ModeToSlot("POSHOLD")).not.toBe(packed);
  });

  it("returns null for modes without a confirmed PX4 slot", () => {
    // Orbit has no COM_FLTMODEx slot value; Rattitude was removed from PX4.
    expect(px4ModeToSlot("ORBIT")).toBeNull();
    expect(px4ModeToSlot("RATTITUDE")).toBeNull();
  });

  it("decodes a slot value read back into the canonical unified mode", () => {
    expect(px4SlotToMode(0)).toBe("MANUAL");
    expect(px4SlotToMode(2)).toBe("POSHOLD");
    expect(px4SlotToMode(3)).toBe("MISSION");
    expect(px4SlotToMode(8)).toBe("STABILIZE");
    expect(px4SlotToMode(11)).toBe("LAND");
  });

  it("treats the unassigned slot and unknown values as no mode", () => {
    expect(PX4_MODE_SLOT_UNASSIGNED).toBe(-1);
    expect(px4SlotToMode(PX4_MODE_SLOT_UNASSIGNED)).toBeNull();
    expect(px4SlotToMode(99)).toBeNull();
  });

  it("round-trips every decode slot back to the same slot value", () => {
    for (const key of Object.keys(PX4_SLOT_TO_MODE)) {
      const slot = Number(key);
      const mode = px4SlotToMode(slot);
      expect(mode).not.toBeNull();
      expect(px4ModeToSlot(mode as UnifiedFlightMode)).toBe(slot);
    }
  });

  it("keeps every slot value in the small enum range, never a packed custom_mode", () => {
    for (const key of Object.keys(PX4_SLOT_TO_MODE)) {
      const slot = Number(key);
      // COM_FLTMODEx slot values are a tiny enum; a packed custom_mode is > 0xffff.
      expect(slot).toBeGreaterThanOrEqual(0);
      expect(slot).toBeLessThan(0xffff);
    }
  });

  it("writes slot values into the COM_FLTMODE1..6 parameters, not the packed FLTMODEn", () => {
    // The panel writes canonical FLTMODE1..6 / FLTMODE_CH; the PX4 name map must
    // route those to COM_FLTMODE1..6 / RC_MAP_FLTMODE so the small slot enum
    // lands in the correct PX4 parameters.
    for (let i = 1; i <= 6; i++) {
      expect(px4Handler.mapParameterName(`FLTMODE${i}`)).toBe(`COM_FLTMODE${i}`);
    }
    expect(px4Handler.mapParameterName("FLTMODE_CH")).toBe("RC_MAP_FLTMODE");
  });
});
