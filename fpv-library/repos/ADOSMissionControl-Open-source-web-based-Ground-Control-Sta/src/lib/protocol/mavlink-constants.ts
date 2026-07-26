/**
 * MAVLink constants and bitmask definitions.
 * @module protocol/mavlink-constants
 * @license GPL-3.0-only
 */

/** MAV_SYS_STATUS_SENSOR bitmask definitions. */
export const MAV_SYS_STATUS_SENSOR: ReadonlyMap<number, { name: string; shortName: string }> = new Map([
  [0,  { name: "3D Gyroscope",      shortName: "Gyro" }],
  [1,  { name: "3D Accelerometer",  shortName: "Accel" }],
  [2,  { name: "3D Magnetometer",   shortName: "Compass" }],
  [3,  { name: "Barometer",         shortName: "Baro" }],
  [4,  { name: "Differential Pressure", shortName: "DiffPress" }],
  [5,  { name: "GPS",               shortName: "GPS" }],
  [6,  { name: "Optical Flow",      shortName: "OptFlow" }],
  [7,  { name: "Vision Position",   shortName: "VisPOS" }],
  [8,  { name: "Laser Position",    shortName: "LaserPOS" }],
  [9,  { name: "Ext. Ground Truth", shortName: "ExtGT" }],
  [10, { name: "Angular Rate Ctrl", shortName: "RateCtl" }],
  [11, { name: "Attitude Ctrl",     shortName: "AttCtl" }],
  [12, { name: "Yaw Position",      shortName: "YawPos" }],
  [13, { name: "Z/Alt Control",     shortName: "AltCtl" }],
  [14, { name: "XY Position Ctrl",  shortName: "PosCtl" }],
  [15, { name: "Motor Outputs",     shortName: "Motors" }],
  [16, { name: "RC Receiver",       shortName: "RC" }],
  [17, { name: "Gyro 2",            shortName: "Gyro2" }],
  [18, { name: "Accel 2",           shortName: "Accel2" }],
  [19, { name: "Mag 2",             shortName: "Compass2" }],
  [20, { name: "GeoFence",          shortName: "Fence" }],
  [21, { name: "AHRS",              shortName: "AHRS" }],
  [22, { name: "Terrain",           shortName: "Terrain" }],
  [23, { name: "Reverse Thrust",    shortName: "RevThr" }],
  [24, { name: "Logging",           shortName: "Log" }],
  [25, { name: "Battery",           shortName: "Batt" }],
  [26, { name: "Proximity",         shortName: "Prox" }],
  [27, { name: "Satellite Comm",    shortName: "SatCom" }],
  [28, { name: "Pre-Arm Check",     shortName: "PreArm" }],
  [29, { name: "Obstacle Avoid",    shortName: "ObsAvoid" }],
  [30, { name: "Propulsion",        shortName: "Prop" }],
]);

/**
 * Parse sensor bitmasks into an array of sensor health objects.
 * Each bit position corresponds to a sensor type.
 */
export interface SensorHealth {
  id: number;
  name: string;
  shortName: string;
  present: boolean;
  enabled: boolean;
  healthy: boolean;
}

export function parseSensorHealth(
  present: number,
  enabled: number,
  health: number,
): SensorHealth[] {
  const sensors: SensorHealth[] = [];
  for (const [bit, info] of MAV_SYS_STATUS_SENSOR) {
    const mask = 1 << bit;
    const isPresent = (present & mask) !== 0;
    if (isPresent) {
      sensors.push({
        id: bit,
        name: info.name,
        shortName: info.shortName,
        present: true,
        enabled: (enabled & mask) !== 0,
        healthy: (health & mask) !== 0,
      });
    }
  }
  return sensors;
}
