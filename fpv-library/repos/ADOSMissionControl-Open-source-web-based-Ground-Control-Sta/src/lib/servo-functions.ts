/**
 * Complete ArduPilot servo function database.
 *
 * Covers all 100+ servo function IDs across all ArduPilot vehicle types
 * (Copter and Plane SERVOx_FUNCTION values).
 *
 * @license GPL-3.0-only
 */

// ── Types ─────────────────────────────────────────────────────

export interface ServoFunction {
  value: number;
  label: string;
}

export interface ServoFunctionGroup {
  label: string;
  functions: ServoFunction[];
}

// ── Grouped Database ──────────────────────────────────────────

export const SERVO_FUNCTION_GROUPS: ServoFunctionGroup[] = [
  {
    label: "General",
    functions: [
      { value: -1, label: "GPIO" },
      { value: 0, label: "Disabled" },
      { value: 1, label: "RCPassThru" },
    ],
  },
  {
    label: "Control Surfaces (Plane)",
    functions: [
      { value: 2, label: "Flap" },
      { value: 3, label: "FlapAuto" },
      { value: 4, label: "Aileron" },
      { value: 16, label: "DiffSpoilerLeft1" },
      { value: 17, label: "DiffSpoilerRight1" },
      { value: 19, label: "Elevator" },
      { value: 21, label: "Rudder" },
      { value: 24, label: "FlaperonLeft" },
      { value: 25, label: "FlaperonRight" },
      { value: 26, label: "GroundSteering" },
      { value: 77, label: "ElevonLeft" },
      { value: 78, label: "ElevonRight" },
      { value: 79, label: "VTailLeft" },
      { value: 80, label: "VTailRight" },
      { value: 86, label: "DiffSpoilerLeft2" },
      { value: 87, label: "DiffSpoilerRight2" },
    ],
  },
  {
    label: "Motors",
    functions: [
      { value: 33, label: "Motor 1" },
      { value: 34, label: "Motor 2" },
      { value: 35, label: "Motor 3" },
      { value: 36, label: "Motor 4" },
      { value: 37, label: "Motor 5" },
      { value: 38, label: "Motor 6" },
      { value: 39, label: "Motor 7" },
      { value: 40, label: "Motor 8" },
      { value: 82, label: "Motor 9" },
      { value: 83, label: "Motor 10" },
      { value: 84, label: "Motor 11" },
      { value: 85, label: "Motor 12" },
    ],
  },
  {
    label: "Throttle / Engine",
    functions: [
      { value: 30, label: "EngineRunEnable" },
      { value: 67, label: "Ignition" },
      { value: 69, label: "Starter" },
      { value: 70, label: "Throttle" },
      { value: 73, label: "ThrottleLeft" },
      { value: 74, label: "ThrottleRight" },
      { value: 81, label: "BoostThrottle" },
    ],
  },
  {
    label: "Tilt Motors (VTOL/QuadPlane)",
    functions: [
      { value: 41, label: "TiltMotorsFront" },
      { value: 45, label: "TiltMotorsRear" },
      { value: 46, label: "TiltMotorRearLeft" },
      { value: 47, label: "TiltMotorRearRight" },
      { value: 75, label: "TiltMotorFrontLeft" },
      { value: 76, label: "TiltMotorFrontRight" },
    ],
  },
  {
    label: "Helicopter",
    functions: [
      { value: 31, label: "HeliRSC" },
      { value: 32, label: "HeliTailRSC" },
    ],
  },
  {
    label: "Gimbal / Mount",
    functions: [
      { value: 6, label: "Mount1Pan" },
      { value: 7, label: "Mount1Tilt" },
      { value: 8, label: "Mount1Roll" },
      { value: 9, label: "Mount1Open" },
      { value: 12, label: "Mount2Pan" },
      { value: 13, label: "Mount2Tilt" },
      { value: 14, label: "Mount2Roll" },
      { value: 15, label: "Mount2Open" },
    ],
  },
  {
    label: "Camera",
    functions: [
      { value: 10, label: "CameraTrigger" },
      { value: 90, label: "CameraISO" },
      { value: 91, label: "CameraAperture" },
      { value: 92, label: "CameraFocus" },
      { value: 93, label: "CameraShutterSpeed" },
    ],
  },
  {
    label: "Payload / Utility",
    functions: [
      { value: 27, label: "Parachute" },
      { value: 28, label: "Gripper" },
      { value: 29, label: "LandingGear" },
      { value: 88, label: "Winch" },
      { value: 133, label: "WinchClutch" },
    ],
  },
  {
    label: "Sprayer (Agriculture)",
    functions: [
      { value: 22, label: "SprayerPump" },
      { value: 23, label: "SprayerSpinner" },
    ],
  },
  {
    label: "RC Input Passthrough",
    functions: [
      { value: 51, label: "RCIN1" },
      { value: 52, label: "RCIN2" },
      { value: 53, label: "RCIN3" },
      { value: 54, label: "RCIN4" },
      { value: 55, label: "RCIN5" },
      { value: 56, label: "RCIN6" },
      { value: 57, label: "RCIN7" },
      { value: 58, label: "RCIN8" },
      { value: 59, label: "RCIN9" },
      { value: 60, label: "RCIN10" },
      { value: 61, label: "RCIN11" },
      { value: 62, label: "RCIN12" },
      { value: 63, label: "RCIN13" },
      { value: 64, label: "RCIN14" },
      { value: 65, label: "RCIN15" },
      { value: 66, label: "RCIN16" },
    ],
  },
  {
    label: "Scripting / Lua",
    functions: [
      { value: 94, label: "Script1" },
      { value: 95, label: "Script2" },
      { value: 96, label: "Script3" },
      { value: 97, label: "Script4" },
      { value: 98, label: "Script5" },
      { value: 99, label: "Script6" },
      { value: 100, label: "Script7" },
      { value: 101, label: "Script8" },
      { value: 102, label: "Script9" },
      { value: 103, label: "Script10" },
      { value: 104, label: "Script11" },
      { value: 105, label: "Script12" },
      { value: 106, label: "Script13" },
      { value: 107, label: "Script14" },
      { value: 108, label: "Script15" },
      { value: 109, label: "Script16" },
    ],
  },
  {
    label: "Rate Controller",
    functions: [
      { value: 124, label: "RateRoll" },
      { value: 125, label: "RatePitch" },
      { value: 126, label: "RateThrust" },
      { value: 127, label: "RateYaw" },
    ],
  },
  {
    label: "LED / Lighting",
    functions: [
      { value: 120, label: "NeoPixel1" },
      { value: 121, label: "NeoPixel2" },
      { value: 122, label: "NeoPixel3" },
      { value: 123, label: "NeoPixel4" },
      { value: 129, label: "ProfiLED1" },
      { value: 130, label: "ProfiLED2" },
      { value: 131, label: "ProfiLED3" },
      { value: 132, label: "ProfiLEDClock" },
    ],
  },
  {
    label: "Servo Passthrough",
    functions: [
      { value: 134, label: "SERVOn_MIN" },
      { value: 135, label: "SERVOn_TRIM" },
      { value: 136, label: "SERVOn_MAX" },
    ],
  },
  {
    label: "Alarm",
    functions: [
      { value: 138, label: "Alarm" },
      { value: 139, label: "AlarmInverted" },
    ],
  },
];

// ── Flat Lookup Map ───────────────────────────────────────────

/** Fast value → label lookup for inline display. */
export const SERVO_FUNCTION_MAP: Map<number, string> = new Map(
  SERVO_FUNCTION_GROUPS.flatMap((g) =>
    g.functions.map((fn) => [fn.value, fn.label] as [number, string])
  )
);

/** Get display label for a servo function ID, with fallback. */
export function getServoFunctionLabel(value: number): string {
  return SERVO_FUNCTION_MAP.get(value) ?? `Unknown (${value})`;
}
