/**
 * Per-vehicle telemetry, keyed by vehicleKey.
 *
 * The legacy `telemetry-store` holds a single flat snapshot that the existing
 * views read; it now reflects only the *active* vehicle (gated in App.tsx). This
 * store holds the accumulated telemetry for *every* vehicle so the fleet strip
 * and the multi-marker map (Sub-spec C) can render all vehicles at once without
 * disturbing the single-vehicle views.
 *
 * Fed by the same TELEMETRY_BATCH IPC stream: App.tsx routes each batch here by
 * its tagged `__vehicleKey`, then also applies it to the flat store when it is
 * the active vehicle.
 *
 * Batches are coalesced: a swarm of N vehicles at 10Hz would otherwise publish
 * N*10 store updates/sec, and every `byVehicle` subscriber (fleet strip, map
 * markers, minimap, control panel) re-renders on each one - at 20 vehicles that
 * is 200 re-renders/sec and the telemetry page crawls. Incoming batches merge
 * into a pending buffer and a single set() flushes at most every FLUSH_MS.
 * The active vehicle's HUD/dashboard is unaffected (it reads the flat store,
 * which App.tsx feeds directly at full rate).
 */

import { create } from 'zustand';
import type { TelemetryBatch } from './telemetry-store';

/** Accumulated telemetry for one vehicle. Same optional-field shape as a batch. */
export type VehicleTelemetry = Omit<TelemetryBatch, '__vehicleKey'> & {
  /** Wall-clock ms of the last batch applied to this vehicle. */
  lastUpdate: number;
};

interface FleetTelemetryStore {
  byVehicle: Record<string, VehicleTelemetry>;
  /** Merge a batch into a vehicle's accumulated telemetry (coalesced, see above). */
  applyBatch: (vehicleKey: string, batch: TelemetryBatch) => void;
  /** Drop a vehicle's telemetry (on vehicle lost / disconnect). */
  removeVehicle: (vehicleKey: string) => void;
  clear: () => void;
}

const FLUSH_MS = 150;

export const useFleetTelemetryStore = create<FleetTelemetryStore>((set, get) => {
  let pending: Record<string, VehicleTelemetry> = {};
  let flushTimer: ReturnType<typeof setTimeout> | null = null;
  let lastFlush = 0;

  const flush = () => {
    if (flushTimer !== null) { clearTimeout(flushTimer); flushTimer = null; }
    lastFlush = Date.now();
    if (Object.keys(pending).length === 0) return;
    const merged = pending;
    pending = {};
    set({ byVehicle: { ...get().byVehicle, ...merged } });
  };

  return {
    byVehicle: {},

    applyBatch: (vehicleKey, batch) => {
      const { __vehicleKey: _ignored, ...fields } = batch;
      const base = pending[vehicleKey] ?? get().byVehicle[vehicleKey];
      pending[vehicleKey] = { ...base, ...fields, lastUpdate: Date.now() };
      const elapsed = Date.now() - lastFlush;
      // Negative elapsed = wall clock stepped backwards; flush rather than stall.
      if (elapsed >= FLUSH_MS || elapsed < 0) {
        flush();
      } else if (flushTimer === null) {
        flushTimer = setTimeout(flush, FLUSH_MS - elapsed);
      }
    },

    removeVehicle: (vehicleKey) => {
      delete pending[vehicleKey];
      const next = { ...get().byVehicle };
      delete next[vehicleKey];
      set({ byVehicle: next });
    },

    clear: () => {
      pending = {};
      if (flushTimer !== null) { clearTimeout(flushTimer); flushTimer = null; }
      set({ byVehicle: {} });
    },
  };
});
