/**
 * iNav-specific MSP encoders barrel.
 *
 * Implementation lives in per-family files under `encoders/inav/`:
 *   - settings      : MSP2_COMMON_SETTING / SET_SETTING / SETTING_INFO
 *   - misc          : MSP2_INAV_SET_MISC
 *   - battery       : MSP2_INAV_SET_BATTERY_CONFIG
 *   - geozone       : MSP2_INAV_SET_GEOZONE / SET_GEOZONE_VERTEX
 *   - profile       : MSP2_INAV_SELECT_BATTERY_PROFILE / SELECT_MIXER_PROFILE
 *   - servo         : MSP2_INAV_SET_SERVO_CONFIG / SET_SERVO_MIXER
 *   - tuning        : MSP2_INAV_SET_MC_BRAKING / SET_RATE_DYNAMICS / EZ_TUNE_SET
 *   - timer         : MSP2_INAV_SET_TIMER_OUTPUT_MODE
 *   - fw-approach   : MSP2_INAV_SET_FW_APPROACH
 *   - osd           : MSP2_INAV_OSD_SET_ALARMS / SET_PREFERENCES / SET_CUSTOM_OSD_ELEMENTS
 *   - programming   : MSP2_INAV_SET_LOGIC_CONDITIONS / SET_PROGRAMMING_PID
 *   - motor-mixer   : MSP2_COMMON_SET_MOTOR_MIXER (shared with iNav)
 *
 * Two extra encoders that physically live in the iNav decoders module
 * (encodeMspSetWp, encodeMspINavSetSafehome) are re-exported here for
 * backward compat so callers continue to import everything from this path.
 *
 * All multi-byte values are little-endian to match MSP wire convention.
 *
 * @module protocol/msp/msp-encoders-inav
 */

// ── Encoders that live in the decoders file (backward compat) ─────
export { encodeMspSetWp, encodeMspINavSetSafehome } from './msp-decoders-inav';

// ── Per-family iNav encoders ──────────────────────────────────────
export {
  encodeCommonSetting,
  encodeCommonSetSetting,
  encodeCommonSettingInfo,
  encodeCommonSettingInfoByIndex,
} from './encoders/inav/settings';

export { encodeMspINavSetMisc } from './encoders/inav/misc';

export { encodeMspINavSetBatteryConfig } from './encoders/inav/battery';

export {
  encodeMspINavSetGeozone,
  encodeMspINavSetGeozoneVertex,
} from './encoders/inav/geozone';

export {
  encodeMspINavSelectBatteryProfile,
  encodeMspINavSelectMixerProfile,
} from './encoders/inav/profile';

export {
  encodeMspINavSetServoConfig,
  encodeMspINavSetServoMixer,
} from './encoders/inav/servo';

export {
  encodeMspINavSetMcBraking,
  encodeMspINavSetRateDynamics,
  encodeMspINavSetEzTune,
} from './encoders/inav/tuning';

export { encodeMspINavSetTimerOutputMode } from './encoders/inav/timer';

export { encodeMspINavSetFwApproach } from './encoders/inav/fw-approach';

export {
  encodeMspINavSetOsdAlarms,
  encodeMspINavSetOsdPreferences,
  encodeMspINavSetCustomOsdElement,
} from './encoders/inav/osd';

export {
  encodeMspINavSetLogicCondition,
  encodeMspINavSetProgrammingPid,
  encodeMspINavSetGvar,
} from './encoders/inav/programming';

export { encodeMspCommonSetMotorMixer } from './encoders/inav/motor-mixer';
