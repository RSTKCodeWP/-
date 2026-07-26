import { create } from "zustand";

const SENSOR_BITS: Record<number, { name: string; label: string }> = {
  0: { name: "gyro_3d", label: "3D Gyro" },
  1: { name: "accel_3d", label: "3D Accel" },
  2: { name: "mag_3d", label: "3D Mag" },
  3: { name: "abs_pressure", label: "Abs Pressure" },
  4: { name: "diff_pressure", label: "Diff Pressure" },
  5: { name: "gps", label: "GPS" },
  6: { name: "optical_flow", label: "Optical Flow" },
  7: { name: "vision_position", label: "Vision Position" },
  8: { name: "laser_position", label: "Laser Position" },
  9: { name: "external_ground_truth", label: "External GT" },
  10: { name: "angular_rate_control", label: "Rate Control" },
  11: { name: "attitude_stabilization", label: "Attitude Stab" },
  12: { name: "yaw_position", label: "Yaw Position" },
  13: { name: "z_altitude_control", label: "Z/Alt Control" },
  14: { name: "xy_position_control", label: "XY Position" },
  15: { name: "motor_outputs", label: "Motor Outputs" },
  16: { name: "rc_receiver", label: "RC Receiver" },
  17: { name: "gyro2_3d", label: "3D Gyro 2" },
  18: { name: "accel2_3d", label: "3D Accel 2" },
  19: { name: "mag2_3d", label: "3D Mag 2" },
  20: { name: "geofence", label: "Geofence" },
  21: { name: "ahrs", label: "AHRS" },
  22: { name: "terrain", label: "Terrain" },
  23: { name: "reverse_motor", label: "Reverse Motor" },
  24: { name: "logging", label: "Logging" },
  25: { name: "battery", label: "Battery" },
  26: { name: "proximity", label: "Proximity" },
  27: { name: "satcom", label: "Satcom" },
  28: { name: "pre_arm_check", label: "Pre-Arm Check" },
  29: { name: "obstacle_avoidance", label: "Obstacle Avoid" },
  30: { name: "propulsion", label: "Propulsion" },
  31: { name: "extension", label: "Extension" },
};

type SensorStatus = "healthy" | "unhealthy" | "error" | "not_present";

interface SensorInfo {
  name: string;
  label: string;
  bit: number;
  present: boolean;
  enabled: boolean;
  healthy: boolean;
  status: SensorStatus;
}

interface SensorHealthStoreState {
  sensors: SensorInfo[];
  lastUpdate: number;

  updateFromSysStatus: (sensorsPresent: number, sensorsEnabled: number, sensorsHealthy: number) => void;
  getSensorByName: (name: string) => SensorInfo | undefined;
  getHealthySensorCount: () => number;
  getTotalPresentCount: () => number;
  clear: () => void;
}

function decodeSensors(present: number, enabled: number, healthy: number): SensorInfo[] {
  const sensors: SensorInfo[] = [];
  for (let bit = 0; bit < 32; bit++) {
    const def = SENSOR_BITS[bit];
    if (!def) continue;

    const mask = 1 << bit;
    const isPresent = (present & mask) !== 0;
    const isEnabled = (enabled & mask) !== 0;
    const isHealthy = (healthy & mask) !== 0;

    let status: SensorStatus;
    if (!isPresent) {
      status = "not_present";
    } else if (isHealthy) {
      status = "healthy";
    } else if (isEnabled) {
      // present + enabled but NOT healthy = error
      status = "error";
    } else {
      // present but not enabled and not healthy = unhealthy
      status = "unhealthy";
    }

    sensors.push({
      name: def.name,
      label: def.label,
      bit,
      present: isPresent,
      enabled: isEnabled,
      healthy: isHealthy,
      status,
    });
  }
  return sensors;
}

export const useSensorHealthStore = create<SensorHealthStoreState>((set, get) => ({
  sensors: [],
  lastUpdate: 0,

  updateFromSysStatus: (sensorsPresent, sensorsEnabled, sensorsHealthy) => {
    set({
      sensors: decodeSensors(sensorsPresent, sensorsEnabled, sensorsHealthy),
      lastUpdate: Date.now(),
    });
  },

  getSensorByName: (name) => get().sensors.find((s) => s.name === name),

  getHealthySensorCount: () => get().sensors.filter((s) => s.status === "healthy").length,

  getTotalPresentCount: () => get().sensors.filter((s) => s.present).length,

  clear: () =>
    set({
      sensors: [],
      lastUpdate: 0,
    }),
}));
