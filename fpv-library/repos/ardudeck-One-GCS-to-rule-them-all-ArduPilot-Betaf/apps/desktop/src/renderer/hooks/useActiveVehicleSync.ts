/**
 * Keeps the active-vehicle store in sync with the main-process registry.
 *
 * Mounted once at app startup (by App.tsx). Performs an initial hydrate via
 * COMMS_LIST_VEHICLES so the renderer has the registry's view of the world,
 * then subscribes to COMMS_VEHICLE_DISCOVERED / COMMS_VEHICLE_LOST to stay
 * current. Single-vehicle UX is unchanged: the store auto-promotes the first
 * discovered vehicle to active.
 */

import { useEffect } from 'react';
import { useActiveVehicleStore } from '../stores/active-vehicle-store';
import { useFleetTelemetryStore } from '../stores/fleet-telemetry-store';
import { useOrchestrationStore } from '../stores/orchestration-store';
import { useMessagesStore } from '../stores/messages-store';
import { applyActiveSelectionFromBroadcast } from './useFleet';

export function useActiveVehicleSync(): void {
  const recordDiscovered = useActiveVehicleStore((s) => s.recordDiscovered);
  const recordLost = useActiveVehicleStore((s) => s.recordLost);
  const hydrate = useActiveVehicleStore((s) => s.hydrate);

  useEffect(() => {
    const api = window.electronAPI;
    if (!api) return;

    // Initial hydrate from the main process registry. Covers hot-reload, where
    // the renderer reattaches to a main process that already has vehicles.
    api.listVehicles?.().then(hydrate).catch((err: unknown) => {
      console.warn('[useActiveVehicleSync] initial listVehicles failed', err);
    });

    const offDiscovered = api.onVehicleDiscovered?.((vehicle) => {
      recordDiscovered(vehicle);
    });

    const offLost = api.onVehicleLost?.((vehicleKey) => {
      recordLost(vehicleKey);
      useFleetTelemetryStore.getState().removeVehicle(vehicleKey);
    });

    // Engine intent feedback -> Messages panel. The engine answers every intent
    // (take off all, form up, break) with acks / status / errors, but they were
    // only shown on the connection screen - so a refused takeoff on the telemetry
    // screen looked like "nothing happened, no reason". Repeats per intent id are
    // collapsed (the follow loop re-sends the same running status at 1 Hz).
    const lastIntentText = new Map<string, string>();
    const offOrch = api.onOrchestrationStatus?.((status) => {
      useOrchestrationStore.getState().applyStatus(status);
      if (status.kind === 'control' && status.control) {
        const c = status.control;
        const text = [c.state, c.message].filter(Boolean).join(' - ');
        if (!text) return;
        const key = String(c.id ?? c.type ?? 'engine');
        if (lastIntentText.get(key) === text) return;
        lastIntentText.set(key, text);
        const isErr = c.type === 'error' || c.state === 'rejected' || c.state === 'failed';
        useMessagesStore.getState().addMessage(isErr ? 3 : 6, isErr ? 'ERROR' : 'INFO', `Engine: ${text}`);
      }
    });

    // Follow active-vehicle changes made in other windows (e.g. the 3D world).
    const offActive = api.onActiveVehicleChanged?.((payload) => {
      applyActiveSelectionFromBroadcast(payload.transportId, payload.vehicleKey ?? null);
    });

    return () => {
      offDiscovered?.();
      offLost?.();
      offOrch?.();
      offActive?.();
    };
  }, [recordDiscovered, recordLost, hydrate]);
}
