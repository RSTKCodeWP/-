/**
 * Betaflight arming-disable flags decoder.
 *
 * Betaflight reports a 32-bit `armingDisableFlags` word in MSP_STATUS_EX. It is
 * distinct from iNav's arming-flags word (different bit meanings), so it needs
 * its own map. Every set bit is a reason arming is blocked — there is no
 * "OK to arm" bit — so the FC is ready to arm exactly when the word is zero.
 *
 * @module protocol/msp/betaflight-arming-flags
 */

import type { ArmingFlagEntry, DecodeArmingFlagsResult } from "./inav-arming-flags";

/**
 * Bit-position to label map for Betaflight arming-disable flags.
 * Bit 0 is the least-significant bit of the 32-bit word. Every entry is a
 * blocker.
 */
export const BETAFLIGHT_ARMING_DISABLE_FLAGS: Record<number, ArmingFlagEntry> = {
  0:  { name: "NO_GYRO",            label: "No gyro",                  isBlocker: true },
  1:  { name: "FAILSAFE",           label: "Failsafe",                 isBlocker: true },
  2:  { name: "RX_FAILSAFE",        label: "RX failsafe",              isBlocker: true },
  3:  { name: "BAD_RX_RECOVERY",    label: "Bad RX recovery",          isBlocker: true },
  4:  { name: "BOXFAILSAFE",        label: "Box failsafe",             isBlocker: true },
  5:  { name: "RUNAWAY_TAKEOFF",    label: "Runaway takeoff",          isBlocker: true },
  6:  { name: "CRASH_DETECTED",     label: "Crash detected",           isBlocker: true },
  7:  { name: "THROTTLE",           label: "Throttle not low",         isBlocker: true },
  8:  { name: "ANGLE",              label: "Craft not level",          isBlocker: true },
  9:  { name: "BOOT_GRACE_TIME",    label: "Boot grace time",          isBlocker: true },
  10: { name: "NOPREARM",           label: "Pre-arm not set",          isBlocker: true },
  11: { name: "LOAD",               label: "System load too high",     isBlocker: true },
  12: { name: "CALIBRATING",        label: "Sensors calibrating",      isBlocker: true },
  13: { name: "CLI",                label: "CLI active",               isBlocker: true },
  14: { name: "CMS_MENU",           label: "CMS menu open",            isBlocker: true },
  15: { name: "BST",                label: "BST active",               isBlocker: true },
  16: { name: "MSP",                label: "MSP link active",          isBlocker: true },
  17: { name: "PARALYZE",           label: "Paralyze mode",            isBlocker: true },
  18: { name: "GPS",                label: "GPS rescue unavailable",   isBlocker: true },
  19: { name: "RESC",               label: "GPS rescue active",        isBlocker: true },
  20: { name: "RPMFILTER",          label: "RPM filter",               isBlocker: true },
  21: { name: "REBOOT_REQUIRED",    label: "Reboot required",          isBlocker: true },
  22: { name: "DSHOT_BITBANG",      label: "DShot bitbang",            isBlocker: true },
  23: { name: "ACC_CALIBRATION",    label: "Accelerometer not calibrated", isBlocker: true },
  24: { name: "MOTOR_PROTOCOL",     label: "Motor protocol disabled",  isBlocker: true },
  25: { name: "ARM_SWITCH",         label: "Arm switch",               isBlocker: true },
};

/**
 * Decode a 32-bit Betaflight arming-disable bitmask into structured output.
 *
 * Every set bit blocks arming, so `okToArm` is true exactly when no bits are
 * set. `blockers` carries a label per set bit; `notes` is always empty
 * (Betaflight has no informational arming bits, unlike iNav).
 */
export function decodeBetaflightArmingFlags(
  bitmask: number,
): DecodeArmingFlagsResult {
  const blockers: string[] = [];
  for (let bit = 0; bit < 32; bit++) {
    if ((bitmask & (1 << bit)) === 0) continue;
    const entry = BETAFLIGHT_ARMING_DISABLE_FLAGS[bit];
    blockers.push(entry ? entry.label : `Unknown flag (bit ${bit})`);
  }
  return { okToArm: bitmask === 0, blockers, notes: [] };
}
