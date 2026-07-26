/**
 * Navigation and safety MAVLink v2 message decoders: EKF, Vibration,
 * ServoOutput, Wind, Terrain, HomePosition, NavController, Fence,
 * DistanceSensor, SetAttitudeTarget, SetPositionTargetGlobalInt.
 *
 * @module protocol/messages/nav-safety
 */

// ── SERVO_OUTPUT_RAW (ID 36) ───────────────────────────────

export interface ServoOutputRawMsg {
  timeUsec: number;
  servo1: number;
  servo2: number;
  servo3: number;
  servo4: number;
  servo5: number;
  servo6: number;
  servo7: number;
  servo8: number;
  port: number;
}

/**
 * Decode SERVO_OUTPUT_RAW (msg ID 36).
 *
 * | Offset | Type   | Field      |
 * |--------|--------|------------|
 * | 0      | uint32 | timeUsec   |
 * | 4      | uint16 | servo1_raw |
 * | 6      | uint16 | servo2_raw |
 * | 8      | uint16 | servo3_raw |
 * | 10     | uint16 | servo4_raw |
 * | 12     | uint16 | servo5_raw |
 * | 14     | uint16 | servo6_raw |
 * | 16     | uint16 | servo7_raw |
 * | 18     | uint16 | servo8_raw |
 * | 20     | uint8  | port       |
 */
export function decodeServoOutputRaw(dv: DataView): ServoOutputRawMsg {
  return {
    timeUsec: dv.getUint32(0, true),
    servo1: dv.getUint16(4, true),
    servo2: dv.getUint16(6, true),
    servo3: dv.getUint16(8, true),
    servo4: dv.getUint16(10, true),
    servo5: dv.getUint16(12, true),
    servo6: dv.getUint16(14, true),
    servo7: dv.getUint16(16, true),
    servo8: dv.getUint16(18, true),
    port: dv.getUint8(20),
  };
}

// ── NAV_CONTROLLER_OUTPUT (ID 62) ───────────────────────────

export interface NavControllerOutputMsg {
  navRoll: number;
  navPitch: number;
  altError: number;
  aspdError: number;
  xtrackError: number;
  navBearing: number;
  targetBearing: number;
  wpDist: number;
}

/**
 * Decode NAV_CONTROLLER_OUTPUT (msg ID 62).
 *
 * Wire order (float32 → int16 → uint16):
 * | Offset | Type    | Field          |
 * |--------|---------|----------------|
 * | 0      | float32 | navRoll        |
 * | 4      | float32 | navPitch       |
 * | 8      | float32 | altError       |
 * | 12     | float32 | aspdError      |
 * | 16     | float32 | xtrackError    |
 * | 20     | int16   | navBearing     |
 * | 22     | int16   | targetBearing  |
 * | 24     | uint16  | wpDist         |
 */
export function decodeNavControllerOutput(dv: DataView): NavControllerOutputMsg {
  return {
    navRoll: dv.getFloat32(0, true),
    navPitch: dv.getFloat32(4, true),
    altError: dv.getFloat32(8, true),
    aspdError: dv.getFloat32(12, true),
    xtrackError: dv.getFloat32(16, true),
    navBearing: dv.getInt16(20, true),
    targetBearing: dv.getInt16(22, true),
    wpDist: dv.getUint16(24, true),
  };
}

// ── SET_ATTITUDE_TARGET (ID 82) ─────────────────────────────

export interface SetAttitudeTargetMsg {
  timeBootMs: number;
  q: [number, number, number, number];
  bodyRollRate: number;
  bodyPitchRate: number;
  bodyYawRate: number;
  thrust: number;
  targetSystem: number;
  targetComponent: number;
  typeMask: number;
}

/**
 * Decode SET_ATTITUDE_TARGET (msg ID 82).
 *
 * Wire order (uint32/float32 → uint8):
 * | Offset | Type       | Field          |
 * |--------|------------|----------------|
 * | 0      | uint32     | timeBootMs     |
 * | 4      | float32[4] | q              |
 * | 20     | float32    | bodyRollRate   |
 * | 24     | float32    | bodyPitchRate  |
 * | 28     | float32    | bodyYawRate    |
 * | 32     | float32    | thrust         |
 * | 36     | uint8      | targetSystem   |
 * | 37     | uint8      | targetComponent|
 * | 38     | uint8      | typeMask       |
 */
export function decodeSetAttitudeTarget(dv: DataView): SetAttitudeTargetMsg {
  return {
    timeBootMs: dv.getUint32(0, true),
    q: [
      dv.getFloat32(4, true),
      dv.getFloat32(8, true),
      dv.getFloat32(12, true),
      dv.getFloat32(16, true),
    ],
    bodyRollRate: dv.getFloat32(20, true),
    bodyPitchRate: dv.getFloat32(24, true),
    bodyYawRate: dv.getFloat32(28, true),
    thrust: dv.getFloat32(32, true),
    targetSystem: dv.getUint8(36),
    targetComponent: dv.getUint8(37),
    typeMask: dv.getUint8(38),
  };
}

// ── SET_POSITION_TARGET_GLOBAL_INT (ID 86) ──────────────────

export interface SetPositionTargetGlobalIntMsg {
  timeBootMs: number;
  latInt: number;
  lonInt: number;
  alt: number;
  vx: number;
  vy: number;
  vz: number;
  afx: number;
  afy: number;
  afz: number;
  yaw: number;
  yawRate: number;
  typeMask: number;
  targetSystem: number;
  targetComponent: number;
  coordinateFrame: number;
}

/**
 * Decode SET_POSITION_TARGET_GLOBAL_INT (msg ID 86).
 *
 * Wire order (uint32/int32/float32 → uint16 → uint8):
 * | Offset | Type    | Field           |
 * |--------|---------|-----------------|
 * | 0      | uint32  | timeBootMs      |
 * | 4      | int32   | latInt          |
 * | 8      | int32   | lonInt          |
 * | 12     | float32 | alt             |
 * | 16     | float32 | vx              |
 * | 20     | float32 | vy              |
 * | 24     | float32 | vz              |
 * | 28     | float32 | afx             |
 * | 32     | float32 | afy             |
 * | 36     | float32 | afz             |
 * | 40     | float32 | yaw             |
 * | 44     | float32 | yawRate         |
 * | 48     | uint16  | typeMask        |
 * | 50     | uint8   | targetSystem    |
 * | 51     | uint8   | targetComponent |
 * | 52     | uint8   | coordinateFrame |
 */
export function decodeSetPositionTargetGlobalInt(dv: DataView): SetPositionTargetGlobalIntMsg {
  return {
    timeBootMs: dv.getUint32(0, true),
    latInt: dv.getInt32(4, true),
    lonInt: dv.getInt32(8, true),
    alt: dv.getFloat32(12, true),
    vx: dv.getFloat32(16, true),
    vy: dv.getFloat32(20, true),
    vz: dv.getFloat32(24, true),
    afx: dv.getFloat32(28, true),
    afy: dv.getFloat32(32, true),
    afz: dv.getFloat32(36, true),
    yaw: dv.getFloat32(40, true),
    yawRate: dv.getFloat32(44, true),
    typeMask: dv.getUint16(48, true),
    targetSystem: dv.getUint8(50),
    targetComponent: dv.getUint8(51),
    coordinateFrame: dv.getUint8(52),
  };
}

// ── DISTANCE_SENSOR (ID 132) ────────────────────────────────

export interface DistanceSensorMsg {
  timeBootMs: number;
  minDistance: number;
  maxDistance: number;
  currentDistance: number;
  type: number;
  id: number;
  orientation: number;
  covariance: number;
}

/**
 * Decode DISTANCE_SENSOR (msg ID 132).
 *
 * Wire order (uint32 → uint16 → uint8):
 * | Offset | Type   | Field           |
 * |--------|--------|-----------------|
 * | 0      | uint32 | timeBootMs      |
 * | 4      | uint16 | minDistance (cm) |
 * | 6      | uint16 | maxDistance (cm) |
 * | 8      | uint16 | currentDist(cm) |
 * | 10     | uint8  | type            |
 * | 11     | uint8  | id              |
 * | 12     | uint8  | orientation     |
 * | 13     | uint8  | covariance (cm) |
 */
export function decodeDistanceSensor(dv: DataView): DistanceSensorMsg {
  return {
    timeBootMs: dv.getUint32(0, true),
    minDistance: dv.getUint16(4, true),
    maxDistance: dv.getUint16(6, true),
    currentDistance: dv.getUint16(8, true),
    type: dv.getUint8(10),
    id: dv.getUint8(11),
    orientation: dv.getUint8(12),
    covariance: dv.getUint8(13),
  };
}

// ── TERRAIN_REPORT (ID 136) ────────────────────────────────

export interface TerrainReportMsg {
  lat: number;
  lon: number;
  spacing: number;
  terrainHeight: number;
  currentHeight: number;
  pending: number;
  loaded: number;
}

/**
 * Decode TERRAIN_REPORT (msg ID 136).
 *
 * | Offset | Type    | Field          |
 * |--------|---------|----------------|
 * | 0      | int32   | lat (degE7)    |
 * | 4      | int32   | lon (degE7)    |
 * | 8      | float32 | terrainHeight  |
 * | 12     | float32 | currentHeight  |
 * | 16     | uint16  | spacing        |
 * | 18     | uint16  | pending        |
 * | 20     | uint16  | loaded         |
 */
export function decodeTerrainReport(dv: DataView): TerrainReportMsg {
  return {
    lat: dv.getInt32(0, true),
    lon: dv.getInt32(4, true),
    terrainHeight: dv.getFloat32(8, true),
    currentHeight: dv.getFloat32(12, true),
    spacing: dv.getUint16(16, true),
    pending: dv.getUint16(18, true),
    loaded: dv.getUint16(20, true),
  };
}

