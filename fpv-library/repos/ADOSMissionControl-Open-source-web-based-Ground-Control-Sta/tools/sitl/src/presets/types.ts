// presets/types.ts — Build preset type definitions for SITL
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
  propSize: string;       // e.g. "7\"", "5\"", "13\""
  motorSize: string;      // e.g. "2806.5"
  motorKv: number;
  cells: number;          // battery S count
  batteryMah: number;
  auwGrams: number;       // all-up weight in grams
  flightTimeMin: number;  // estimated flight time in minutes
  hasGps: boolean;
  hasCompass: boolean;
  hasRangefinder: boolean;
  hasCompute: boolean;    // companion computer
}

/** Category for grouping presets in UI. */
export type PresetCategory = "fpv" | "long-range" | "heavy-lift" | "cine" | "racing" | "micro" | "reference";

/** ArduPilot SITL vehicle type. */
export type SitlVehicle = "ArduCopter" | "ArduPlane" | "ArduRover";

/** SITL-specific mapping for sim_vehicle.py. */
export interface SitlMapping {
  vehicle: SitlVehicle;
  frame: string;           // -f flag (e.g. "quad", "hexa", "quadplane")
  paramOverrides: Record<string, number>;  // -P KEY=VALUE pairs
}

/** Complete build preset definition. */
export interface BuildPreset {
  id: string;
  name: string;
  description: string;
  category: PresetCategory;
  components: BuildComponent[];
  specs: BuildSpecs;
  sitl: SitlMapping;
}
