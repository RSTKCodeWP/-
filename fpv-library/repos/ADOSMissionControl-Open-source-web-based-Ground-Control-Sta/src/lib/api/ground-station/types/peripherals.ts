/**
 * @module api/ground-station/types/peripherals
 * @description Types for the Peripheral Manager surface (transport-agnostic
 * device summaries + action descriptors).
 *
 * @license GPL-3.0-only
 */

export interface PeripheralMatch {
  vid?: string;
  pid?: string;
  regex?: string;
}

export interface PeripheralAction {
  id: string;
  display_name: string;
  requires_confirm: boolean;
  body_schema?: unknown;
}

export type PeripheralTransport = "usb" | "serial" | "network" | "ble";

export interface PeripheralSummary {
  id: string;
  display_name: string;
  transport: PeripheralTransport;
  connected: boolean;
  capabilities: string[];
}

export interface PeripheralDetail extends PeripheralSummary {
  match: PeripheralMatch;
  actions: PeripheralAction[];
  config_schema?: unknown;
  status_endpoint?: string;
  extra?: Record<string, unknown>;
}

export interface PeripheralListResponse {
  peripherals: PeripheralSummary[];
  count: number;
}
