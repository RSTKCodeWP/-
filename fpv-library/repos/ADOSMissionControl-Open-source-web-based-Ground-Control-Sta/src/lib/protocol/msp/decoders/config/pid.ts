/**
 * MSP PID and rate decoders.
 *
 * @module protocol/msp/decoders/config/pid
 */

import { readU8, readU16 } from '../../msp-decode-utils';

export interface MspPidSet {
  p: number;
  i: number;
  d: number;
}

export interface MspPid {
  pids: MspPidSet[];
}

export interface MspRcTuning {
  rcRate: number;
  rcExpo: number;
  rollRate: number;
  pitchRate: number;
  yawRate: number;
  throttleMid: number;
  throttleExpo: number;
  rcYawExpo: number;
  rcYawRate: number;
  rcPitchRate: number;
  rcPitchExpo: number;
  throttleLimitType: number;
  throttleLimitPercent: number;
  rollRateLimit: number;
  pitchRateLimit: number;
  yawRateLimit: number;
  ratesType: number;
}

/**
 * MSP_PID (112)
 * 3 U8s per axis (P, I, D). Typically 10 axes (30 bytes).
 */
export function decodeMspPid(dv: DataView): MspPid {
  const axisCount = dv.byteLength / 3;
  const pids: MspPidSet[] = [];
  for (let i = 0; i < axisCount; i++) {
    const off = i * 3;
    pids.push({
      p: readU8(dv, off),
      i: readU8(dv, off + 1),
      d: readU8(dv, off + 2),
    });
  }
  return { pids };
}

/**
 * MSP_RC_TUNING (111)
 *
 * Layout (API >=1.43, <1.45 for deprecated fields):
 *   U8  rcRate (/100)
 *   U8  rcExpo (/100)
 *   U8  rollRate (/100)
 *   U8  pitchRate (/100)
 *   U8  yawRate (/100)
 *   U8  dynamicThrPid (/100) deprecated, skip
 *   U8  throttleMid (/100)
 *   U8  throttleExpo (/100)
 *   U16 dynamicThrBreakpoint deprecated, skip
 *   U8  rcYawExpo (/100)
 *   U8  rcYawRate (/100)
 *   U8  rcPitchRate (/100)
 *   U8  rcPitchExpo (/100)
 *   U8  throttleLimitType
 *   U8  throttleLimitPercent
 *   U16 rollRateLimit
 *   U16 pitchRateLimit
 *   U16 yawRateLimit
 *   U8  ratesType
 */
export function decodeMspRcTuning(dv: DataView): MspRcTuning {
  return {
    rcRate: readU8(dv, 0) / 100,
    rcExpo: readU8(dv, 1) / 100,
    rollRate: readU8(dv, 2) / 100,
    pitchRate: readU8(dv, 3) / 100,
    yawRate: readU8(dv, 4) / 100,
    // offset 5 = dynamicThrPid (skipped)
    throttleMid: readU8(dv, 6) / 100,
    throttleExpo: readU8(dv, 7) / 100,
    // offset 8-9 = dynamicThrBreakpoint (U16, skipped)
    rcYawExpo: readU8(dv, 10) / 100,
    rcYawRate: readU8(dv, 11) / 100,
    rcPitchRate: readU8(dv, 12) / 100,
    rcPitchExpo: readU8(dv, 13) / 100,
    throttleLimitType: readU8(dv, 14),
    throttleLimitPercent: readU8(dv, 15),
    rollRateLimit: readU16(dv, 16),
    pitchRateLimit: readU16(dv, 18),
    yawRateLimit: readU16(dv, 20),
    ratesType: readU8(dv, 22),
  };
}
