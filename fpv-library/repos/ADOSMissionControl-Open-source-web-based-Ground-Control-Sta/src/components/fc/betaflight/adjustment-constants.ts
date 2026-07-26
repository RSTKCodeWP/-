export const ADJUSTMENT_SLOT_COUNT = 4;

/**
 * Adjustment function names (Betaflight MSP_ADJUSTMENT_RANGES).
 * 33 functions (0-32) matching BF Configurator AdjustmentsTab.vue.
 */
export const ADJUSTMENT_FUNCTIONS = [
  { value: "0", label: "RC Rate" },
  { value: "1", label: "RC Expo" },
  { value: "2", label: "Throttle Expo" },
  { value: "3", label: "Roll Rate" },
  { value: "4", label: "Pitch Rate" },
  { value: "5", label: "Yaw Rate" },
  { value: "6", label: "PID Roll P" },
  { value: "7", label: "PID Roll I" },
  { value: "8", label: "PID Roll D" },
  { value: "9", label: "PID Pitch P" },
  { value: "10", label: "PID Pitch I" },
  { value: "11", label: "PID Pitch D" },
  { value: "12", label: "PID Yaw P" },
  { value: "13", label: "PID Yaw I" },
  { value: "14", label: "PID Yaw D" },
  { value: "15", label: "PID Roll F" },
  { value: "16", label: "PID Pitch F" },
  { value: "17", label: "PID Yaw F" },
  { value: "18", label: "Rate Profile" },
  { value: "19", label: "PID Profile" },
  { value: "20", label: "OSD Profile" },
  { value: "21", label: "LED Profile" },
  { value: "22", label: "Gyro LPF" },
  { value: "23", label: "D-term LPF" },
  { value: "24", label: "RC Rate Yaw" },
  { value: "25", label: "PID Audio" },
  { value: "26", label: "Roll Pitch Ratio" },
  { value: "27", label: "Anti Gravity" },
  { value: "28", label: "Landing Gear" },
  { value: "29", label: "OSD Profile Change" },
  { value: "30", label: "LED Profile Change" },
  { value: "31", label: "Rates Collection" },
  { value: "32", label: "Slider Master Multiplier" },
];

export const AUX_CHANNELS = Array.from({ length: 12 }, (_, i) => ({
  value: String(i),
  label: `AUX ${i + 1}`,
}));

export function buildAdjustmentParamNames(): string[] {
  const names: string[] = [];
  for (let i = 0; i < ADJUSTMENT_SLOT_COUNT; i++) {
    names.push(
      `BF_ADJ${i}_ENABLE`,
      `BF_ADJ${i}_CHANNEL`,
      `BF_ADJ${i}_RANGE_LOW`,
      `BF_ADJ${i}_RANGE_HIGH`,
      `BF_ADJ${i}_FUNCTION`,
      `BF_ADJ${i}_VIA_CHANNEL`,
    );
  }
  return names;
}
