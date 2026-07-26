// lib/presets/types.ts — Build preset type definitions for Command GCS
// SPDX-License-Identifier: GPL-3.0-only

/** Hardware component type in the build manifest. */
export type ComponentType =
  | "compute"
  | "fc"
  | "esc"
  | "motor"
  | "sensor"
  | "camera"
  | "radio"
  | "gps"
  | "battery"
  | "frame"
  | "rangefinder"
  | "companion";

/** A single hardware component in the build. */
export interface BuildComponent {
  type: ComponentType;
  name: string;
  count: number;
  details?: Record<string, string | number>;
}

/** Physical specs summary. */
export interface BuildSpecs {
  propSize: string;
  motorSize: string;
  motorKv: number;
  cells: number;
  batteryMah: number;
  auwGrams: number;
  flightTimeMin: number;
  hasGps: boolean;
  hasCompass: boolean;
  hasRangefinder: boolean;
  hasCompute: boolean;
}

/** Category for grouping presets in UI. */
export type PresetCategory = "fpv" | "long-range" | "heavy-lift" | "cine" | "racing" | "micro" | "reference";

/** Complete build preset definition (GCS side — no SITL mapping). */
export interface BuildPreset {
  id: string;
  name: string;
  description: string;
  category: PresetCategory;
  components: BuildComponent[];
  specs: BuildSpecs;
}
