/**
 * Chip-family detection for ArduPilot board IDs.
 *
 * Used by the SLCAN flash arbiter to decide whether entering SLCAN mode
 * requires a reboot (F4: yes) or whether the firmware supports a
 * hot-switch via MAV_CMD_CAN_FORWARD on the same MAVLink link (F7/H7/G4).
 *
 * The mapping is sourced from the project's local board registry where a
 * row exists; for boards not in the registry we fall back to a small
 * hand-rolled table of common board IDs and finally to a conservative
 * "F4" default so unknown boards take the reboot path.
 *
 * @module lib/board-profiles/family
 * @license GPL-3.0-only
 */

import { findArduPilotBoard } from "../boards/ardupilot-boards";

/** Known chip families that affect SLCAN entry strategy. */
export type ChipFamily = "F4" | "F7" | "H7" | "G4" | "unknown";

/**
 * Common ArduPilot board IDs paired with their chip family. Used when the
 * registry does not have a row for the board (e.g. legacy reference boards
 * that the GCS never carried timer-group data for).
 */
const FAMILY_BY_BOARD_ID: ReadonlyMap<number, ChipFamily> = new Map([
  // ── F4 ──
  [5, "F4"], // Pixhawk 1
  [9, "F4"], // CubeBlack-ish reference (F427)
  [140, "F4"], // legacy SpeedyBee variants — F4
  [142, "F4"],
  [143, "F4"],

  // ── F7 ──
  [50, "F7"], // Pixhawk 4 / FMUv5
  [52, "F7"], // Kakute F7
  [15, "F7"], // MatekF765

  // ── H7 ──
  [53, "H7"], // Pixhawk 6C
  [54, "H7"], // Pixhawk 6X
  [1009, "H7"], // MatekH743 (variant)
  [1063, "H7"], // CubeOrange / CubeOrangePlus references
]);

/**
 * Map an MCU string from the board registry onto a chip family.
 * The registry uses values like "STM32F405", "STM32F745", "STM32H743".
 */
function familyFromMcu(mcu: string): ChipFamily {
  if (/H7\d\d/i.test(mcu)) return "H7";
  if (/F7\d\d/i.test(mcu)) return "F7";
  if (/G4\d\d/i.test(mcu)) return "G4";
  if (/F4\d\d|F303/i.test(mcu)) return "F4";
  return "unknown";
}

/**
 * Resolve the chip family for an AP_FW_BOARD_ID.
 *
 * Strategy:
 *   1. If the board registry has a row, derive the family from its MCU
 *      field. The registry is the source of truth.
 *   2. Otherwise consult the hand-rolled common-board table above.
 *   3. Otherwise return "F4" as a conservative default — assume reboot is
 *      required so we never accidentally try a hot-switch on hardware that
 *      cannot handle it.
 */
export function detectChipFamily(boardId: number): ChipFamily {
  const entry = findArduPilotBoard(boardId);
  if (entry) {
    const fromRegistry = familyFromMcu(entry.mcu);
    if (fromRegistry !== "unknown") return fromRegistry;
  }
  const fallback = FAMILY_BY_BOARD_ID.get(boardId);
  if (fallback) return fallback;
  return "F4";
}

/**
 * True when entering SLCAN mode on this chip family requires a full FC
 * reboot to take effect. F4 builds re-route the CAN driver only on boot;
 * F7/H7/G4 builds can switch into CAN passthrough via MAV_CMD_CAN_FORWARD
 * on a live MAVLink link without a reboot.
 */
export function chipFamilyRequiresReboot(family: ChipFamily): boolean {
  return family === "F4" || family === "unknown";
}
