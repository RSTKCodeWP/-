import type { CalibrationStatus, CalibrationStep } from "./CalibrationWizard";

export interface CompassResult {
  ofsX: number; ofsY: number; ofsZ: number;
  fitness: number; calStatus: number;
  diagX: number; diagY: number; diagZ: number;
  offdiagX: number; offdiagY: number; offdiagZ: number;
  orientationConfidence: number;
  oldOrientation: number; newOrientation: number;
  scaleFactor: number;
}

export interface CalibrationState {
  status: CalibrationStatus;
  currentStep: number;
  progress: number;
  message: string;
  waitingForConfirm: boolean;
  accelCalPosition: number | null;
  compassProgress: Map<number, number>;
  compassStatus: Map<number, number>;
  compassResults: Map<number, CompassResult>;
  compassCompletionMask: Map<number, number[]>;
  compassDirection: Map<number, { x: number; y: number; z: number }>;
  needsReboot: boolean;
  failureFixes: string[];
  commandAccepted: boolean;
}

export const INITIAL_STATE: CalibrationState = {
  status: "idle",
  currentStep: 0,
  progress: 0,
  message: "",
  waitingForConfirm: false,
  accelCalPosition: null,
  compassProgress: new Map(),
  compassStatus: new Map(),
  compassResults: new Map(),
  compassCompletionMask: new Map(),
  compassDirection: new Map(),
  needsReboot: false,
  failureFixes: [],
  commandAccepted: false,
};

// ArduPilot ACCELCAL_VEHICLE_POS enum: 1=Level, 2=Left, 3=Right, 4=NoseDown, 5=NoseUp, 6=Back
export const ACCEL_STEPS: CalibrationStep[] = [
  { label: "Level", description: "Place vehicle level on a flat surface" },
  { label: "Left Side", description: "Rotate vehicle so left side faces down" },
  { label: "Right Side", description: "Rotate vehicle so right side faces down" },
  { label: "Nose Down", description: "Point the nose straight down" },
  { label: "Nose Up", description: "Point the nose straight up" },
  { label: "Back", description: "Place vehicle upside-down" },
];

export const GYRO_STEPS: CalibrationStep[] = [
  { label: "Keep Still", description: "Keep the vehicle perfectly still on a level surface" },
];

export const COMPASS_STEPS: CalibrationStep[] = [
  { label: "Rotate", description: "Slowly rotate the vehicle in all orientations — roll, pitch, and yaw" },
];

export const LEVEL_STEPS: CalibrationStep[] = [
  { label: "Level Surface", description: "Place vehicle on a perfectly level surface" },
];

export const AIRSPEED_STEPS: CalibrationStep[] = [
  { label: "Cover Pitot", description: "Cover the pitot tube opening to seal it from airflow" },
];

export const BARO_STEPS: CalibrationStep[] = [
  { label: "Stabilize", description: "Keep vehicle still in current environment — do not cover barometer" },
];

export const RC_CAL_STEPS: CalibrationStep[] = [
  { label: "Center Sticks", description: "Move all sticks to center position and all switches to default" },
  { label: "Move Sticks", description: "Move all sticks and switches to their full extent in all directions" },
  { label: "Center Again", description: "Return all sticks to center position" },
];

export const ESC_CAL_STEPS: CalibrationStep[] = [
  { label: "Safety", description: "REMOVE ALL PROPELLERS. Disconnect battery. Ensure ESCs are powered off" },
  { label: "Max Throttle", description: "Set throttle to maximum and connect battery" },
  { label: "Wait for Beep", description: "Wait for ESC beep sequence (high-low tones)" },
  { label: "Min Throttle", description: "Set throttle to minimum — wait for confirmation beeps" },
];

export const COMPASSMOT_STEPS: CalibrationStep[] = [
  { label: "Setup", description: "Place vehicle in open area. Ensure GPS fix. Remove nearby metal objects" },
  { label: "Run Test", description: "Motors will spin — stay clear. Interference is measured at various throttle levels" },
];

/** Keywords per calibration type — only messages containing these are shown */
export const TYPE_KEYWORDS: Record<string, string[]> = {
  accel: ["accel", "place vehicle"],
  gyro: ["gyro", "imu"],
  compass: ["compass", "mag"],
  level: ["level", "horizon", "trim"],
  airspeed: ["airspeed", "pitot"],
  baro: ["baro", "ground pressure"],
  rc: ["radio", "rc ", "trim", "calibrat"],
  esc: ["esc", "motor", "throttle"],
  compassmot: ["compassmot", "interference", "compensation"],
};

/** Human-readable compass calibration failure messages with actionable fixes */
export const MAG_CAL_FAIL_MESSAGES: Record<number, { message: string; fixes: string[] }> = {
  5: {
    message: "Calibration failed — strong magnetic interference detected",
    fixes: [
      "Move at least 10m away from metal objects, vehicles, buildings, and power lines",
      "Remove phone, tools, and metal accessories from nearby",
      "If using USB power, try battery power (USB cables create EMI)",
    ],
  },
  6: {
    message: "Calibration failed — insufficient rotation coverage",
    fixes: [
      "Rotate SLOWLY (2-3 sec per orientation) — fast rotation drops samples",
      "Cover all 6 faces: front, back, left, right, nose-up, nose-down",
      "Add 4 diagonal corners for full sphere coverage",
      "Total calibration should take 2-3 minutes of continuous rotation",
      "Try setting COMPASS_AUTO_ROT=3 if orientation detection is failing",
    ],
  },
  7: {
    message: "Calibration failed — magnetic field radius out of range (150-950 mGauss)",
    fixes: [
      "Severe magnetic interference — move compass further from motors/ESCs/battery",
      "If external compass, mount on a mast at least 15cm above the frame",
      "Check compass wiring — loose I2C connection can cause erratic readings",
    ],
  },
};

/** Keywords to capture for the calibration log */
export const LOG_KEYWORDS = [
  "calibrat", "accel", "gyro", "compass", "mag", "level",
  "place vehicle", "baro", "airspeed", "pitot", "horizon",
  "radio", "rc ", "esc", "motor", "throttle", "compassmot",
  "interference", "compensation", "trim", "imu", "offsets",
  "[cal]",  // PX4 calibration STATUSTEXT prefix
];

/** Per-type calibration timeout in ms */
export const CAL_TIMEOUTS: Record<string, number> = {
  accel: 300_000,       // 5 min — 6 physical repositions
  gyro: 60_000,         // 1 min
  compass: 120_000,     // 2 min
  level: 60_000,        // 1 min
  airspeed: 60_000,     // 1 min
  baro: 60_000,         // 1 min
  rc: 120_000,          // 2 min — manual stick movement
  esc: 120_000,         // 2 min — boot sequence
  compassmot: 180_000,  // 3 min — motor spin + data collection
};

export const MAX_LOG_ENTRIES = 200;

export interface CalibrationLogEntry {
  timestamp: number;
  text: string;
  severity: number;
}

export const SEVERITY_COLORS: Record<number, string> = {
  0: "text-status-error",     // EMERGENCY
  1: "text-status-error",     // ALERT
  2: "text-status-error",     // CRITICAL
  3: "text-status-error",     // ERROR
  4: "text-status-warning",   // WARNING
  5: "text-text-secondary",   // NOTICE
  6: "text-text-tertiary",    // INFO
  7: "text-text-tertiary",    // DEBUG
};
