/**
 * Pure config + helpers for the SITL test-condition bench (SimTestPanel).
 *
 * ArduPilot SITL exposes SIM_* parameters that perturb the simulation live; we
 * set them over MAVLink PARAM_SET so real failsafes fire on the real flight code.
 * This module holds the param names, the engine-failure bitmask helper, the
 * one-click scenario presets, and the safe-defaults reset - kept separate from
 * the React panel so the fiddly bits (esp. the bitmask) are unit-testable.
 */

/** MAVLink PARAM type we send everything as. ArduPilot casts to the param's real
    type on receive, so REAL32 is safe for the INT8 SIM_* params too. */
export const PARAM_REAL32 = 9;

/**
 * Bitmask of motors to fail, from 1-indexed motor numbers.
 *
 * On current ArduPilot, SIM_ENGINE_FAIL is a *motor bitmask* (bit 0 = motor 1),
 * NOT an engine index - and the thrust of the masked motors is scaled by
 * SIM_ENGINE_MUL. The old panel set SIM_ENGINE_FAIL=0 (which now selects NO
 * motor) so SIM_ENGINE_MUL=0 had nothing to act on and the failure never fired.
 */
export function engineFailMask(motors: Iterable<number>): number {
  let mask = 0;
  for (const n of motors) if (n >= 1) mask |= 1 << (n - 1);
  return mask;
}

/**
 * The full set of test-condition state. A "patch" (Partial) is what presets and
 * the reset apply; the panel maps each present field to its SIM_* param(s).
 */
export interface SimConditions {
  /** 1-indexed motor numbers currently failed. */
  failedMotors: number[];
  /** Thrust multiplier for failed motors (0 = dead, 1 = full). */
  engineMul: number;
  gpsEnable: boolean;
  gpsJam: boolean;
  /** Horizontal position glitch magnitude in metres (sets GLTCH_X and _Y). */
  gpsGlitch: number;
  /** Reported satellite count (10 = healthy). */
  gpsSats: number;
  baroDisable: boolean;
  mag1Fail: boolean;
  mag2Fail: boolean;
  /** Motor-driven vibration amplitude (SIM_VIB_MOT_MAX, m/s/s). */
  vibe: number;
  rcFail: boolean;
  windSpd: number;
  windDir: number;
  windTurb: number;
}

export type SimPatch = Partial<SimConditions>;

/** Safe defaults - what "Reset all" restores (battery is handled separately,
    keyed off the vehicle's live pack voltage). */
export const SIM_DEFAULTS: SimConditions = {
  failedMotors: [],
  engineMul: 1,
  gpsEnable: true,
  gpsJam: false,
  gpsGlitch: 0,
  gpsSats: 10,
  baroDisable: false,
  mag1Fail: false,
  mag2Fail: false,
  vibe: 0,
  rcFail: false,
  windSpd: 0,
  windDir: 0,
  windTurb: 0,
};

export interface SimPreset {
  id: string;
  label: string;
  tip: string;
  patch: SimPatch;
}

/** One-click failure scenarios. Each is a patch applied over current state. */
export const SIM_PRESETS: SimPreset[] = [
  { id: 'motor-out', label: 'Motor out', tip: 'Kill motor 1 (SIM_ENGINE_FAIL bit0, SIM_ENGINE_MUL 0)', patch: { failedMotors: [1], engineMul: 0 } },
  { id: 'gps-denied', label: 'GPS denied', tip: 'Disable GPS to trigger the GPS-loss failsafe / EKF fallback (SIM_GPS1_ENABLE 0)', patch: { gpsEnable: false } },
  { id: 'gps-glitch', label: 'GPS glitch', tip: '30 m position jump (SIM_GPS1_GLTCH_X/Y)', patch: { gpsGlitch: 30 } },
  { id: 'gps-jam', label: 'GPS jam', tip: 'Jam GPS reception (SIM_GPS1_JAM 1)', patch: { gpsJam: true } },
  { id: 'low-sats', label: 'Sat dropout', tip: 'Degrade to 4 satellites (SIM_GPS1_NUMSATS 4)', patch: { gpsSats: 4 } },
  { id: 'compass-fail', label: 'Compass fail', tip: 'Fail both compasses (SIM_MAG1_FAIL / SIM_MAG2_FAIL 1)', patch: { mag1Fail: true, mag2Fail: true } },
  { id: 'baro-fail', label: 'Baro fail', tip: 'Disable the barometer (SIM_BARO_DISABLE 1)', patch: { baroDisable: true } },
  { id: 'radio-loss', label: 'Radio loss', tip: 'Drop RC to trigger the radio failsafe (SIM_RC_FAIL 1)', patch: { rcFail: true } },
  { id: 'high-vibe', label: 'High vibe', tip: 'Inject motor vibration (SIM_VIB_MOT_MAX 30)', patch: { vibe: 30 } },
];
