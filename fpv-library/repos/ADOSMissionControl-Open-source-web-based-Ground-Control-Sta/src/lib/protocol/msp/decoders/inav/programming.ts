/**
 * iNav programming decoders: logic conditions, their live status, global
 * variables, programmable PIDs, and PID status.
 *
 * @module protocol/msp/decoders/inav/programming
 */

import { readU8, readS32 } from "./helpers";
import type {
  INavLogicCondition,
  INavLogicConditionsStatus,
  INavGvarStatus,
  INavProgrammingPid,
  INavProgrammingPidStatus,
} from "./types";

// ── iNav LOGIC CONDITIONS decoder ────────────────────────────

/**
 * Decode one or more 14-byte logic-condition blocks. A single condition is
 * read per-index via MSP2_INAV_LOGIC_CONDITIONS_SINGLE (0x203B); the bulk
 * getter (0x2022) is deprecated and returns no data on current firmware.
 *
 * Per condition (14 bytes):
 *   U8  enabled
 *   U8  activatorId
 *   U8  operation
 *   U8  operandAType
 *   S32 operandAValue
 *   U8  operandBType
 *   S32 operandBValue
 *   U8  flags
 */
export function decodeMspINavLogicConditions(dv: DataView): INavLogicCondition[] {
  const result: INavLogicCondition[] = [];
  const ENTRY = 14;
  let offset = 0;
  while (offset + ENTRY <= dv.byteLength) {
    result.push({
      enabled: readU8(dv, offset) !== 0,
      activatorId: readU8(dv, offset + 1),
      operation: readU8(dv, offset + 2),
      operandAType: readU8(dv, offset + 3),
      operandAValue: readS32(dv, offset + 4),
      operandBType: readU8(dv, offset + 8),
      operandBValue: readS32(dv, offset + 9),
      flags: readU8(dv, offset + 13),
    });
    offset += ENTRY;
  }
  return result;
}

// ── iNav LOGIC CONDITIONS STATUS decoder ─────────────────────

/**
 * MSP2_INAV_LOGIC_CONDITIONS_STATUS (0x2026)
 *
 * Repeated per condition:
 *   U8  id
 *   S32 value
 */
export function decodeMspINavLogicConditionsStatus(dv: DataView): INavLogicConditionsStatus[] {
  const result: INavLogicConditionsStatus[] = [];
  const ENTRY = 5;
  let offset = 0;
  while (offset + ENTRY <= dv.byteLength) {
    result.push({
      id: readU8(dv, offset),
      value: readS32(dv, offset + 1),
    });
    offset += ENTRY;
  }
  return result;
}

// ── iNav GVAR STATUS decoder ─────────────────────────────────

/**
 * MSP2_INAV_GVAR_STATUS (0x2027)
 *
 * S32[8] live global-variable values (gvGet(0..7)); 32 bytes total.
 */
export function decodeMspINavGvarStatus(dv: DataView): INavGvarStatus {
  const values: number[] = [];
  for (let i = 0; i < 8; i++) {
    values.push(dv.byteLength >= (i + 1) * 4 ? readS32(dv, i * 4) : 0);
  }
  return { values };
}

// ── iNav PROGRAMMING PID decoder ─────────────────────────────

/**
 * MSP2_INAV_PROGRAMMING_PID (0x2028)
 *
 * Repeated per PID (variable size):
 *   U8  enabled
 *   U8  setpointType
 *   S32 setpointValue
 *   U8  measurementType
 *   S32 measurementValue
 *   U8  P
 *   U8  I
 *   U8  D
 *   U8  FF
 */
export function decodeMspINavProgrammingPid(dv: DataView): INavProgrammingPid[] {
  const result: INavProgrammingPid[] = [];
  const ENTRY = 15;
  let offset = 0;
  while (offset + ENTRY <= dv.byteLength) {
    result.push({
      enabled: readU8(dv, offset) !== 0,
      setpointType: readU8(dv, offset + 1),
      setpointValue: readS32(dv, offset + 2),
      measurementType: readU8(dv, offset + 6),
      measurementValue: readS32(dv, offset + 7),
      gains: {
        P: readU8(dv, offset + 11),
        I: readU8(dv, offset + 12),
        D: readU8(dv, offset + 13),
        FF: readU8(dv, offset + 14),
      },
    });
    offset += ENTRY;
  }
  return result;
}

// ── iNav PROGRAMMING PID STATUS decoder ──────────────────────

/**
 * MSP2_INAV_PROGRAMMING_PID_STATUS (0x202a)
 *
 * Repeated per PID:
 *   U8  id
 *   S32 output
 */
export function decodeMspINavProgrammingPidStatus(dv: DataView): INavProgrammingPidStatus[] {
  const result: INavProgrammingPidStatus[] = [];
  const ENTRY = 5;
  let offset = 0;
  while (offset + ENTRY <= dv.byteLength) {
    result.push({
      id: readU8(dv, offset),
      output: readS32(dv, offset + 1),
    });
    offset += ENTRY;
  }
  return result;
}
