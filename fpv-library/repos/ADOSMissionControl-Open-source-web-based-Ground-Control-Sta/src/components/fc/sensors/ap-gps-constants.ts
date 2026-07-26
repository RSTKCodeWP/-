/**
 * @module fc/sensors/ap-gps-constants
 * @description Parameter names and option lists for the ArduPilot GPS panel.
 * Names + enum values follow the ArduPilot AP_GPS driver parameter set
 * (classic `GPS_*` naming, ArduPilot 4.5). Second-GPS, blending, moving-baseline
 * yaw, antenna offset, and driver-option params are optional so a single-GPS
 * build (or a firmware that renamed them per-instance) degrades cleanly rather
 * than erroring.
 * @license GPL-3.0-only
 */

/** Always-present single-GPS config. */
export const AP_GPS_CORE_PARAM_NAMES = [
  "GPS_TYPE",
  "GPS_AUTO_SWITCH",
  "GPS_GNSS_MODE",
  "GPS_RATE_MS",
  "GPS_SBAS_MODE",
  "GPS_MIN_ELEV",
  "GPS_AUTO_CONFIG",
] as const;

/** Second GPS, blending, yaw/moving-baseline, antenna offsets, driver options. */
export const AP_GPS_OPTIONAL_PARAM_NAMES = [
  "GPS_TYPE2",
  "GPS_PRIMARY",
  "GPS_BLEND_MASK",
  "GPS_NAVFILTER",
  "GPS_DRV_OPTIONS",
  "GPS_MB1_TYPE",
  "GPS_POS1_X",
  "GPS_POS1_Y",
  "GPS_POS1_Z",
] as const;

export const apGpsParamNames = [...AP_GPS_CORE_PARAM_NAMES];
export const apGpsOptionalParamNames = [...AP_GPS_OPTIONAL_PARAM_NAMES];

/** GPS receiver driver type (`GPS_TYPE` / `GPS_TYPE2`). */
export const AP_GPS_TYPE_OPTIONS = [
  { value: "0", label: "0 — None" },
  { value: "1", label: "1 — Auto" },
  { value: "2", label: "2 — uBlox" },
  { value: "5", label: "5 — NMEA" },
  { value: "6", label: "6 — SiRF" },
  { value: "7", label: "7 — HIL" },
  { value: "8", label: "8 — SwiftNav" },
  { value: "9", label: "9 — DroneCAN" },
  { value: "10", label: "10 — SBF (Septentrio)" },
  { value: "11", label: "11 — GSOF (Trimble)" },
  { value: "13", label: "13 — ERB" },
  { value: "14", label: "14 — MAV" },
  { value: "15", label: "15 — NOVA" },
  { value: "16", label: "16 — Hemisphere NMEA" },
  { value: "17", label: "17 — uBlox Moving Baseline Base" },
  { value: "18", label: "18 — uBlox Moving Baseline Rover" },
  { value: "19", label: "19 — MSP" },
  { value: "20", label: "20 — AllyStar" },
  { value: "21", label: "21 — External AHRS" },
  { value: "22", label: "22 — DroneCAN Moving Baseline Base" },
  { value: "23", label: "23 — DroneCAN Moving Baseline Rover" },
  { value: "24", label: "24 — Unicore NMEA" },
  { value: "25", label: "25 — Unicore Moving Baseline NMEA" },
  { value: "26", label: "26 — SBF Dual Antenna" },
];

/** Automatic switchover between two GPS units (`GPS_AUTO_SWITCH`). */
export const AP_GPS_AUTO_SWITCH_OPTIONS = [
  { value: "0", label: "0 — Use primary" },
  { value: "1", label: "1 — Use best" },
  { value: "2", label: "2 — Blend" },
  { value: "4", label: "4 — Use primary if 3D fix or better" },
];

/** Which GPS is preferred when auto-switch is off (`GPS_PRIMARY`). */
export const AP_GPS_PRIMARY_OPTIONS = [
  { value: "0", label: "0 — First GPS" },
  { value: "1", label: "1 — Second GPS" },
];

/** GPS update rate (`GPS_RATE_MS`). */
export const AP_GPS_RATE_OPTIONS = [
  { value: "100", label: "100 ms — 10 Hz" },
  { value: "125", label: "125 ms — 8 Hz" },
  { value: "200", label: "200 ms — 5 Hz" },
];

/** SBAS augmentation mode (`GPS_SBAS_MODE`). */
export const AP_GPS_SBAS_OPTIONS = [
  { value: "0", label: "0 — Disabled" },
  { value: "1", label: "1 — Enabled" },
  { value: "2", label: "2 — No change" },
];

/** Automatic receiver configuration (`GPS_AUTO_CONFIG`). */
export const AP_GPS_AUTO_CONFIG_OPTIONS = [
  { value: "0", label: "0 — Disabled" },
  { value: "1", label: "1 — Serial GPSes only" },
  { value: "2", label: "2 — Serial + DroneCAN" },
  { value: "3", label: "3 — Clear config (uBlox only)" },
];

/** Navigation dynamics filter preset (`GPS_NAVFILTER`). */
export const AP_GPS_NAVFILTER_OPTIONS = [
  { value: "0", label: "0 — Portable" },
  { value: "2", label: "2 — Stationary" },
  { value: "3", label: "3 — Pedestrian" },
  { value: "4", label: "4 — Automotive" },
  { value: "5", label: "5 — Sea" },
  { value: "6", label: "6 — Airborne <1g" },
  { value: "7", label: "7 — Airborne <2g" },
  { value: "8", label: "8 — Airborne <4g" },
];

/** Moving-baseline (GPS-for-yaw) base type (`GPS_MB1_TYPE`). */
export const AP_GPS_MB_TYPE_OPTIONS = [
  { value: "0", label: "0 — Relative to alternate GPS" },
  { value: "1", label: "1 — Relative to custom base" },
];
