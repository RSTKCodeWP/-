// ── Failsafe Constants ───────────────────────────────────────

export const RC_CHANNEL_COUNT = 8;

export const BF_FAILSAFE_PARAMS = [
  'BF_FS_DELAY',
  'BF_FS_OFF_DELAY',
  'BF_FS_THROTTLE',
  'BF_FS_PROCEDURE',
] as const;

export const BF_FS_PROCEDURE_OPTIONS = [
  { value: "0", label: "0 — Drop" },
  { value: "1", label: "1 — Land" },
  { value: "2", label: "2 — GPS Rescue" },
];

export const RC_OPTION_VALUES = [
  { value: "0", label: "0 — Do Nothing", description: "No action assigned to this channel" },
  { value: "2", label: "2 — Flip", description: "Trigger a flip maneuver" },
  { value: "3", label: "3 — Simple Mode", description: "Earth-frame heading control" },
  { value: "4", label: "4 — RTL", description: "Return to launch point and land" },
  { value: "7", label: "7 — Save WP", description: "Save current position as waypoint" },
  { value: "9", label: "9 — Camera Trigger", description: "Trigger camera shutter" },
  { value: "10", label: "10 — RangeFinder", description: "Enable/disable rangefinder" },
  { value: "11", label: "11 — Fence", description: "Enable/disable geofence" },
  { value: "16", label: "16 — Auto", description: "Switch to auto mission mode" },
  { value: "17", label: "17 — AutoTune", description: "Start automatic PID tuning" },
  { value: "18", label: "18 — Land", description: "Land at current position" },
  { value: "21", label: "21 — Parachute Enable", description: "Arm the parachute release mechanism" },
  { value: "22", label: "22 — Parachute Release", description: "Deploy parachute immediately" },
  { value: "28", label: "28 — Relay1 On/Off", description: "Toggle relay output 1" },
  { value: "39", label: "39 — Motor Emergency Stop", description: "Kill all motors immediately" },
  { value: "40", label: "40 — Motor Interlock", description: "Motors only spin when switch is active" },
  { value: "41", label: "41 — Brake", description: "Rapid stop and hold position" },
  { value: "55", label: "55 — Guided", description: "Switch to GCS-guided flight" },
  { value: "56", label: "56 — Loiter", description: "Hold GPS position and altitude" },
  { value: "57", label: "57 — Follow", description: "Follow another vehicle or GCS" },
];

/** ArduCopter FS_OPTIONS bitmask bits */
export const FS_OPTION_BITS = [
  { mask: 1 << 0, label: "Bit 0 — Continue if in auto mode on RC failsafe" },
  { mask: 1 << 1, label: "Bit 1 — Continue if in auto mode on GCS failsafe" },
  { mask: 1 << 2, label: "Bit 2 — Continue if in guided mode on RC failsafe" },
  { mask: 1 << 3, label: "Bit 3 — Continue if landing on any failsafe" },
  { mask: 1 << 4, label: "Bit 4 — Continue if in pilot controlled mode on GCS failsafe" },
  { mask: 1 << 5, label: "Bit 5 — Release gripper" },
];

// Vehicle-specific failsafe params
export const COPTER_FS_PARAMS = [
  "FS_SHORT_ACTN", "FS_SHORT_TIMEOUT", "FS_LONG_ACTN", "FS_LONG_TIMEOUT", "FS_GCS_ENABL",
  "TERRAIN_ENABLE", "FS_OPTIONS", "FS_THR_VALUE",
];

export const PLANE_FS_PARAMS = [
  "THR_FAILSAFE", "THR_FS_VALUE",
];

export const SHARED_FS_PARAMS = [
  "BATT_FS_VOLTSRC", "BATT_FS_LOW_VOLT", "BATT_FS_LOW_ACT",
  "FENCE_ENABLE", "FENCE_ACTION", "FENCE_ALT_MAX", "FENCE_RADIUS", "FENCE_ALT_MIN",
  ...Array.from({ length: RC_CHANNEL_COUNT }, (_, i) => `RC${i + 1}_OPTION`),
];

// ── Failsafe Card Component ─────────────────────────────────

// Re-exported from parent file — not a separate component file
// because the Card pattern is identical across all panels
