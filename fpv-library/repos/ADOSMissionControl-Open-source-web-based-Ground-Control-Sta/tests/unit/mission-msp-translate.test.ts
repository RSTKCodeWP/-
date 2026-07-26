/**
 * Tests for the iNav waypoint translator.
 *
 * Covers round-trip fidelity, coordinate scaling, altitude conversion,
 * WP numbering, last-WP flag preservation, and unknown command fallback.
 *
 * @license GPL-3.0-only
 */

import { describe, it, expect } from "vitest";
import {
  translateToInavWaypoints,
  translateFromInavWaypoints,
} from "@/lib/mission/inav-translator";
import { INAV_WP_ACTION, INAV_WP_FLAG_LAST } from "@/lib/protocol/msp/msp-decoders-inav";
import type { MissionItem } from "@/lib/protocol/types";

// ── Helpers ──────────────────────────────────────────────────

function missionItem(overrides: Partial<MissionItem> = {}): MissionItem {
  return {
    seq: 0,
    frame: 0,
    command: 16, // WAYPOINT
    current: 0,
    autocontinue: 1,
    param1: 0,
    param2: 0,
    param3: 0,
    param4: 0,
    x: 129700000, // 12.97° lat * 1e7
    y: 775900000, // 77.59° lon * 1e7
    z: 50, // 50 m altitude
    ...overrides,
  };
}

// ── translateToInavWaypoints ─────────────────────────────────

describe("translateToInavWaypoints", () => {
  it("returns empty array for empty input", () => {
    expect(translateToInavWaypoints([])).toEqual([]);
  });

  it("converts lat/lon from int*1e7 to float degrees", () => {
    const wps = translateToInavWaypoints([missionItem()]);
    expect(wps[0].lat).toBeCloseTo(12.97, 5);
    expect(wps[0].lon).toBeCloseTo(77.59, 5);
  });

  it("converts altitude from meters to centimetres", () => {
    const wps = translateToInavWaypoints([missionItem({ z: 100 })]);
    expect(wps[0].altitude).toBe(10000);
  });

  it("numbers waypoints starting from 1", () => {
    const items = [missionItem({ seq: 0 }), missionItem({ seq: 1 }), missionItem({ seq: 2 })];
    const wps = translateToInavWaypoints(items);
    expect(wps.map((w) => w.number)).toEqual([1, 2, 3]);
  });

  it("marks the last waypoint with INAV_WP_FLAG_LAST", () => {
    const items = [missionItem(), missionItem(), missionItem()];
    const wps = translateToInavWaypoints(items);
    expect(wps[wps.length - 1].flag).toBe(INAV_WP_FLAG_LAST);
    expect(wps[0].flag).toBe(0);
    expect(wps[1].flag).toBe(0);
  });

  it("maps MAV_CMD_NAV_WAYPOINT (16) to INAV_WP_ACTION.WAYPOINT", () => {
    const wps = translateToInavWaypoints([missionItem({ command: 16 })]);
    expect(wps[0].action).toBe(INAV_WP_ACTION.WAYPOINT);
  });

  it("maps MAV_CMD_NAV_RETURN_TO_LAUNCH (20) to INAV_WP_ACTION.RTH", () => {
    const wps = translateToInavWaypoints([missionItem({ command: 20 })]);
    expect(wps[0].action).toBe(INAV_WP_ACTION.RTH);
  });

  it("maps MAV_CMD_NAV_LAND (21) to INAV_WP_ACTION.LAND", () => {
    const wps = translateToInavWaypoints([missionItem({ command: 21 })]);
    expect(wps[0].action).toBe(INAV_WP_ACTION.LAND);
  });

  it("carries the LAND elevation (p2) and altitude-datum bit (p3) to the wire", () => {
    // param2 = landing-site elevation (m); param3 bit0 = MSL datum.
    const wps = translateToInavWaypoints([missionItem({ command: 21, param2: 12, param3: 1 })]);
    expect(wps[0].action).toBe(INAV_WP_ACTION.LAND);
    expect(wps[0].p2).toBe(12);
    expect(wps[0].p3 & 1).toBe(1);
  });

  it("maps MAV_CMD_NAV_LOITER_UNLIM (17) to INAV_WP_ACTION.POSHOLD_UNLIM", () => {
    const wps = translateToInavWaypoints([missionItem({ command: 17 })]);
    expect(wps[0].action).toBe(INAV_WP_ACTION.POSHOLD_UNLIM);
  });

  it("maps MAV_CMD_NAV_LOITER_TIME (19) to INAV_WP_ACTION.POSHOLD_TIME", () => {
    const wps = translateToInavWaypoints([missionItem({ command: 19 })]);
    expect(wps[0].action).toBe(INAV_WP_ACTION.POSHOLD_TIME);
  });

  it("maps MAV_CMD_DO_JUMP (177) to INAV_WP_ACTION.JUMP and shifts target to 1-based", () => {
    // MAVLink DO_JUMP param1 is a 0-based seq. iNav JUMP p1 is a 1-based wp number.
    const wps = translateToInavWaypoints([missionItem({ command: 177, param1: 3, param2: 2 })]);
    expect(wps[0].action).toBe(INAV_WP_ACTION.JUMP);
    expect(wps[0].p1).toBe(4);
    expect(wps[0].p2).toBe(2);
  });

  it("maps MAV_CMD_DO_SET_ROI (201) to INAV_WP_ACTION.SET_POI", () => {
    const wps = translateToInavWaypoints([missionItem({ command: 201 })]);
    expect(wps[0].action).toBe(INAV_WP_ACTION.SET_POI);
  });

  it("maps MAV_CMD_CONDITION_YAW (115) to INAV_WP_ACTION.SET_HEAD", () => {
    const wps = translateToInavWaypoints([missionItem({ command: 115, param1: 90 })]);
    expect(wps[0].action).toBe(INAV_WP_ACTION.SET_HEAD);
    expect(wps[0].p1).toBe(90);
  });

  it("falls back to WAYPOINT for unknown MAV_CMD", () => {
    const wps = translateToInavWaypoints([missionItem({ command: 9999 })]);
    expect(wps[0].action).toBe(INAV_WP_ACTION.WAYPOINT);
  });
});

// ── translateFromInavWaypoints ───────────────────────────────

describe("translateFromInavWaypoints", () => {
  it("returns empty array for empty input", () => {
    expect(translateFromInavWaypoints([])).toEqual([]);
  });

  it("converts lat/lon from float degrees to int*1e7", () => {
    const wp = {
      number: 1, action: INAV_WP_ACTION.WAYPOINT,
      lat: 12.97, lon: 77.59, altitude: 5000,
      p1: 0, p2: 0, p3: 0, flag: 0,
    };
    const items = translateFromInavWaypoints([wp]);
    expect(items[0].x).toBe(Math.round(12.97 * 1e7));
    expect(items[0].y).toBe(Math.round(77.59 * 1e7));
  });

  it("converts altitude from centimetres to meters", () => {
    const wp = {
      number: 1, action: INAV_WP_ACTION.WAYPOINT,
      lat: 0, lon: 0, altitude: 10000,
      p1: 0, p2: 0, p3: 0, flag: 0,
    };
    const items = translateFromInavWaypoints([wp]);
    expect(items[0].z).toBe(100);
  });

  it("numbers MissionItems with seq starting from 0", () => {
    const wps = [1, 2, 3].map((n) => ({
      number: n, action: INAV_WP_ACTION.WAYPOINT,
      lat: 0, lon: 0, altitude: 0,
      p1: 0, p2: 0, p3: 0, flag: 0,
    }));
    const items = translateFromInavWaypoints(wps);
    expect(items.map((i) => i.seq)).toEqual([0, 1, 2]);
  });

  it("maps INAV_WP_ACTION.WAYPOINT to MAV_CMD_NAV_WAYPOINT (16)", () => {
    const wp = {
      number: 1, action: INAV_WP_ACTION.WAYPOINT,
      lat: 0, lon: 0, altitude: 0,
      p1: 0, p2: 0, p3: 0, flag: 0,
    };
    expect(translateFromInavWaypoints([wp])[0].command).toBe(16);
  });

  it("maps INAV_WP_ACTION.RTH to MAV_CMD_NAV_RETURN_TO_LAUNCH (20)", () => {
    const wp = {
      number: 1, action: INAV_WP_ACTION.RTH,
      lat: 0, lon: 0, altitude: 0,
      p1: 0, p2: 0, p3: 0, flag: 0,
    };
    expect(translateFromInavWaypoints([wp])[0].command).toBe(20);
  });

  it("round-trips a multi-waypoint mission", () => {
    const original: MissionItem[] = [
      missionItem({ seq: 0, command: 16, x: 129700000, y: 775900000, z: 50 }),
      missionItem({ seq: 1, command: 19, x: 129800000, y: 775950000, z: 80, param1: 10 }),
      missionItem({ seq: 2, command: 20, x: 0, y: 0, z: 0 }),
    ];
    const wps = translateToInavWaypoints(original);
    const restored = translateFromInavWaypoints(wps);

    expect(restored).toHaveLength(original.length);
    for (let i = 0; i < original.length; i++) {
      expect(restored[i].command).toBe(original[i].command);
      expect(restored[i].z).toBeCloseTo(original[i].z, 1);
      // lat/lon round-trip: int*1e7 -> float degrees -> int*1e7, max 1 unit rounding error
      expect(Math.abs(restored[i].x - original[i].x)).toBeLessThanOrEqual(1);
      expect(Math.abs(restored[i].y - original[i].y)).toBeLessThanOrEqual(1);
    }
  });
});
