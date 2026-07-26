/**
 * ArduPilot-style STATUSTEXT message templates for demo mode.
 *
 * Boot messages emitted once at start. Periodic messages chosen
 * contextually based on drone state (waypoint, battery, tick count).
 *
 * @license GPL-3.0-only
 */

/** MAVLink severity levels (MAV_SEVERITY). */
export const SEVERITY = {
  EMERGENCY: 0,
  ALERT: 1,
  CRITICAL: 2,
  ERROR: 3,
  WARNING: 4,
  NOTICE: 5,
  INFO: 6,
  DEBUG: 7,
} as const;

export interface StatusMessage {
  severity: number;
  text: string;
}

/** Boot sequence messages — emitted once in order. */
export const BOOT_MESSAGES: StatusMessage[] = [
  { severity: SEVERITY.INFO, text: "ArduCopter V4.5.7 (5f6a3b2c)" },
  { severity: SEVERITY.INFO, text: "ChibiOS: d4fce84e" },
  { severity: SEVERITY.INFO, text: "Frame: QUAD/X" },
  { severity: SEVERITY.INFO, text: "IMU0: fast sampling enabled 8.0kHz/1.0kHz" },
  { severity: SEVERITY.INFO, text: "GPS 1: u-blox 3D fix" },
  { severity: SEVERITY.NOTICE, text: "EKF3 IMU0 initialised" },
  { severity: SEVERITY.INFO, text: "Fence: enabled" },
  { severity: SEVERITY.INFO, text: "RCOut: PWM:1-4" },
  { severity: SEVERITY.INFO, text: "PreArm: Ready to arm" },
];

/** Periodic in-flight message templates. */
const FLIGHT_MESSAGES: StatusMessage[] = [
  { severity: SEVERITY.INFO, text: "EKF3 IMU0 is using GPS" },
  { severity: SEVERITY.NOTICE, text: "Vibration compensation ON" },
  { severity: SEVERITY.INFO, text: "Compass variance: 0.02" },
  { severity: SEVERITY.INFO, text: "GPS: 3D Fix" },
  { severity: SEVERITY.INFO, text: "Terrain data OK" },
  { severity: SEVERITY.INFO, text: "EKF3 IMU0 MAG0 in-flight yaw alignment complete" },
  { severity: SEVERITY.INFO, text: "Wind: 2.3m/s @ 125deg" },
  { severity: SEVERITY.DEBUG, text: "GPS Glitch cleared" },
];

const BATTERY_WARNINGS: StatusMessage[] = [
  { severity: SEVERITY.WARNING, text: "Battery 1 low" },
  { severity: SEVERITY.WARNING, text: "Battery failsafe" },
];

/**
 * Generate a contextual status message based on current drone state.
 */
export function generateStatusMessage(state: {
  waypointIndex: number;
  battery: number;
  tickCount: number;
}): StatusMessage | null {
  // Only emit roughly every 10-30s (at 5Hz = 50-150 ticks)
  if (state.tickCount % 75 !== 0 && Math.random() > 0.01) {
    return null;
  }

  // Battery warnings take priority
  if (state.battery < 25) {
    return BATTERY_WARNINGS[state.battery < 15 ? 1 : 0];
  }

  // Waypoint reached messages
  if (state.tickCount % 150 === 0 && state.waypointIndex > 0) {
    return {
      severity: SEVERITY.INFO,
      text: `Reached waypoint #${state.waypointIndex}`,
    };
  }

  // Random flight message
  const idx = Math.floor(Math.random() * FLIGHT_MESSAGES.length);
  return FLIGHT_MESSAGES[idx];
}
