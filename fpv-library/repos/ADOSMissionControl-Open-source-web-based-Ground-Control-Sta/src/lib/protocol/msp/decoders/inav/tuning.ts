/**
 * iNav tuning decoders: rate profile, rate dynamics, EZ-Tune, MC braking,
 * and per-axis PID gains.
 *
 * @module protocol/msp/decoders/inav/tuning
 */

import { readU8, readU16 } from "./helpers";
import type {
  INavRateProfile,
  INavMcBraking,
  INavPid,
  INavRateDynamics,
  INavEzTune,
} from "./types";

// ── iNav RATE PROFILE decoder ────────────────────────────────

/**
 * MSP2_INAV_RATE_PROFILE (0x2007)
 *
 * U8  throttleMid
 * U8  throttleExpo
 * U8  dynamicThrottlePid
 * U8  rcRateRoll
 * U8  rcRatePitch
 * U8  rcRateYaw
 * U8  rcExpoRoll
 * U8  rcExpoPitch
 * U8  rcExpoYaw
 * U8  rateRoll
 * U8  ratePitch
 * U8  rateYaw
 */
export function decodeMspINavRateProfile(dv: DataView): INavRateProfile {
  return {
    throttleMid: readU8(dv, 0),
    throttleExpo: dv.byteLength > 1 ? readU8(dv, 1) : 0,
    dynamicThrottlePid: dv.byteLength > 2 ? readU8(dv, 2) : 0,
    rcRateRoll: dv.byteLength > 3 ? readU8(dv, 3) : 0,
    rcRatePitch: dv.byteLength > 4 ? readU8(dv, 4) : 0,
    rcRateYaw: dv.byteLength > 5 ? readU8(dv, 5) : 0,
    rcExpoRoll: dv.byteLength > 6 ? readU8(dv, 6) : 0,
    rcExpoPitch: dv.byteLength > 7 ? readU8(dv, 7) : 0,
    rcExpoYaw: dv.byteLength > 8 ? readU8(dv, 8) : 0,
    rateRoll: dv.byteLength > 9 ? readU8(dv, 9) : 0,
    ratePitch: dv.byteLength > 10 ? readU8(dv, 10) : 0,
    rateYaw: dv.byteLength > 11 ? readU8(dv, 11) : 0,
  };
}

// ── iNav MC BRAKING decoder ──────────────────────────────────

/**
 * MSP2_INAV_MC_BRAKING (0x200b)
 *
 * U16 speedThreshold (cm/s)
 * U16 disengageSpeed (cm/s)
 * U16 timeout (ms)
 * U8  boostFactor
 * U16 boostTimeout (ms)
 * U16 boostSpeedThreshold (cm/s)
 * U16 boostDisengage (cm/s)
 * U8  bankAngle (degrees)
 */
export function decodeMspINavMcBraking(dv: DataView): INavMcBraking {
  return {
    speedThreshold: readU16(dv, 0),
    disengageSpeed: dv.byteLength > 3 ? readU16(dv, 2) : 0,
    timeout: dv.byteLength > 5 ? readU16(dv, 4) : 0,
    boostFactor: dv.byteLength > 6 ? readU8(dv, 6) : 0,
    boostTimeout: dv.byteLength > 8 ? readU16(dv, 7) : 0,
    boostSpeedThreshold: dv.byteLength > 10 ? readU16(dv, 9) : 0,
    boostDisengage: dv.byteLength > 12 ? readU16(dv, 11) : 0,
    bankAngle: dv.byteLength > 13 ? readU8(dv, 13) : 0,
  };
}

// ── iNav PID decoder ─────────────────────────────────────────

/**
 * MSP2_INAV_PID (0x2030)
 *
 * Repeated per axis (5 bytes each):
 *   U8 P
 *   U8 I
 *   U8 D
 *   U8 FF
 *   (axis index is the iteration index: 0=ROLL...9=VEL_Z)
 *
 * Axes: 0=ROLL, 1=PITCH, 2=YAW, 3=POS_Z, 4=POS_XY, 5=VEL_XY,
 *       6=SURFACE, 7=LEVEL, 8=HEADING, 9=VEL_Z
 */
export function decodeMspINavPid(dv: DataView): INavPid[] {
  const result: INavPid[] = [];
  let offset = 0;
  let axis = 0;
  while (offset + 3 < dv.byteLength) {
    result.push({
      axis,
      P: readU8(dv, offset),
      I: readU8(dv, offset + 1),
      D: readU8(dv, offset + 2),
      FF: dv.byteLength > offset + 3 ? readU8(dv, offset + 3) : 0,
    });
    offset += 4;
    axis++;
  }
  return result;
}

// ── iNav RATE DYNAMICS decoder ────────────────────────────────

/**
 * MSP2_INAV_RATE_DYNAMICS (0x2060)
 *
 * U8 sensitivityRoll
 * U8 sensitivityPitch
 * U8 sensitivityYaw
 * U8 correctionRoll
 * U8 correctionPitch
 * U8 correctionYaw
 * U8 weightRoll
 * U8 weightPitch
 * U8 weightYaw
 */
export function decodeMspINavRateDynamics(dv: DataView): INavRateDynamics {
  return {
    sensitivityRoll: readU8(dv, 0),
    sensitivityPitch: dv.byteLength > 1 ? readU8(dv, 1) : 0,
    sensitivityYaw: dv.byteLength > 2 ? readU8(dv, 2) : 0,
    correctionRoll: dv.byteLength > 3 ? readU8(dv, 3) : 0,
    correctionPitch: dv.byteLength > 4 ? readU8(dv, 4) : 0,
    correctionYaw: dv.byteLength > 5 ? readU8(dv, 5) : 0,
    weightRoll: dv.byteLength > 6 ? readU8(dv, 6) : 0,
    weightPitch: dv.byteLength > 7 ? readU8(dv, 7) : 0,
    weightYaw: dv.byteLength > 8 ? readU8(dv, 8) : 0,
  };
}

// ── iNav EZ TUNE decoder ──────────────────────────────────────

/**
 * MSP2_INAV_EZ_TUNE (0x2070)
 *
 * U8  enabled
 * U16 filterHz
 * U8  axisRatio
 * U8  response
 * U8  damping
 * U8  stability
 * U8  aggressiveness
 * U8  rate
 * U8  expo
 * U8  snappiness
 */
export function decodeMspINavEzTune(dv: DataView): INavEzTune {
  return {
    enabled: readU8(dv, 0) !== 0,
    filterHz: dv.byteLength > 2 ? readU16(dv, 1) : 0,
    axisRatio: dv.byteLength > 3 ? readU8(dv, 3) : 0,
    response: dv.byteLength > 4 ? readU8(dv, 4) : 0,
    damping: dv.byteLength > 5 ? readU8(dv, 5) : 0,
    stability: dv.byteLength > 6 ? readU8(dv, 6) : 0,
    aggressiveness: dv.byteLength > 7 ? readU8(dv, 7) : 0,
    rate: dv.byteLength > 8 ? readU8(dv, 8) : 0,
    expo: dv.byteLength > 9 ? readU8(dv, 9) : 0,
    snappiness: dv.byteLength > 10 ? readU8(dv, 10) : 0,
  };
}
