/**
 * @module protocol/msp/msp-sensor-flags
 * @description Translate an MSP `MSP_STATUS` / `MSP_STATUS_EX` sensor bitmask
 * into the MAVLink `MAV_SYS_STATUS_SENSOR` bit layout the GCS sensor-health
 * surfaces decode.
 *
 * The two layouts differ. MSP packs the sensor word as
 * ACC(0), BARO(1), MAG(2), GPS(3), RANGEFINDER(4); bit 5 is firmware-specific
 * (Betaflight: gyro; iNav: optical flow) and iNav additionally reports
 * PITOT(6). MAVLink's `MAV_SYS_STATUS_SENSOR` is gyro(0), accel(1), mag(2),
 * abs-pressure(3), diff-pressure(4), gps(5), optical-flow(6), laser(8).
 *
 * Stuffing the raw MSP word into the MAVLink-shaped sensor fields (as the
 * telemetry dispatch used to) mislabels every chip for an MSP flight
 * controller. Translating once at the MSP source keeps every downstream
 * consumer on the single MAVLink layout.
 * @license GPL-3.0-only
 */

// MAVLink MAV_SYS_STATUS_SENSOR bit positions.
const MAV_GYRO = 1 << 0;
const MAV_ACCEL = 1 << 1;
const MAV_MAG = 1 << 2;
const MAV_ABS_PRESSURE = 1 << 3;
const MAV_DIFF_PRESSURE = 1 << 4;
const MAV_GPS = 1 << 5;
const MAV_OPTICAL_FLOW = 1 << 6;
const MAV_LASER_POSITION = 1 << 8;

// MSP sensor word bit positions (packed by the flight controller).
const MSP_ACC = 1 << 0;
const MSP_BARO = 1 << 1;
const MSP_MAG = 1 << 2;
const MSP_GPS = 1 << 3;
const MSP_RANGEFINDER = 1 << 4;
const MSP_BIT5 = 1 << 5; // Betaflight: gyro; iNav: optical flow
const MSP_INAV_PITOT = 1 << 6;

/**
 * Convert an MSP sensor bitmask to a MAVLink `MAV_SYS_STATUS_SENSOR` bitmask.
 *
 * The bit-5 (and iNav bit-6) interpretation is firmware-specific, so the
 * caller must pass the identified firmware. Any non-iNav value is treated as
 * Betaflight (gyro at bit 5), which is the correct default for the only other
 * MSP firmware the GCS drives.
 */
export function mspSensorFlagsToMavlink(
  mspFlags: number,
  firmwareType: string | null | undefined,
): number {
  let out = 0;
  if (mspFlags & MSP_ACC) out |= MAV_ACCEL;
  if (mspFlags & MSP_BARO) out |= MAV_ABS_PRESSURE;
  if (mspFlags & MSP_MAG) out |= MAV_MAG;
  if (mspFlags & MSP_GPS) out |= MAV_GPS;
  if (mspFlags & MSP_RANGEFINDER) out |= MAV_LASER_POSITION;
  if (firmwareType === "inav") {
    if (mspFlags & MSP_BIT5) out |= MAV_OPTICAL_FLOW;
    if (mspFlags & MSP_INAV_PITOT) out |= MAV_DIFF_PRESSURE;
  } else {
    if (mspFlags & MSP_BIT5) out |= MAV_GYRO;
  }
  return out;
}
