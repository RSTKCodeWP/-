/**
 * MSP payload encoders for tuning: PID, RC tuning, filters, advanced
 * tuning, and adjustment ranges.
 *
 * @module protocol/msp/encoders/tuning
 */

import { makeBuffer, push8, push16 } from "./helpers";

/**
 * MSP_SET_ADJUSTMENT_RANGE (53)
 * 7 bytes: U8 index, U8 slotIndex, U8 auxChannelIndex, U8 startStep, U8 endStep,
 *          U8 adjustmentFunction, U8 auxSwitchChannelIndex
 * Steps are PWM-to-step: step = (PWM - 900) / 25
 */
export function encodeMspSetAdjustmentRange(
  index: number,
  range: {
    slotIndex: number;
    auxChannelIndex: number;
    rangeStart: number;
    rangeEnd: number;
    adjustmentFunction: number;
    auxSwitchChannelIndex: number;
  },
): Uint8Array {
  const { buf, dv } = makeBuffer(7);
  push8(dv, 0, index);
  push8(dv, 1, range.slotIndex);
  push8(dv, 2, range.auxChannelIndex);
  push8(dv, 3, Math.round((range.rangeStart - 900) / 25));
  push8(dv, 4, Math.round((range.rangeEnd - 900) / 25));
  push8(dv, 5, range.adjustmentFunction);
  push8(dv, 6, range.auxSwitchChannelIndex);
  return buf;
}


/**
 * MSP_SET_PID (202)
 * 3 bytes per axis (P, I, D)
 */
export function encodeMspSetPid(pids: Array<{ p: number; i: number; d: number }>): Uint8Array {
  const { buf, dv } = makeBuffer(pids.length * 3);
  for (let i = 0; i < pids.length; i++) {
    const off = i * 3;
    push8(dv, off, pids[i].p);
    push8(dv, off + 1, pids[i].i);
    push8(dv, off + 2, pids[i].d);
  }
  return buf;
}


/**
 * MSP_SET_RC_TUNING (204)
 *
 * From MSPHelper.js crunch (API >= 1.43):
 *   U8  rcRate (×100)
 *   U8  rcExpo (×100)
 *   U8  rollRate (×100)
 *   U8  pitchRate (×100)
 *   U8  yawRate (×100)
 *   U8  0 (deprecated dynamicThrPid)
 *   U8  throttleMid (×100)
 *   U8  throttleExpo (×100)
 *   U16 0 (deprecated dynamicThrBreakpoint)
 *   U8  rcYawExpo (×100)
 *   U8  rcYawRate (×100)
 *   U8  rcPitchRate (×100)
 *   U8  rcPitchExpo (×100)
 *   U8  throttleLimitType
 *   U8  throttleLimitPercent
 *   U16 rollRateLimit
 *   U16 pitchRateLimit
 *   U16 yawRateLimit
 *   U8  ratesType
 */
export function encodeMspSetRcTuning(tuning: {
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
}): Uint8Array {
  const { buf, dv } = makeBuffer(23);
  push8(dv, 0, Math.round(tuning.rcRate * 100));
  push8(dv, 1, Math.round(tuning.rcExpo * 100));
  push8(dv, 2, Math.round(tuning.rollRate * 100));
  push8(dv, 3, Math.round(tuning.pitchRate * 100));
  push8(dv, 4, Math.round(tuning.yawRate * 100));
  push8(dv, 5, 0); // deprecated dynamicThrPid
  push8(dv, 6, Math.round(tuning.throttleMid * 100));
  push8(dv, 7, Math.round(tuning.throttleExpo * 100));
  push16(dv, 8, 0); // deprecated dynamicThrBreakpoint
  push8(dv, 10, Math.round(tuning.rcYawExpo * 100));
  push8(dv, 11, Math.round(tuning.rcYawRate * 100));
  push8(dv, 12, Math.round(tuning.rcPitchRate * 100));
  push8(dv, 13, Math.round(tuning.rcPitchExpo * 100));
  push8(dv, 14, tuning.throttleLimitType);
  push8(dv, 15, tuning.throttleLimitPercent);
  push16(dv, 16, tuning.rollRateLimit);
  push16(dv, 18, tuning.pitchRateLimit);
  push16(dv, 20, tuning.yawRateLimit);
  push8(dv, 22, tuning.ratesType);
  return buf;
}


/**
 * MSP_SET_FILTER_CONFIG (93)
 *
 * From MSPHelper.js crunch (full layout, API >= 1.44):
 *   U8  gyroLowpassHz (legacy byte)
 *   U16 dtermLowpassHz
 *   U16 yawLowpassHz
 *   U16 gyroNotchHz
 *   U16 gyroNotchCutoff
 *   U16 dtermNotchHz
 *   U16 dtermNotchCutoff
 *   U16 gyroNotch2Hz
 *   U16 gyroNotch2Cutoff
 *   U8  dtermLowpassType
 *   U8  gyroHardwareLpf
 *   U8  0 (unused)
 *   U16 gyroLowpassHz
 *   U16 gyroLowpass2Hz
 *   U8  gyroLowpassType
 *   U8  gyroLowpass2Type
 *   U16 dtermLowpass2Hz
 *   U8  dtermLowpass2Type
 *   U16 gyroLowpassDynMinHz
 *   U16 gyroLowpassDynMaxHz
 *   U16 dtermLowpassDynMinHz
 *   U16 dtermLowpassDynMaxHz
 *   U8  dynNotchRange
 *   U8  dynNotchWidthPercent
 *   U16 dynNotchQ
 *   U16 dynNotchMinHz
 *   U8  gyroRpmNotchHarmonics
 *   U8  gyroRpmNotchMinHz
 *   U16 dynNotchMaxHz
 *   U8  dynLpfCurveExpo
 *   U8  dynNotchCount
 */
export function encodeMspSetFilterConfig(filters: {
  gyroLowpassHz: number;
  dtermLowpassHz: number;
  yawLowpassHz: number;
  gyroNotchHz: number;
  gyroNotchCutoff: number;
  dtermNotchHz: number;
  dtermNotchCutoff: number;
  gyroNotch2Hz: number;
  gyroNotch2Cutoff: number;
  dtermLowpassType: number;
  gyroHardwareLpf: number;
  gyroLowpass2Hz: number;
  gyroLowpassType: number;
  gyroLowpass2Type: number;
  dtermLowpass2Hz: number;
  dtermLowpass2Type: number;
  gyroLowpassDynMinHz: number;
  gyroLowpassDynMaxHz: number;
  dtermLowpassDynMinHz: number;
  dtermLowpassDynMaxHz: number;
  dynNotchRange: number;
  dynNotchWidthPercent: number;
  dynNotchQ: number;
  dynNotchMinHz: number;
  gyroRpmNotchHarmonics: number;
  gyroRpmNotchMinHz: number;
  dynNotchMaxHz: number;
  dynLpfCurveExpo: number;
  dynNotchCount: number;
}): Uint8Array {
  const { buf, dv } = makeBuffer(49);
  push8(dv, 0, filters.gyroLowpassHz & 0xff); // legacy byte
  push16(dv, 1, filters.dtermLowpassHz);
  push16(dv, 3, filters.yawLowpassHz);
  push16(dv, 5, filters.gyroNotchHz);
  push16(dv, 7, filters.gyroNotchCutoff);
  push16(dv, 9, filters.dtermNotchHz);
  push16(dv, 11, filters.dtermNotchCutoff);
  push16(dv, 13, filters.gyroNotch2Hz);
  push16(dv, 15, filters.gyroNotch2Cutoff);
  push8(dv, 17, filters.dtermLowpassType);
  push8(dv, 18, filters.gyroHardwareLpf);
  push8(dv, 19, 0); // unused
  push16(dv, 20, filters.gyroLowpassHz);
  push16(dv, 22, filters.gyroLowpass2Hz);
  push8(dv, 24, filters.gyroLowpassType);
  push8(dv, 25, filters.gyroLowpass2Type);
  push16(dv, 26, filters.dtermLowpass2Hz);
  push8(dv, 28, filters.dtermLowpass2Type);
  push16(dv, 29, filters.gyroLowpassDynMinHz);
  push16(dv, 31, filters.gyroLowpassDynMaxHz);
  push16(dv, 33, filters.dtermLowpassDynMinHz);
  push16(dv, 35, filters.dtermLowpassDynMaxHz);
  push8(dv, 37, filters.dynNotchRange);
  push8(dv, 38, filters.dynNotchWidthPercent);
  push16(dv, 39, filters.dynNotchQ);
  push16(dv, 41, filters.dynNotchMinHz);
  push8(dv, 43, filters.gyroRpmNotchHarmonics);
  push8(dv, 44, filters.gyroRpmNotchMinHz);
  push16(dv, 45, filters.dynNotchMaxHz);
  push8(dv, 47, filters.dynLpfCurveExpo);
  push8(dv, 48, filters.dynNotchCount);
  return buf;
}


/**
 * MSP_SET_ADVANCED_CONFIG (91)
 *
 * From MSPHelper.js crunch:
 *   U8  gyroSyncDenom
 *   U8  pidProcessDenom
 *   U8  useUnsyncedPwm
 *   U8  motorPwmProtocol
 *   U16 motorPwmRate
 *   U16 motorIdle (×100)
 *   U8  0 (gyroUse32kHz, unused)
 *   U8  motorPwmInversion
 *   U8  gyroToUse
 *   U8  gyroHighFsr
 *   U8  gyroMovementCalibThreshold
 *   U16 gyroCalibDuration
 *   U16 gyroOffsetYaw
 *   U8  gyroCheckOverflow
 *   U8  debugMode
 */
export function encodeMspSetAdvancedConfig(config: {
  gyroSyncDenom: number;
  pidProcessDenom: number;
  useUnsyncedPwm: number;
  motorPwmProtocol: number;
  motorPwmRate: number;
  digitalIdlePercent: number;
  motorPwmInversion: number;
  gyroToUse: number;
  gyroHighFsr: number;
  gyroMovementCalibThreshold: number;
  gyroCalibDuration: number;
  gyroOffsetYaw: number;
  gyroCheckOverflow: number;
  debugMode: number;
}): Uint8Array {
  const { buf, dv } = makeBuffer(19);
  push8(dv, 0, config.gyroSyncDenom);
  push8(dv, 1, config.pidProcessDenom);
  push8(dv, 2, config.useUnsyncedPwm);
  push8(dv, 3, config.motorPwmProtocol);
  push16(dv, 4, config.motorPwmRate);
  push16(dv, 6, Math.round(config.digitalIdlePercent * 100));
  push8(dv, 8, 0); // gyroUse32kHz unused
  push8(dv, 9, config.motorPwmInversion);
  push8(dv, 10, config.gyroToUse);
  push8(dv, 11, config.gyroHighFsr);
  push8(dv, 12, config.gyroMovementCalibThreshold);
  push16(dv, 13, config.gyroCalibDuration);
  push16(dv, 15, config.gyroOffsetYaw);
  push8(dv, 17, config.gyroCheckOverflow);
  push8(dv, 18, config.debugMode);
  return buf;
}

