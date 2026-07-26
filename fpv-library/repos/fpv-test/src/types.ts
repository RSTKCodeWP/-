/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

export enum ActiveView {
  DASHBOARD = "dashboard",
  CONFIGURATOR = "configurator",
  ACADEMY = "academy",
  SIMULATOR = "simulator",
  SPECS = "specs"
}

export type FlightMode = "ACRO" | "ANGLE" | "HORIZON" | "FAILSAFE";

export interface DronePart {
  id: string;
  name: string;
  category: "frame" | "motor" | "props" | "vtx";
  weight: number; // grams
  price: number;
  specs: Record<string, string | number>;
  description: string;
}

export interface DroneConfig {
  frame: DronePart;
  motor: DronePart;
  props: DronePart;
  vtx: DronePart;
}
