/**
 * @module protocol/firmware/px4.test
 * @license GPL-3.0-only
 *
 * PX4 custom_mode packing. The union (mavros px4_custom_mode.h) is
 * reserved(0-15) | main_mode(16-23) | sub_mode(24-31), so an AUTO submode
 * must land in the top byte. These golden values are computed from that
 * layout, independent of the implementation.
 */

import { describe, it, expect } from "vitest";
import { px4Handler, createPX4Handler } from "../px4";
import { createFirmwareHandler } from "../ardupilot";
import type { UnifiedFlightMode } from "../../types";

// HEARTBEAT enum values (common.xml).
const PX4 = 12; // MAV_AUTOPILOT_PX4
const MAV_TYPE_FIXED_WING = 1;
const MAV_TYPE_QUADROTOR = 2;
const MAV_TYPE_VTOL_TILTROTOR = 24;

// main_mode / sub_mode ids from PX4 commander (px4_custom_mode.h).
const MAIN = { MANUAL: 1, ALTCTL: 2, POSCTL: 3, AUTO: 4, STABILIZED: 7 };
const SUB_AUTO = { TAKEOFF: 2, LOITER: 3, MISSION: 4, RTL: 5, LAND: 6 };

/** The correct packed custom_mode for a (main, sub) pair, per the union. */
function packed(main: number, sub: number): number {
  return ((sub << 24) | (main << 16)) >>> 0;
}

describe("PX4 custom_mode packing", () => {
  it("packs a base mode (sub=0) into bits 16-23", () => {
    const { customMode } = px4Handler.encodeFlightMode("MANUAL");
    expect(customMode).toBe(packed(MAIN.MANUAL, 0));
    expect(customMode).toBe(0x00010000);
  });

  it("packs an AUTO submode into the top byte (bits 24-31), not the low bytes", () => {
    // AUTO.MISSION = main 4, sub 4 -> 0x04040000, NOT 0x00040004.
    const { customMode } = px4Handler.encodeFlightMode("MISSION");
    expect(customMode).toBe(packed(MAIN.AUTO, SUB_AUTO.MISSION));
    expect(customMode).toBe(0x04040000);
    // Guard against the old low-bits regression.
    expect(customMode).not.toBe(0x00040004);
  });

  it.each<[UnifiedFlightMode, number, number]>([
    ["MISSION", MAIN.AUTO, SUB_AUTO.MISSION],
    ["LOITER", MAIN.AUTO, SUB_AUTO.LOITER],
    ["RTL", MAIN.AUTO, SUB_AUTO.RTL],
    ["LAND", MAIN.AUTO, SUB_AUTO.LAND],
    ["TAKEOFF", MAIN.AUTO, SUB_AUTO.TAKEOFF],
  ])("encodes AUTO submode %s to the correct custom_mode", (mode, main, sub) => {
    expect(px4Handler.encodeFlightMode(mode).customMode).toBe(packed(main, sub));
  });

  // These modes have a unique (main, sub) pair so encode -> decode is exact.
  it.each<UnifiedFlightMode>([
    "MANUAL",
    "ALT_HOLD",
    "POSHOLD",
    "STABILIZE",
    "LOITER",
    "RTL",
    "LAND",
    "TAKEOFF",
  ])("round-trips %s through encode -> decode", (mode) => {
    const { customMode } = px4Handler.encodeFlightMode(mode);
    expect(px4Handler.decodeFlightMode(customMode)).toBe(mode);
  });

  it("AUTO and MISSION alias the same custom_mode (main=AUTO, sub=MISSION)", () => {
    // PX4 has no distinct AUTO mode: AUTO main + MISSION sub IS mission/auto.
    // Both encode to the same value; it decodes to the canonical 'AUTO'.
    const missionMode = packed(MAIN.AUTO, SUB_AUTO.MISSION);
    expect(px4Handler.encodeFlightMode("MISSION").customMode).toBe(missionMode);
    expect(px4Handler.encodeFlightMode("AUTO").customMode).toBe(missionMode);
    expect(px4Handler.decodeFlightMode(missionMode)).toBe("AUTO");
  });

  it("decodes a live AUTO.RTL custom_mode from the top byte", () => {
    // What a PX4 HEARTBEAT actually carries for AUTO.RTL.
    expect(px4Handler.decodeFlightMode(packed(MAIN.AUTO, SUB_AUTO.RTL))).toBe("RTL");
  });

  it("decodes an unknown custom_mode to UNKNOWN", () => {
    expect(px4Handler.decodeFlightMode(packed(0x0f, 0x0f))).toBe("UNKNOWN");
  });

  it("createPX4Handler yields the same packing for a plane class", () => {
    const plane = createPX4Handler("plane");
    expect(plane.encodeFlightMode("MISSION").customMode).toBe(
      packed(MAIN.AUTO, SUB_AUTO.MISSION),
    );
  });
});

describe("PX4 vehicle-class classification from HEARTBEAT", () => {
  it("classifies a PX4 fixed-wing as a plane, not a copter", () => {
    expect(createFirmwareHandler(PX4, MAV_TYPE_FIXED_WING).vehicleClass).toBe("plane");
  });

  it("classifies a PX4 VTOL as a vtol", () => {
    expect(createFirmwareHandler(PX4, MAV_TYPE_VTOL_TILTROTOR).vehicleClass).toBe("vtol");
  });

  it("classifies a PX4 multirotor as a copter", () => {
    expect(createFirmwareHandler(PX4, MAV_TYPE_QUADROTOR).vehicleClass).toBe("copter");
  });
});

describe("PX4 supported mission commands", () => {
  it("excludes NAV_SPLINE_WAYPOINT (82, ArduPilot-only)", () => {
    const cmds = createPX4Handler("copter").getSupportedMissionCommands?.() ?? [];
    expect(cmds).not.toContain(82); // spline is ArduPilot-only
    expect(cmds).toContain(16); // NAV_WAYPOINT
    expect(cmds).toContain(93); // NAV_DELAY (was mislabeled as 82)
    expect(cmds).toContain(94); // NAV_PAYLOAD_PLACE
  });

  it("adds the VTOL commands for a plane/VTOL, not a copter", () => {
    const copter = createPX4Handler("copter").getSupportedMissionCommands?.() ?? [];
    const plane = createPX4Handler("plane").getSupportedMissionCommands?.() ?? [];
    expect(copter).not.toContain(84); // NAV_VTOL_TAKEOFF
    expect(plane).toContain(84); // NAV_VTOL_TAKEOFF
    expect(plane).toContain(85); // NAV_VTOL_LAND
    expect(plane).toContain(189); // DO_LAND_START
  });
});
