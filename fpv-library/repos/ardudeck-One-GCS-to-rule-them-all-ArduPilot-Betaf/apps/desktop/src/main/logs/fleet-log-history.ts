/**
 * Fleet log history persistence + maintenance-flag derivation.
 *
 * Stores one compact FlightSummary per parsed log, grouped by vehicle, so the
 * Fleet Forensics view can show health trends and maintenance flags across many
 * aircraft over time without re-parsing every .bin. Capped per vehicle so the
 * store stays bounded.
 */
import Store from 'electron-store';
import type {
  FlightSummary,
  VehicleFlightHistory,
} from '../../shared/fleet-log-types.js';
export { deriveMaintenanceFlags } from '../../shared/fleet-log-maintenance.js';

const MAX_FLIGHTS_PER_VEHICLE = 200;

const historyStore = new Store<{ flights: FlightSummary[] }>({
  name: 'fleet-log-history',
  defaults: { flights: [] },
});

/** Append a flight summary, de-duplicating by file path (re-opening a log updates it). */
export function recordFlight(summary: FlightSummary): void {
  const all = historyStore.get('flights').filter((f) => f.path !== summary.path);
  all.push(summary);
  // Keep only the most recent N per vehicle to bound growth.
  const byVehicle = new Map<string, FlightSummary[]>();
  for (const f of all) {
    const list = byVehicle.get(f.vehicleKey) ?? [];
    list.push(f);
    byVehicle.set(f.vehicleKey, list);
  }
  const trimmed: FlightSummary[] = [];
  for (const list of byVehicle.values()) {
    list.sort((a, b) => b.startedAt - a.startedAt);
    trimmed.push(...list.slice(0, MAX_FLIGHTS_PER_VEHICLE));
  }
  historyStore.set('flights', trimmed);
}

/** All flights grouped by vehicle, newest first within each. */
export function getFleetHistory(): VehicleFlightHistory[] {
  const all = historyStore.get('flights');
  const byVehicle = new Map<string, FlightSummary[]>();
  for (const f of all) {
    const list = byVehicle.get(f.vehicleKey) ?? [];
    list.push(f);
    byVehicle.set(f.vehicleKey, list);
  }
  const out: VehicleFlightHistory[] = [];
  for (const [vehicleKey, flights] of byVehicle) {
    flights.sort((a, b) => b.startedAt - a.startedAt);
    out.push({ vehicleKey, vehicleLabel: flights[0]!.vehicleLabel, flights });
  }
  // Vehicles with the most recent activity first.
  out.sort((a, b) => (b.flights[0]?.startedAt ?? 0) - (a.flights[0]?.startedAt ?? 0));
  return out;
}

export function clearFleetHistory(): void {
  historyStore.set('flights', []);
}
