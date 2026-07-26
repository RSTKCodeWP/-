/**
 * Active vehicle store - renderer-side mirror of the connection registry's
 * known vehicles plus the user's "currently selected" pointer.
 *
 * Role:
 *   - Mirrors the registry's vehicle list (kept in sync via the
 *     COMMS_VEHICLE_DISCOVERED / COMMS_VEHICLE_LOST IPC events).
 *   - Holds the active vehicle pointer that per-vehicle store projections will
 *     read (Sub-spec B) and the fleet UI will drive (Sub-spec C).
 *   - Auto-promotes the first discovered vehicle to active so single-vehicle
 *     users see no behavioral change at all.
 */

import { create } from 'zustand';
import type { VehicleInfoIpc } from '../../shared/ipc-channels';

interface ActiveVehicleState {
  /** The currently selected vehicle's key, or null if nothing is selected. */
  activeVehicleKey: string | null;
  /** The transport that owns the active vehicle. Cached for convenience. */
  activeTransportId: string | null;
  /**
   * Every vehicle the registry has reported. Indexed by `key` for fast lookup;
   * stored as a record (not a Map) so selector subscribers get structural
   * equality.
   */
  knownVehicles: Record<string, VehicleInfoIpc>;
  /**
   * Vehicles the user has multi-selected for group commands (fleet strip
   * checkboxes). Independent of the single active vehicle.
   */
  selectedVehicleKeys: string[];

  /**
   * Active leader-follower formations: leader key -> member keys (leader first,
   * then its wingmen). Several formations can run at once - the fleet strip nests
   * each group under its leader; vehicles in no formation stay free cards. A
   * vehicle belongs to at most one formation (setFormation strips it elsewhere).
   */
  formations: Record<string, string[]>;

  /** Set the active selection. Pass null for both to clear. */
  setActive: (transportId: string | null, vehicleKey: string | null) => void;

  /** Toggle a vehicle's membership in the group-command selection. */
  toggleSelected: (vehicleKey: string) => void;
  /** Replace the group-command selection. */
  setSelected: (vehicleKeys: string[]) => void;

  /** Register/replace a formation. Members are removed from any other formation. */
  setFormation: (leaderKey: string, memberKeys: string[]) => void;
  /** Drop one formation (its vehicles become free). */
  removeFormation: (leaderKey: string) => void;
  /** Drop every formation. */
  clearFormations: () => void;

  /**
   * Record a vehicle the registry just discovered. Adds it to `knownVehicles`
   * and, if nothing is active, auto-promotes it. The auto-promotion keeps
   * single-vehicle behavior unchanged: the first heartbeat after connect makes
   * the new vehicle active with no extra UI step.
   */
  recordDiscovered: (vehicle: VehicleInfoIpc) => void;

  /**
   * Drop a vehicle the registry has lost, by key. Removes it from
   * `knownVehicles` and, if it was active, clears the active pointer.
   */
  recordLost: (vehicleKey: string) => void;

  /** Replace the entire known-vehicles map (used after a COMMS_LIST_VEHICLES poll). */
  hydrate: (vehicles: VehicleInfoIpc[]) => void;

  /** Clear everything - used by mode switching and disconnect-all flows. */
  clearAll: () => void;
}

export const useActiveVehicleStore = create<ActiveVehicleState>((set, get) => ({
  activeVehicleKey: null,
  activeTransportId: null,
  knownVehicles: {},
  selectedVehicleKeys: [],
  formations: {},

  setActive: (transportId, vehicleKey) => {
    set({ activeTransportId: transportId, activeVehicleKey: vehicleKey });
  },

  setFormation: (leaderKey, memberKeys) => {
    const members = new Set(memberKeys);
    const next: Record<string, string[]> = {};
    // A vehicle flies in one formation: strip the new members from every other
    // group; a group whose leader was stolen (or that shrinks below 2) dissolves.
    for (const [lead, keys] of Object.entries(get().formations)) {
      if (lead === leaderKey || members.has(lead)) continue;
      const kept = keys.filter((k) => !members.has(k));
      if (kept.length >= 2) next[lead] = kept;
    }
    next[leaderKey] = memberKeys;
    set({ formations: next });
  },

  removeFormation: (leaderKey) => {
    const next = { ...get().formations };
    delete next[leaderKey];
    set({ formations: next });
  },

  clearFormations: () => set({ formations: {} }),

  toggleSelected: (vehicleKey) => {
    const current = get().selectedVehicleKeys;
    set({
      selectedVehicleKeys: current.includes(vehicleKey)
        ? current.filter((k) => k !== vehicleKey)
        : [...current, vehicleKey],
    });
  },

  setSelected: (vehicleKeys) => set({ selectedVehicleKeys: vehicleKeys }),

  recordDiscovered: (vehicle) => {
    const next = { ...get().knownVehicles, [vehicle.key]: vehicle };
    const shouldPromote = get().activeVehicleKey === null;
    set({
      knownVehicles: next,
      ...(shouldPromote
        ? { activeVehicleKey: vehicle.key, activeTransportId: vehicle.transportId }
        : {}),
    });
  },

  recordLost: (vehicleKey) => {
    const next = { ...get().knownVehicles };
    delete next[vehicleKey];
    const wasActive = get().activeVehicleKey === vehicleKey;
    // Drop the lost vehicle from its formation; a formation whose leader is lost
    // (or that shrinks below leader+1) dissolves.
    const formations: Record<string, string[]> = {};
    for (const [lead, keys] of Object.entries(get().formations)) {
      if (lead === vehicleKey) continue;
      const kept = keys.filter((k) => k !== vehicleKey);
      if (kept.length >= 2) formations[lead] = kept;
    }
    set({
      knownVehicles: next,
      selectedVehicleKeys: get().selectedVehicleKeys.filter((k) => k !== vehicleKey),
      formations,
      ...(wasActive ? { activeVehicleKey: null, activeTransportId: null } : {}),
    });
  },

  hydrate: (vehicles) => {
    const map: Record<string, VehicleInfoIpc> = {};
    for (const v of vehicles) {
      map[v.key] = v;
    }
    const patch: Partial<ActiveVehicleState> = { knownVehicles: map };
    // Adopt the active selection the roster reports (set by the main process), so
    // a window that opens *after* the selection was made — e.g. a popped-out
    // panel — still knows the active vehicle. The change broadcast only covers
    // future changes, never the current state. Fall back to the sole vehicle in
    // single-vehicle mode so it works even before any explicit selection.
    if (get().activeVehicleKey === null) {
      const active = vehicles.find((v) => v.isActive) ?? (vehicles.length === 1 ? vehicles[0] : undefined);
      if (active) {
        patch.activeVehicleKey = active.key;
        patch.activeTransportId = active.transportId;
      }
    }
    set(patch);
  },

  clearAll: () => {
    set({ activeVehicleKey: null, activeTransportId: null, knownVehicles: {}, selectedVehicleKeys: [], formations: {} });
  },
}));

/** The formation a vehicle belongs to (as leader or wingman), or null. */
export function formationOf(
  formations: Record<string, string[]>,
  vehicleKey: string,
): { leaderKey: string; memberKeys: string[] } | null {
  for (const [leaderKey, memberKeys] of Object.entries(formations)) {
    if (memberKeys.includes(vehicleKey)) return { leaderKey, memberKeys };
  }
  return null;
}
