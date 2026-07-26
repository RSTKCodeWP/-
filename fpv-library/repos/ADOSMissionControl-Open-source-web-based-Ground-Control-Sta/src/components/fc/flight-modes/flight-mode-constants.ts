import type { UnifiedFlightMode } from "@/lib/protocol/types";

// ── Mode descriptions ────────────────────────────────────────

export const MODE_DESCRIPTIONS: Partial<Record<UnifiedFlightMode, string>> = {
  STABILIZE: "Self-leveling with manual throttle",
  ACRO: "Rate-based control, no self-leveling",
  ALT_HOLD: "Maintains altitude, pilot controls roll/pitch/yaw",
  AUTO: "Follows uploaded mission autonomously",
  GUIDED: "Fly to commanded positions via GCS",
  LOITER: "GPS hold position and altitude",
  RTL: "Return to launch point and land",
  LAND: "Descend and land at current position",
  CIRCLE: "Circle around a point of interest",
  POSHOLD: "GPS and optical flow position hold",
  AUTOTUNE: "Automatic PID tuning in flight",
  MANUAL: "Direct passthrough to control surfaces",
  FBWA: "Fly-by-wire with manual throttle",
  FBWB: "Fly-by-wire with auto throttle",
  CRUISE: "Level flight with heading lock",
  TRAINING: "Limited roll/pitch for training",
  BRAKE: "Rapid stop and hold position",
  SMART_RTL: "Retrace path back to launch",
  DRIFT: "Coordinated turn flight, easy FPV",
  SPORT: "Rate-controlled with self-leveling",
  FLIP: "Automated flip maneuver",
  THROW: "Launch by throwing the vehicle",
  QSTABILIZE: "VTOL stabilize mode",
  QHOVER: "VTOL altitude hold",
  QLOITER: "VTOL GPS position hold",
  QLAND: "VTOL land mode",
  QRTL: "VTOL return to launch",
  QAUTOTUNE: "VTOL automatic PID tuning",
  QACRO: "VTOL rate-based control",
  FLOWHOLD: "Optical flow position hold without GPS",
  FOLLOW: "Follow another vehicle or GCS",
  ZIGZAG: "Fly zigzag pattern between waypoints A & B",
  SYSTEMID: "System identification for dynamic response characterization",
  HELI_AUTOROTATE: "Helicopter autorotation emergency landing",
  AUTO_RTL: "Return via Smart RTL path then switch to AUTO",
  TAKEOFF: "Automatic takeoff sequence",
  LOITER_TO_QLAND: "Loiter then transition to VTOL landing",
  AVOID_ADSB: "Automatic avoidance of ADS-B equipped aircraft",
  THERMAL: "Soaring in thermal updrafts",
};

// ── PWM ranges per mode slot (6 slots, standard ArduPilot) ──

export const MODE_PWM_RANGES = [
  { label: "PWM 0–1230", min: 0, max: 1230 },
  { label: "PWM 1231–1360", min: 1231, max: 1360 },
  { label: "PWM 1361–1490", min: 1361, max: 1490 },
  { label: "PWM 1491–1620", min: 1491, max: 1620 },
  { label: "PWM 1621–1749", min: 1621, max: 1749 },
  { label: "PWM 1750–2000", min: 1750, max: 2000 },
];

export const MODE_SLOT_COUNT = 6;

// ── Types ────────────────────────────────────────────────────

export interface ModeSlotConfig {
  mode: string;
  simple: boolean;
  superSimple: boolean;
}

export interface FlightModeGlobalConfig {
  modeChannel: string;
  initialMode: string;
}

export function defaultSlot(): ModeSlotConfig {
  return { mode: "STABILIZE", simple: false, superSimple: false };
}

export function defaultGlobalConfig(): FlightModeGlobalConfig {
  return { modeChannel: "5", initialMode: "0" };
}
