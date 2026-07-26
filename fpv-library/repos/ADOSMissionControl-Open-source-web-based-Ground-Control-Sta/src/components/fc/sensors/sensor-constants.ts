// Sensor panel parameter names and option arrays

export const SENSOR_PARAMS = [
  "GND_ABS_PRESS", "GND_TEMP", "BARO_PRIMARY",
];

// ArduPilot supports up to 10 rangefinders: RNGFND1..RNGFND9 then RNGFNDA.
// Instance 1 is handled inline (with live distance); 2..A are the extra
// instances rendered on demand.
export const RNGFND_EXTRA_INSTANCES = ["2", "3", "4", "5", "6", "7", "8", "9", "A"] as const;
export const RNGFND_INSTANCE_FIELDS = ["TYPE", "PIN", "MIN_CM", "MAX_CM", "ORIENT"] as const;
export const RNGFND_EXTRA_PARAMS = RNGFND_EXTRA_INSTANCES.flatMap((n) =>
  RNGFND_INSTANCE_FIELDS.map((f) => `RNGFND${n}_${f}`),
);

export const OPTIONAL_SENSOR_PARAMS = [
  "RNGFND1_TYPE", "RNGFND1_PIN", "RNGFND1_MIN_CM", "RNGFND1_MAX_CM", "RNGFND1_ORIENT",
  ...RNGFND_EXTRA_PARAMS,
  "FLOW_TYPE", "FLOW_FXSCALER", "FLOW_FYSCALER", "FLOW_ORIENT_YAW",
  "ARSPD_TYPE", "ARSPD_USE", "ARSPD_OFFSET", "ARSPD_RATIO",
  // PX4 rangefinder and EKF2 range params (silently fail on ArduPilot)
  "SENS_EN_MB12XX", "SENS_EN_LL40LS", "SENS_EN_SF1XX",
  "EKF2_RNG_AID", "EKF2_RNG_A_HMAX", "EKF2_RNG_NOISE", "EKF2_RNG_SFE", "EKF2_MIN_RNG",
];

export const RNGFND_TYPE_OPTIONS = [
  { value: "0", label: "0 — None" },
  { value: "1", label: "1 — Analog" },
  { value: "2", label: "2 — MaxbotixI2C" },
  { value: "5", label: "5 — PX4" },
  { value: "9", label: "9 — LightWareI2C" },
  { value: "10", label: "10 — MAVLink" },
  { value: "16", label: "16 — Benewake TFmini" },
  { value: "17", label: "17 — LightWareSerial" },
  { value: "20", label: "20 — Benewake TF02" },
];

export const RNGFND_ORIENT_OPTIONS = [
  { value: "0", label: "0 — Forward" },
  { value: "24", label: "24 — Up" },
  { value: "25", label: "25 — Down" },
];

export const FLOW_TYPE_OPTIONS = [
  { value: "0", label: "0 — None" },
  { value: "1", label: "1 — PX4Flow" },
  { value: "2", label: "2 — Pixart" },
  { value: "5", label: "5 — PMW3901" },
];

export const ARSPD_TYPE_OPTIONS = [
  { value: "0", label: "0 — None" },
  { value: "1", label: "1 — MS4525D" },
  { value: "2", label: "2 — Analog" },
  { value: "3", label: "3 — MS5525" },
  { value: "7", label: "7 — DLVR" },
  { value: "8", label: "8 — UAVCAN" },
];
