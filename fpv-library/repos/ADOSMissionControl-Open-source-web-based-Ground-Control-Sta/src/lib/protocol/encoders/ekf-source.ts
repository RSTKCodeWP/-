/**
 * EKF source-set encoder.
 *
 * Wraps MAV_CMD_SET_EKF_SOURCE_SET (42007) inside a COMMAND_LONG frame to
 * switch the active EKF source set on the flight controller at runtime. The
 * autopilot maintains three pre-configured source sets (typically GPS-primary,
 * VIO-primary, and OF-primary); param1 selects which one becomes active.
 *
 * @module protocol/encoders/ekf-source
 */

import { encodeCommandLong } from "./core";

/** MAV_CMD identifier for switching the active EKF source set. */
export const MAV_CMD_SET_EKF_SOURCE_SET = 42007;

/**
 * Encode MAV_CMD_SET_EKF_SOURCE_SET inside a COMMAND_LONG frame.
 *
 * @param sourceSet - 1, 2, or 3, selects the active EKF source set
 * @param sysid     - sender system ID
 * @param compid    - sender component ID
 * @param targetSys - target system ID
 * @param targetComp - target component ID
 */
export function encodeSetEkfSourceSet(
  sourceSet: 1 | 2 | 3,
  sysid: number,
  compid: number,
  targetSys: number,
  targetComp: number,
): Uint8Array {
  return encodeCommandLong(
    targetSys,
    targetComp,
    MAV_CMD_SET_EKF_SOURCE_SET,
    sourceSet, // param1: source-set index (1, 2, or 3)
    0, 0, 0, 0, 0, 0, // params 2-7 unused
    sysid,
    compid,
  );
}
