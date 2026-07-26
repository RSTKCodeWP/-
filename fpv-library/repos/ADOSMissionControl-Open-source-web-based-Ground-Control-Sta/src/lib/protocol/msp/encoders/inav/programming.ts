/**
 * iNav programming framework encoders: logic conditions and programming PIDs.
 *
 * @module protocol/msp/encoders/inav/programming
 */

import type { INavLogicCondition, INavProgrammingPid } from '../../msp-decoders-inav';
import { writeU8, writeS32 } from './_helpers';

/**
 * Encode MSP2_INAV_SET_LOGIC_CONDITIONS (0x2023) payload for one condition slot.
 *
 * U8  enabled
 * U8  activatorId
 * U8  operation
 * U8  operandAType
 * S32 operandAValue
 * U8  operandBType
 * S32 operandBValue
 * U8  flags
 *
 * 14 bytes total. Mirrors the decoder layout in decodeMspINavLogicConditions.
 */
export function encodeMspINavSetLogicCondition(rule: INavLogicCondition): Uint8Array {
  const buf = new Uint8Array(14);
  const dv = new DataView(buf.buffer);

  writeU8(dv, 0, rule.enabled ? 1 : 0);
  writeU8(dv, 1, rule.activatorId);
  writeU8(dv, 2, rule.operation);
  writeU8(dv, 3, rule.operandAType);
  writeS32(dv, 4, rule.operandAValue);
  writeU8(dv, 8, rule.operandBType);
  writeS32(dv, 9, rule.operandBValue);
  writeU8(dv, 13, rule.flags);

  return buf;
}

/**
 * Encode MSP2_INAV_SET_PROGRAMMING_PID (0x2029) payload for one PID slot.
 *
 * U8  enabled
 * U8  setpointType
 * S32 setpointValue
 * U8  measurementType
 * S32 measurementValue
 * U8  P
 * U8  I
 * U8  D
 * U8  FF
 *
 * 15 bytes total. Mirrors the decoder layout in decodeMspINavProgrammingPid.
 */
/**
 * Encode MSP2_INAV_SET_GVAR (0x2214) payload — set one global variable's
 * live runtime value.
 *
 * U8  gvarIndex
 * S32 value
 *
 * 5 bytes total.
 */
export function encodeMspINavSetGvar(index: number, value: number): Uint8Array {
  const buf = new Uint8Array(5);
  const dv = new DataView(buf.buffer);
  writeU8(dv, 0, index);
  writeS32(dv, 1, value);
  return buf;
}

export function encodeMspINavSetProgrammingPid(rule: INavProgrammingPid): Uint8Array {
  const buf = new Uint8Array(15);
  const dv = new DataView(buf.buffer);

  writeU8(dv, 0, rule.enabled ? 1 : 0);
  writeU8(dv, 1, rule.setpointType);
  writeS32(dv, 2, rule.setpointValue);
  writeU8(dv, 6, rule.measurementType);
  writeS32(dv, 7, rule.measurementValue);
  writeU8(dv, 11, rule.gains.P);
  writeU8(dv, 12, rule.gains.I);
  writeU8(dv, 13, rule.gains.D);
  writeU8(dv, 14, rule.gains.FF);

  return buf;
}
