/**
 * Telemetry MAVLink v2 message decoders (extended): PowerStatus, ScaledImu,
 * ScaledPressure, EstimatorStatus, LocalPositionNed, RawImu, RcChannelsRaw,
 * RcChannelsOverride, Altitude.
 *
 * @module protocol/messages/telemetry-ext
 */

// ── POWER_STATUS (ID 125) ───────────────────────────────────

export interface PowerStatusMsg {
  vcc: number;
  vservo: number;
  flags: number;
}

/**
 * Decode POWER_STATUS (msg ID 125).
 *
 * Wire order (all uint16):
 * | Offset | Type   | Field  |
 * |--------|--------|--------|
 * | 0      | uint16 | vcc    |
 * | 2      | uint16 | vservo |
 * | 4      | uint16 | flags  |
 */
export function decodePowerStatus(dv: DataView): PowerStatusMsg {
  return {
    vcc: dv.getUint16(0, true),
    vservo: dv.getUint16(2, true),
    flags: dv.getUint16(4, true),
  };
}

// ── SCALED_IMU (ID 26) ─────────────────────────────────────

export interface ScaledImuMsg {
  timeBootMs: number;
  xacc: number;
  yacc: number;
  zacc: number;
  xgyro: number;
  ygyro: number;
  zgyro: number;
  xmag: number;
  ymag: number;
  zmag: number;
}

/**
 * Decode SCALED_IMU (msg ID 26).
 *
 * Wire order (uint32 → int16):
 * | Offset | Type   | Field      |
 * |--------|--------|------------|
 * | 0      | uint32 | timeBootMs |
 * | 4      | int16  | xacc       |
 * | 6      | int16  | yacc       |
 * | 8      | int16  | zacc       |
 * | 10     | int16  | xgyro      |
 * | 12     | int16  | ygyro      |
 * | 14     | int16  | zgyro      |
 * | 16     | int16  | xmag       |
 * | 18     | int16  | ymag       |
 * | 20     | int16  | zmag       |
 */
export function decodeScaledImu(dv: DataView): ScaledImuMsg {
  return {
    timeBootMs: dv.getUint32(0, true),
    xacc: dv.getInt16(4, true),
    yacc: dv.getInt16(6, true),
    zacc: dv.getInt16(8, true),
    xgyro: dv.getInt16(10, true),
    ygyro: dv.getInt16(12, true),
    zgyro: dv.getInt16(14, true),
    xmag: dv.getInt16(16, true),
    ymag: dv.getInt16(18, true),
    zmag: dv.getInt16(20, true),
  };
}

// ── SCALED_PRESSURE (ID 29) ──────────────────────────────────

export interface ScaledPressureMsg {
  timeBootMs: number;
  pressAbs: number;
  pressDiff: number;
  temperature: number;
}

/**
 * Decode SCALED_PRESSURE (msg ID 29).
 *
 * Wire order (uint32 → float32 → int16):
 * | Offset | Type    | Field        |
 * |--------|---------|--------------|
 * | 0      | uint32  | timeBootMs   |
 * | 4      | float32 | pressAbs     | (hPa)
 * | 8      | float32 | pressDiff    | (hPa)
 * | 12     | int16   | temperature  | (cdegC)
 */
export function decodeScaledPressure(dv: DataView): ScaledPressureMsg {
  return {
    timeBootMs: dv.getUint32(0, true),
    pressAbs: dv.getFloat32(4, true),
    pressDiff: dv.getFloat32(8, true),
    temperature: dv.getInt16(12, true),
  };
}

// ── ESTIMATOR_STATUS (ID 230) ─────────────────────────────────

export interface EstimatorStatusMsg {
  timeUsec: number;
  velRatio: number;
  posHorizRatio: number;
  posVertRatio: number;
  magRatio: number;
  haglRatio: number;
  tasRatio: number;
  posHorizAccuracy: number;
  posVertAccuracy: number;
  flags: number;
}

/**
 * Decode ESTIMATOR_STATUS (msg ID 230).
 *
 * Wire order (uint64 → float32 → uint16):
 * | Offset | Type    | Field             |
 * |--------|---------|-------------------|
 * | 0      | uint64  | timeUsec          |
 * | 8      | float32 | velRatio          |
 * | 12     | float32 | posHorizRatio     |
 * | 16     | float32 | posVertRatio      |
 * | 20     | float32 | magRatio          |
 * | 24     | float32 | haglRatio         |
 * | 28     | float32 | tasRatio          |
 * | 32     | float32 | posHorizAccuracy  |
 * | 36     | float32 | posVertAccuracy   |
 * | 40     | uint16  | flags             |
 */
export function decodeEstimatorStatus(dv: DataView): EstimatorStatusMsg {
  const low = dv.getUint32(0, true);
  const high = dv.getUint32(4, true);
  return {
    timeUsec: high * 0x100000000 + low,
    velRatio: dv.getFloat32(8, true),
    posHorizRatio: dv.getFloat32(12, true),
    posVertRatio: dv.getFloat32(16, true),
    magRatio: dv.getFloat32(20, true),
    haglRatio: dv.getFloat32(24, true),
    tasRatio: dv.getFloat32(28, true),
    posHorizAccuracy: dv.getFloat32(32, true),
    posVertAccuracy: dv.getFloat32(36, true),
    flags: dv.getUint16(40, true),
  };
}

// ── LOCAL_POSITION_NED (ID 32) ──────────────────────────────

export interface LocalPositionNedMsg {
  timeBootMs: number;
  x: number;
  y: number;
  z: number;
  vx: number;
  vy: number;
  vz: number;
}

/**
 * Decode LOCAL_POSITION_NED (msg ID 32).
 *
 * | Offset | Type    | Field      |
 * |--------|---------|------------|
 * | 0      | uint32  | timeBootMs |
 * | 4      | float32 | x          |
 * | 8      | float32 | y          |
 * | 12     | float32 | z          |
 * | 16     | float32 | vx         |
 * | 20     | float32 | vy         |
 * | 24     | float32 | vz         |
 */
export function decodeLocalPositionNed(dv: DataView): LocalPositionNedMsg {
  return {
    timeBootMs: dv.getUint32(0, true),
    x: dv.getFloat32(4, true),
    y: dv.getFloat32(8, true),
    z: dv.getFloat32(12, true),
    vx: dv.getFloat32(16, true),
    vy: dv.getFloat32(20, true),
    vz: dv.getFloat32(24, true),
  };
}

// ── RAW_IMU (ID 27) ──────────────────────────────────────────

export interface RawImuMsg {
  timeUsec: number;
  xacc: number;
  yacc: number;
  zacc: number;
  xgyro: number;
  ygyro: number;
  zgyro: number;
  xmag: number;
  ymag: number;
  zmag: number;
}

/**
 * Decode RAW_IMU (msg ID 27).
 *
 * Wire order (uint64 → int16):
 * | Offset | Type   | Field      |
 * |--------|--------|------------|
 * | 0      | uint64 | timeUsec   |
 * | 8      | int16  | xacc       |
 * | 10     | int16  | yacc       |
 * | 12     | int16  | zacc       |
 * | 14     | int16  | xgyro      |
 * | 16     | int16  | ygyro      |
 * | 18     | int16  | zgyro      |
 * | 20     | int16  | xmag       |
 * | 22     | int16  | ymag       |
 * | 24     | int16  | zmag       |
 */
export function decodeRawImu(dv: DataView): RawImuMsg {
  const low = dv.getUint32(0, true);
  const high = dv.getUint32(4, true);
  return {
    timeUsec: high * 0x100000000 + low,
    xacc: dv.getInt16(8, true),
    yacc: dv.getInt16(10, true),
    zacc: dv.getInt16(12, true),
    xgyro: dv.getInt16(14, true),
    ygyro: dv.getInt16(16, true),
    zgyro: dv.getInt16(18, true),
    xmag: dv.getInt16(20, true),
    ymag: dv.getInt16(22, true),
    zmag: dv.getInt16(24, true),
  };
}

// ── RC_CHANNELS_RAW (ID 35) ──────────────────────────────────

export interface RcChannelsRawMsg {
  timeBootMs: number;
  chan1Raw: number;
  chan2Raw: number;
  chan3Raw: number;
  chan4Raw: number;
  chan5Raw: number;
  chan6Raw: number;
  chan7Raw: number;
  chan8Raw: number;
  port: number;
  rssi: number;
}

/**
 * Decode RC_CHANNELS_RAW (msg ID 35).
 *
 * Wire order (uint32 → uint16 → uint8):
 * | Offset | Type   | Field      |
 * |--------|--------|------------|
 * | 0      | uint32 | timeBootMs |
 * | 4      | uint16 | chan1_raw  |
 * | 6      | uint16 | chan2_raw  |
 * | 8      | uint16 | chan3_raw  |
 * | 10     | uint16 | chan4_raw  |
 * | 12     | uint16 | chan5_raw  |
 * | 14     | uint16 | chan6_raw  |
 * | 16     | uint16 | chan7_raw  |
 * | 18     | uint16 | chan8_raw  |
 * | 20     | uint8  | port       |
 * | 21     | uint8  | rssi       |
 */
export function decodeRcChannelsRaw(dv: DataView): RcChannelsRawMsg {
  return {
    timeBootMs: dv.getUint32(0, true),
    chan1Raw: dv.getUint16(4, true),
    chan2Raw: dv.getUint16(6, true),
    chan3Raw: dv.getUint16(8, true),
    chan4Raw: dv.getUint16(10, true),
    chan5Raw: dv.getUint16(12, true),
    chan6Raw: dv.getUint16(14, true),
    chan7Raw: dv.getUint16(16, true),
    chan8Raw: dv.getUint16(18, true),
    port: dv.getUint8(20),
    rssi: dv.getUint8(21),
  };
}

// ── RC_CHANNELS_OVERRIDE (ID 70) — decoder ───────────────────

export interface RcChannelsOverrideMsg {
  chan1Raw: number;
  chan2Raw: number;
  chan3Raw: number;
  chan4Raw: number;
  chan5Raw: number;
  chan6Raw: number;
  chan7Raw: number;
  chan8Raw: number;
  targetSystem: number;
  targetComponent: number;
}

/**
 * Decode RC_CHANNELS_OVERRIDE (msg ID 70).
 *
 * Wire order (uint16 → uint8):
 * | Offset | Type   | Field           |
 * |--------|--------|-----------------|
 * | 0      | uint16 | chan1_raw       |
 * | 2      | uint16 | chan2_raw       |
 * | 4      | uint16 | chan3_raw       |
 * | 6      | uint16 | chan4_raw       |
 * | 8      | uint16 | chan5_raw       |
 * | 10     | uint16 | chan6_raw       |
 * | 12     | uint16 | chan7_raw       |
 * | 14     | uint16 | chan8_raw       |
 * | 16     | uint8  | targetSystem    |
 * | 17     | uint8  | targetComponent |
 */
export function decodeRcChannelsOverride(dv: DataView): RcChannelsOverrideMsg {
  return {
    chan1Raw: dv.getUint16(0, true),
    chan2Raw: dv.getUint16(2, true),
    chan3Raw: dv.getUint16(4, true),
    chan4Raw: dv.getUint16(6, true),
    chan5Raw: dv.getUint16(8, true),
    chan6Raw: dv.getUint16(10, true),
    chan7Raw: dv.getUint16(12, true),
    chan8Raw: dv.getUint16(14, true),
    targetSystem: dv.getUint8(16),
    targetComponent: dv.getUint8(17),
  };
}

// ── ALTITUDE (ID 141) ────────────────────────────────────────

export interface AltitudeMsg {
  timeUsec: number;
  altitudeMonotonic: number;
  altitudeAmsl: number;
  altitudeLocal: number;
  altitudeRelative: number;
  altitudeTerrain: number;
  bottomClearance: number;
}

/**
 * Decode ALTITUDE (msg ID 141).
 *
 * Wire order (uint64 → float32):
 * | Offset | Type    | Field             |
 * |--------|---------|-------------------|
 * | 0      | uint64  | timeUsec          |
 * | 8      | float32 | altitudeMonotonic |
 * | 12     | float32 | altitudeAmsl      |
 * | 16     | float32 | altitudeLocal     |
 * | 20     | float32 | altitudeRelative  |
 * | 24     | float32 | altitudeTerrain   |
 * | 28     | float32 | bottomClearance   |
 */
export function decodeAltitude(dv: DataView): AltitudeMsg {
  const low = dv.getUint32(0, true);
  const high = dv.getUint32(4, true);
  return {
    timeUsec: high * 0x100000000 + low,
    altitudeMonotonic: dv.getFloat32(8, true),
    altitudeAmsl: dv.getFloat32(12, true),
    altitudeLocal: dv.getFloat32(16, true),
    altitudeRelative: dv.getFloat32(20, true),
    altitudeTerrain: dv.getFloat32(24, true),
    bottomClearance: dv.getFloat32(28, true),
  };
}
