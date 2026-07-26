/**
 * MSP request payload encoders.
 *
 * Pure functions — each returns a Uint8Array payload (NOT the full MSP frame).
 * The codec wraps these payloads into MSPv1/v2 frames.
 *
 * All multi-byte values are little-endian.
 *
 * This module is a facade over the encoders/ folder: implementation lives
 * in per-subsystem files (tuning, power, config, osd-led, nav, control)
 * plus shared buffer helpers.
 *
 * @module protocol/msp/msp-encoders
 */

// ── Tuning: PID, RC tuning, filters, advanced, adjustment ranges ─────────
export {
  encodeMspSetAdjustmentRange,
  encodeMspSetPid,
  encodeMspSetRcTuning,
  encodeMspSetFilterConfig,
  encodeMspSetAdvancedConfig,
} from "./encoders/tuning";

// ── Power: motor config, battery config, raw motor ──────────────────────
export {
  encodeMspSetMotorConfig,
  encodeMspSetBatteryConfig,
  encodeMspSetMotor,
} from "./encoders/power";

// ── Config: feature mask, serial, failsafe, arming, mode ranges, beeper ──
export {
  encodeMspSetFeatureConfig,
  encodeMspSetSerialConfig,
  encodeMspSetFailsafeConfig,
  encodeMspSetArmingConfig,
  encodeMspSetModeRange,
  encodeMspSetBeeperConfig,
} from "./encoders/config";

// ── OSD / LED strip / VTX ───────────────────────────────────────────────
export {
  encodeMspSetOsdConfig,
  encodeMspOsdCharWrite,
  encodeMspSetLedStripConfigEntry,
  encodeMspSetVtxConfig,
} from "./encoders/osd-led";

// ── Navigation: GPS config, GPS Rescue ───────────────────────────────────
export {
  encodeMspSetGpsConfig,
  encodeMspSetGpsRescue,
} from "./encoders/nav";

// ── Control: raw RC, reboot, blackbox config ────────────────────────────
export {
  encodeMspSetRawRc,
  encodeMspSetReboot,
  encodeMspSetBlackboxConfig,
} from "./encoders/control";
