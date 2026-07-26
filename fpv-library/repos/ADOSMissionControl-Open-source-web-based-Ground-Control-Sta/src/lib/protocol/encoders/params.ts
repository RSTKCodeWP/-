/**
 * MAVLink parameter encoders: ParamRequestList, ParamRequestRead, ParamSet.
 * @module protocol/encoders/params
 */

import { buildFrame } from "./frame";

// ── PARAM_REQUEST_LIST (ID 21) ──────────────────────────────

/** Request all parameters from the flight controller. */
export function encodeParamRequestList(
  targetSys: number,
  targetComp: number,
  sysId = 255,
  compId = 190,
): Uint8Array {
  const payload = new Uint8Array(2);
  payload[0] = targetSys;
  payload[1] = targetComp;
  return buildFrame(21, payload, sysId, compId);
}

// ── PARAM_REQUEST_READ (ID 20) ──────────────────────────────

/**
 * Request a single parameter by index from the flight controller.
 *
 * @param targetSys  - Target system ID
 * @param targetComp - Target component ID
 * @param paramId    - Parameter name (empty string to use index)
 * @param paramIndex - Parameter index (-1 to use name instead)
 */
export function encodeParamRequestRead(
  targetSys: number,
  targetComp: number,
  paramId: string,
  paramIndex: number,
  sysId = 255,
  compId = 190,
): Uint8Array {
  const payload = new Uint8Array(20);
  const dv = new DataView(payload.buffer);

  // param_index (int16) at offset 0
  dv.setInt16(0, paramIndex, true);

  // target_system at offset 2
  payload[2] = targetSys;

  // target_component at offset 3
  payload[3] = targetComp;

  // param_id (char[16]) at offset 4 — null-padded
  const encoder = new TextEncoder();
  const nameBytes = encoder.encode(paramId.slice(0, 16));
  payload.set(nameBytes, 4);

  return buildFrame(20, payload, sysId, compId);
}

// ── PARAM_SET (ID 23) ───────────────────────────────────────

/**
 * Set a single parameter on the flight controller.
 *
 * @param paramId - Parameter name (max 16 chars, null-padded)
 * @param value   - New value
 * @param type    - MAV_PARAM_TYPE (default 9 = REAL32)
 */
export function encodeParamSet(
  targetSys: number,
  targetComp: number,
  paramId: string,
  value: number,
  type = 9,
  sysId = 255,
  compId = 190,
): Uint8Array {
  const payload = new Uint8Array(23);
  const dv = new DataView(payload.buffer);

  // param_value (float32) at offset 0
  dv.setFloat32(0, value, true);

  // target_system at offset 4
  payload[4] = targetSys;

  // target_component at offset 5
  payload[5] = targetComp;

  // param_id (char[16]) at offset 6 — null-padded
  const encoder = new TextEncoder();
  const nameBytes = encoder.encode(paramId.slice(0, 16));
  payload.set(nameBytes, 6);

  // param_type at offset 22
  payload[22] = type;

  return buildFrame(23, payload, sysId, compId);
}
