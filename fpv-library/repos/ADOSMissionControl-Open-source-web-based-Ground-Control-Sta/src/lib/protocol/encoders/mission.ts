/**
 * MAVLink mission protocol encoders.
 * Supports mission_type extension field (MAVLink v2) for fence and rally operations.
 * @module protocol/encoders/mission
 */

import { buildFrame } from "./frame";

/** MAVLink mission types */
export const MAV_MISSION_TYPE_MISSION = 0;
export const MAV_MISSION_TYPE_FENCE = 1;
export const MAV_MISSION_TYPE_RALLY = 2;

// ── MISSION_COUNT (ID 44) ───────────────────────────────────

/** Send mission item count to initiate mission upload.
 * @param missionType - 0=mission, 1=fence, 2=rally (v2 extension field)
 */
export function encodeMissionCount(
  targetSys: number,
  targetComp: number,
  count: number,
  sysId = 255,
  compId = 190,
  missionType = 0,
): Uint8Array {
  const len = missionType > 0 ? 5 : 4;
  const payload = new Uint8Array(len);
  const dv = new DataView(payload.buffer);
  dv.setUint16(0, count, true);
  payload[2] = targetSys;
  payload[3] = targetComp;
  if (missionType > 0) payload[4] = missionType;
  return buildFrame(44, payload, sysId, compId);
}

// ── MISSION_ITEM_INT (ID 73) ────────────────────────────────

/** Encode a single mission item (INT variant — lat/lon as int32 * 1e7).
 * @param missionType - 0=mission, 1=fence, 2=rally (v2 extension field)
 */
export function encodeMissionItemInt(
  targetSys: number,
  targetComp: number,
  seq: number,
  frame: number,
  command: number,
  current: number,
  autocontinue: number,
  p1: number,
  p2: number,
  p3: number,
  p4: number,
  x: number,
  y: number,
  z: number,
  sysId = 255,
  compId = 190,
  missionType = 0,
): Uint8Array {
  const len = missionType > 0 ? 38 : 37;
  const payload = new Uint8Array(len);
  const dv = new DataView(payload.buffer);
  dv.setFloat32(0, p1, true);
  dv.setFloat32(4, p2, true);
  dv.setFloat32(8, p3, true);
  dv.setFloat32(12, p4, true);
  dv.setInt32(16, x, true);      // lat * 1e7
  dv.setInt32(20, y, true);      // lon * 1e7
  dv.setFloat32(24, z, true);    // alt
  dv.setUint16(28, seq, true);
  dv.setUint16(30, command, true);
  payload[32] = targetSys;
  payload[33] = targetComp;
  payload[34] = frame;
  payload[35] = current;
  payload[36] = autocontinue;
  if (missionType > 0) payload[37] = missionType;
  return buildFrame(73, payload, sysId, compId);
}

// ── MISSION_REQUEST_LIST (ID 43) ─────────────────────────────

/** Request the mission item list from the flight controller.
 * @param missionType - 0=mission, 1=fence, 2=rally (v2 extension field)
 */
export function encodeMissionRequestList(
  targetSys: number,
  targetComp: number,
  sysId = 255,
  compId = 190,
  missionType = 0,
): Uint8Array {
  const len = missionType > 0 ? 3 : 2;
  const payload = new Uint8Array(len);
  payload[0] = targetSys;
  payload[1] = targetComp;
  if (missionType > 0) payload[2] = missionType;
  return buildFrame(43, payload, sysId, compId);
}

// ── MISSION_REQUEST_INT (ID 51) ──────────────────────────────

/** Request a specific mission item by sequence number.
 * @param missionType - 0=mission, 1=fence, 2=rally (v2 extension field)
 */
export function encodeMissionRequestInt(
  targetSys: number,
  targetComp: number,
  seq: number,
  sysId = 255,
  compId = 190,
  missionType = 0,
): Uint8Array {
  const len = missionType > 0 ? 5 : 4;
  const payload = new Uint8Array(len);
  const dv = new DataView(payload.buffer);
  dv.setUint16(0, seq, true);
  payload[2] = targetSys;
  payload[3] = targetComp;
  if (missionType > 0) payload[4] = missionType;
  return buildFrame(51, payload, sysId, compId);
}

// ── MISSION_ACK (ID 47) ─────────────────────────────────────

/** Send mission acknowledgement.
 * @param missionType - 0=mission, 1=fence, 2=rally (v2 extension field)
 */
export function encodeMissionAck(
  targetSys: number,
  targetComp: number,
  type: number,
  sysId = 255,
  compId = 190,
  missionType = 0,
): Uint8Array {
  const len = missionType > 0 ? 4 : 3;
  const payload = new Uint8Array(len);
  payload[0] = targetSys;
  payload[1] = targetComp;
  payload[2] = type;
  if (missionType > 0) payload[3] = missionType;
  return buildFrame(47, payload, sysId, compId);
}

// ── MISSION_CLEAR_ALL (ID 45) ───────────────────────────────

/** Clear all mission items on the flight controller.
 * @param missionType - 0=mission, 1=fence, 2=rally (v2 extension field)
 */
export function encodeMissionClearAll(
  targetSys: number,
  targetComp: number,
  sysId = 255,
  compId = 190,
  missionType = 0,
): Uint8Array {
  const len = missionType > 0 ? 3 : 2;
  const payload = new Uint8Array(len);
  payload[0] = targetSys;
  payload[1] = targetComp;
  if (missionType > 0) payload[2] = missionType;
  return buildFrame(45, payload, sysId, compId);
}
