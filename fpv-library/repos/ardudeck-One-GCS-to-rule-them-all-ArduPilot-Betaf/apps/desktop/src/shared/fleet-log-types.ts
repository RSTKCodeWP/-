/**
 * Fleet log aggregation types — the roll-up of per-flight log analysis across
 * many vehicles over time (Fleet Forensics).
 *
 * Each parsed log produces one compact FlightSummary keyed to a vehicle
 * identity. Summaries persist so the app can show health trends and maintenance
 * flags across a fleet without re-parsing every .bin. The single-flight analyzer
 * is untouched; this is purely additive.
 */

export type FlightHealthStatus = 'pass' | 'warn' | 'fail' | 'skip' | 'info';

export interface FlightHealthFlag {
  id: string;
  name: string;
  status: FlightHealthStatus;
  summary: string;
}

export interface FlightSummary {
  flightId: string;
  /** Stable per-vehicle key derived from board type + SYSID_THISMAV. */
  vehicleKey: string;
  vehicleLabel: string;
  boardType: string;
  vehicleType: string;
  firmwareVersion: string;
  sysid: number | null;
  fileName: string;
  path: string;
  /** Flight start, epoch ms (GPS time when available, else file mtime). */
  startedAt: number;
  durationSec: number;
  maxAltM: number;
  maxGroundSpeedMps: number;
  distanceM: number;
  /** Battery consumed (mAh) if the log carried current totals. */
  batteryMah: number;
  /** Lowest pack voltage seen (V), 0 if no battery data. */
  minBatteryV: number;
  /** Peak vibration magnitude (m/s^2). */
  maxVibe: number;
  health: FlightHealthFlag[];
}

export interface VehicleFlightHistory {
  vehicleKey: string;
  vehicleLabel: string;
  /** Newest first. */
  flights: FlightSummary[];
}

/** A derived maintenance concern surfaced from a vehicle's flight history. */
export interface MaintenanceFlag {
  vehicleKey: string;
  severity: 'info' | 'warn' | 'fail';
  title: string;
  detail: string;
}
