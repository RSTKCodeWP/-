/**
 * Vehicle info MAVLink v2 message decoders: AutopilotVersion, ExtendedSysState,
 * ComponentMetadata.
 *
 * @module protocol/messages/vehicle-info
 */

// ── AUTOPILOT_VERSION (ID 148) ──────────────────────────────

export interface AutopilotVersionMsg {
  capabilities: number;
  flightSwVersion: number;
  middlewareSwVersion: number;
  osSwVersion: number;
  boardVersion: number;
  uid: number;
  vendorId: number;
  productId: number;
}

/**
 * Decode AUTOPILOT_VERSION (msg ID 148).
 *
 * Wire order (uint64 → uint32 → uint16 → uint8[]):
 * | Offset | Type      | Field                |
 * |--------|-----------|----------------------|
 * | 0      | uint64    | capabilities         |
 * | 8      | uint64    | uid                  |
 * | 16     | uint32    | flightSwVersion      |
 * | 20     | uint32    | middlewareSwVersion   |
 * | 24     | uint32    | osSwVersion          |
 * | 28     | uint32    | boardVersion         |
 * | 32     | uint16    | vendorId             |
 * | 34     | uint16    | productId            |
 * | 36     | uint8[8]  | flightCustomVersion  |
 * | 44     | uint8[8]  | middlewareCustomVer  |
 * | 52     | uint8[8]  | osCustomVersion      |
 */
export function decodeAutopilotVersion(dv: DataView): AutopilotVersionMsg {
  // capabilities is uint64 — read as two uint32
  const capLow = dv.getUint32(0, true);
  const capHigh = dv.getUint32(4, true);
  const uidLow = dv.getUint32(8, true);
  const uidHigh = dv.getUint32(12, true);

  return {
    capabilities: capHigh * 0x100000000 + capLow,
    uid: uidHigh * 0x100000000 + uidLow,
    flightSwVersion: dv.getUint32(16, true),
    middlewareSwVersion: dv.getUint32(20, true),
    osSwVersion: dv.getUint32(24, true),
    boardVersion: dv.getUint32(28, true),
    vendorId: dv.getUint16(32, true),
    productId: dv.getUint16(34, true),
  };
}

// ── EXTENDED_SYS_STATE (ID 245) ─────────────────────────────

export interface ExtendedSysStateMsg {
  vtolState: number;
  landedState: number;
}

/**
 * Decode EXTENDED_SYS_STATE (msg ID 245).
 *
 * | Offset | Type  | Field       |
 * |--------|-------|-------------|
 * | 0      | uint8 | vtolState   |
 * | 1      | uint8 | landedState |
 */
export function decodeExtendedSysState(dv: DataView): ExtendedSysStateMsg {
  return {
    vtolState: dv.getUint8(0),
    landedState: dv.getUint8(1),
  };
}

// ── COMPONENT_METADATA (ID 397) ─────────────────────────────

export interface ComponentMetadataMsg {
  timeBootMs: number;
  /** CRC32 of the general metadata file (0 if the vehicle does not supply one). */
  fileCrc: number;
  /** MAVLink FTP (`mftp://`) or HTTP(S) URI for the general metadata file. */
  uri: string;
}

/**
 * Decode COMPONENT_METADATA (msg ID 397).
 *
 * A component (PX4 autopilots in practice) sends this in response to
 * MAV_CMD_REQUEST_MESSAGE(397) to advertise where its general metadata file
 * lives. That file in turn lists the URI of the parameter metadata file
 * (COMP_METADATA_TYPE_PARAMETER), which is the FC-served overlay this decoder
 * feeds into the parameter metadata provider.
 *
 * Wire order (uint32 -> uint32 -> char[100], no extension fields):
 * | Offset | Type      | Field       |
 * |--------|-----------|-------------|
 * | 0      | uint32    | timeBootMs  |
 * | 4      | uint32    | fileCrc     |
 * | 8      | char[100] | uri         |
 *
 * `uri` is zero-terminated inside its 100-byte field; bytes at and after the
 * first NUL are dropped.
 */
export function decodeComponentMetadata(dv: DataView): ComponentMetadataMsg {
  const timeBootMs = dv.getUint32(0, true);
  const fileCrc = dv.getUint32(4, true);
  const uriBytes = new Uint8Array(100);
  for (let i = 0; i < 100; i++) uriBytes[i] = dv.getUint8(8 + i);
  const nul = uriBytes.indexOf(0);
  const trimmed = nul >= 0 ? uriBytes.subarray(0, nul) : uriBytes;
  return { timeBootMs, fileCrc, uri: new TextDecoder().decode(trimmed) };
}
