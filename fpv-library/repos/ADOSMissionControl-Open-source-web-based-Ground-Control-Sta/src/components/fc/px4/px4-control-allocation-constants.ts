/**
 * PX4 control-allocation (CA_*) field definitions. Enum labels + ranges come
 * from the bundled PX4 param metadata; only CA_R_REV's bit meaning (which the
 * metadata does not decompose) is supplied here from firmware.
 *
 * @module fc/px4/px4-control-allocation-constants
 */

// Exempt from 300 LOC soft rule: protocol data table.

/** Per-section counts at the firmware maxima: rotors 12, surfaces 8, tilts 4. */
export const CA_MAX_ROTORS = 12;
export const CA_MAX_SURFACES = 8;
export const CA_MAX_TILTS = 4;

/** CA_R_REV bit N = Motor N+1 (bidirectional / reversible), 12 motors. */
export const CA_R_REV_BITS = new Map<number, string>(
  Array.from({ length: 12 }, (_, i): [number, string] => [i, `Motor ${i + 1}`]),
);

export interface CaField {
  param: string;
  label: string;
  kind: "enum" | "number";
}

export const caRotorFields = (i: number): CaField[] => [
  { param: `CA_ROTOR${i}_CT`, label: "Thrust coeff (CT)", kind: "number" },
  { param: `CA_ROTOR${i}_KM`, label: "Moment coeff (KM)", kind: "number" },
  { param: `CA_ROTOR${i}_AX`, label: "Axis X", kind: "number" },
  { param: `CA_ROTOR${i}_AY`, label: "Axis Y", kind: "number" },
  { param: `CA_ROTOR${i}_AZ`, label: "Axis Z", kind: "number" },
  { param: `CA_ROTOR${i}_TILT`, label: "Tilt assignment", kind: "enum" },
  { param: `CA_R${i}_SLEW`, label: "Slew rate (s)", kind: "number" },
];

export const caSurfaceFields = (i: number): CaField[] => [
  { param: `CA_SV_CS${i}_TYPE`, label: "Surface type", kind: "enum" },
  { param: `CA_SV_CS${i}_TRQ_R`, label: "Roll torque", kind: "number" },
  { param: `CA_SV_CS${i}_TRQ_P`, label: "Pitch torque", kind: "number" },
  { param: `CA_SV_CS${i}_TRQ_Y`, label: "Yaw torque", kind: "number" },
  { param: `CA_SV_CS${i}_TRIM`, label: "Trim", kind: "number" },
];

export const caTiltFields = (i: number): CaField[] => [
  { param: `CA_SV_TL${i}_CT`, label: "Controls", kind: "enum" },
  { param: `CA_SV_TL${i}_MINA`, label: "Min angle (deg)", kind: "number" },
  { param: `CA_SV_TL${i}_MAXA`, label: "Max angle (deg)", kind: "number" },
  { param: `CA_SV_TL${i}_TD`, label: "Tilt direction", kind: "enum" },
];

/** Every CA_* param the panel may read (counts + all indexed slots). */
export const CA_ALL_PARAM_NAMES: string[] = (() => {
  const names = ["CA_AIRFRAME", "CA_METHOD", "CA_R_REV", "CA_ROTOR_COUNT", "CA_SV_CS_COUNT", "CA_SV_TL_COUNT"];
  for (let i = 0; i < CA_MAX_ROTORS; i++) names.push(...caRotorFields(i).map((f) => f.param));
  for (let i = 0; i < CA_MAX_SURFACES; i++) names.push(...caSurfaceFields(i).map((f) => f.param));
  for (let i = 0; i < CA_MAX_TILTS; i++) names.push(...caTiltFields(i).map((f) => f.param));
  return names;
})();
