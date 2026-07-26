export const BLACKBOX_PARAM_NAMES = [
  "BF_BLACKBOX_DEVICE",
  "BF_BLACKBOX_RATE_NUM",
  "BF_BLACKBOX_RATE_DENOM",
] as const;

export const blackboxParamNames = [...BLACKBOX_PARAM_NAMES];

export const DEVICE_OPTIONS = [
  { value: "0", label: "0 — None" },
  { value: "1", label: "1 — Onboard Flash" },
  { value: "2", label: "2 — SD Card" },
  { value: "3", label: "3 — Serial Port" },
];

export const RATE_PRESETS = [
  { num: 1, denom: 1, label: "1/1 (100%)" },
  { num: 1, denom: 2, label: "1/2 (50%)" },
  { num: 1, denom: 4, label: "1/4 (25%)" },
  { num: 1, denom: 8, label: "1/8 (12.5%)" },
  { num: 1, denom: 16, label: "1/16 (6.25%)" },
];

export interface DataflashSummary {
  totalSize: number;
  usedSize: number;
  ready: boolean;
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
