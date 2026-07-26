export const RC_CHANNEL_COUNT = 16;

export const CHANNEL_OPTIONS = Array.from({ length: RC_CHANNEL_COUNT }, (_, i) => ({
  value: String(i + 1),
  label: `Channel ${i + 1}`,
}));

export const RC_PROTOCOLS_OPTIONS = [
  { value: "1", label: "1 — PPM" },
  { value: "2", label: "2 — IBUS" },
  { value: "4", label: "4 — SBUS" },
  { value: "8", label: "8 — SBUS_NI" },
  { value: "16", label: "16 — DSM" },
  { value: "32", label: "32 — SUMD" },
  { value: "64", label: "64 — SRXL" },
  { value: "128", label: "128 — SRXL2" },
  { value: "256", label: "256 — CRSF" },
  { value: "512", label: "512 — ST24" },
  { value: "1024", label: "1024 — FPort" },
  { value: "2048", label: "2048 — FPort2" },
  { value: "4096", label: "4096 — GHST" },
];

export const RSSI_TYPE_OPTIONS = [
  { value: "0", label: "0 — Disabled" },
  { value: "1", label: "1 — Analog Pin" },
  { value: "2", label: "2 — RC Channel PWM" },
  { value: "3", label: "3 — Receiver Protocol" },
  { value: "4", label: "4 — Telemetry Radio RSSI" },
  { value: "5", label: "5 — CRSF/ELRS" },
];

export const RECEIVER_PARAMS: string[] = [
  "RCMAP_ROLL", "RCMAP_PITCH", "RCMAP_THROTTLE", "RCMAP_YAW",
  "RC_PROTOCOLS", "RSSI_TYPE",
  ...Array.from({ length: RC_CHANNEL_COUNT }, (_, i) => {
    const n = i + 1;
    return [`RC${n}_MIN`, `RC${n}_MAX`, `RC${n}_TRIM`, `RC${n}_REVERSED`, `RC${n}_DZ`];
  }).flat(),
];
