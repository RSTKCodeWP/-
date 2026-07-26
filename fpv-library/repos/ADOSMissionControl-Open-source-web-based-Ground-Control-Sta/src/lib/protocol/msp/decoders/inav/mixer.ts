/**
 * iNav mixer decoders: platform mixer, servo mixer rules, servo config,
 * output mapping, timer output mode, and the common motor mixer table.
 *
 * @module protocol/msp/decoders/inav/mixer
 */

import { readU8, readU16, readS16 } from "./helpers";
import type {
  INavMixer,
  INavTimerOutputModeEntry,
  INavOutputMappingExt2Entry,
  INavServoMixerRule,
  INavServoConfig,
  MotorMixerRule,
} from "./types";

// ── iNav MIXER decoder ───────────────────────────────────────

/**
 * MSP2_INAV_MIXER (0x2010)
 *
 * U8  platformType (0=MULTIROTOR, 1=AIRPLANE, 2=TRICOPTER, 3=ROVER, 4=BOAT, 5=HELICOPTER)
 * U8  yawMotorsReversed (bool)
 * U8  hasFlaps (bool)
 * U16 appliedMixerPreset
 * U8  motorCount
 * U8  servoCount
 */
export function decodeMspINavMixer(dv: DataView): INavMixer {
  return {
    platformType: readU8(dv, 0),
    yawMotorsReversed: dv.byteLength > 1 ? readU8(dv, 1) !== 0 : false,
    hasFlaps: dv.byteLength > 2 ? readU8(dv, 2) !== 0 : false,
    appliedMixerPreset: dv.byteLength > 4 ? readU16(dv, 3) : 0,
    motorCount: dv.byteLength > 5 ? readU8(dv, 5) : 0,
    servoCount: dv.byteLength > 6 ? readU8(dv, 6) : 0,
  };
}

// ── iNav TIMER OUTPUT MODE decoder ───────────────────────────

/**
 * MSP2_INAV_TIMER_OUTPUT_MODE (0x200e)
 *
 * Repeated for each timer:
 *   U8 timerId
 *   U8 mode
 */
export function decodeMspINavTimerOutputMode(dv: DataView): INavTimerOutputModeEntry[] {
  const result: INavTimerOutputModeEntry[] = [];
  let offset = 0;
  while (offset + 1 < dv.byteLength) {
    result.push({
      timerId: readU8(dv, offset),
      mode: readU8(dv, offset + 1),
    });
    offset += 2;
  }
  return result;
}

// ── iNav OUTPUT MAPPING EXT2 decoder ─────────────────────────

/**
 * MSP2_INAV_OUTPUT_MAPPING_EXT2 (0x210d)
 *
 * Repeated for each output:
 *   U8 timerId
 *   U16 usageFlags
 *   U16 specialLabels
 */
export function decodeMspINavOutputMappingExt2(dv: DataView): INavOutputMappingExt2Entry[] {
  const result: INavOutputMappingExt2Entry[] = [];
  let offset = 0;
  while (offset + 4 < dv.byteLength) {
    result.push({
      timerId: readU8(dv, offset),
      usageFlags: readU16(dv, offset + 1),
      specialLabels: readU16(dv, offset + 3),
    });
    offset += 5;
  }
  return result;
}

// ── iNav SERVO MIXER decoder ──────────────────────────────────

/**
 * MSP2_INAV_SERVO_MIXER (0x2020)
 *
 * Repeated per rule:
 *   U8  targetChannel
 *   U8  inputSource
 *   S16 rate
 *   U8  speed
 *   U8  conditionId (or -1 if none)
 */
export function decodeMspINavServoMixer(dv: DataView): INavServoMixerRule[] {
  const result: INavServoMixerRule[] = [];
  let offset = 0;
  while (offset + 5 < dv.byteLength) {
    result.push({
      targetChannel: readU8(dv, offset),
      inputSource: readU8(dv, offset + 1),
      rate: readS16(dv, offset + 2),
      speed: readU8(dv, offset + 4),
      conditionId: dv.byteLength > offset + 5 ? readU8(dv, offset + 5) : 0,
    });
    offset += 6;
  }
  return result;
}

// ── iNav SERVO CONFIG decoder ─────────────────────────────────

/**
 * MSP2_INAV_SERVO_CONFIG (0x2200)
 *
 * Repeated per servo (10 bytes each):
 *   S16 rate
 *   S16 min
 *   S16 max
 *   S16 middle
 *   U8  forwardFromChannel
 *   U16 reversedInputSources (bitmask)
 *   U8  flags
 */
export function decodeMspINavServoConfig(dv: DataView): INavServoConfig[] {
  const result: INavServoConfig[] = [];
  let offset = 0;
  while (offset + 10 <= dv.byteLength) {
    result.push({
      rate: readS16(dv, offset),
      min: readS16(dv, offset + 2),
      max: readS16(dv, offset + 4),
      middle: readS16(dv, offset + 6),
      forwardFromChannel: readU8(dv, offset + 8),
      reversedInputSources: dv.byteLength >= offset + 11 ? readU16(dv, offset + 9) : 0,
      flags: dv.byteLength >= offset + 12 ? readU8(dv, offset + 11) : 0,
    });
    offset += 12;
  }
  return result;
}


/**
 * Decode MSP2_COMMON_MOTOR_MIXER (0x1005) response.
 *
 * iNav transmits the motor mixer as a flat array of 8-byte records in slot
 * order (no index field). Each record: S16 throttle, S16 roll, S16 pitch,
 * S16 yaw, all x1000. Empty slots where all four values are 0 are omitted
 * from the returned array.
 */
export function decodeMspCommonMotorMixer(dv: DataView): MotorMixerRule[] {
  const rules: MotorMixerRule[] = [];
  let offset = 0;
  while (offset + 7 < dv.byteLength) {
    const throttle = readS16(dv, offset) / 1000;
    const roll = readS16(dv, offset + 2) / 1000;
    const pitch = readS16(dv, offset + 4) / 1000;
    const yaw = readS16(dv, offset + 6) / 1000;
    if (throttle !== 0 || roll !== 0 || pitch !== 0 || yaw !== 0) {
      rules.push({ throttle, roll, pitch, yaw });
    }
    offset += 8;
  }
  return rules;
}
