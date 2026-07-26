/**
 * Command target store — tracks the currently-active map command target
 * (orbit center, goto destination, spiral anchor, ...) per vehicle so the
 * overlay survives view transitions (2D ↔ 3D, panel remounts, layout swaps)
 * and across panels that want to render the same target.
 *
 * Multi-vehicle ready: keyed by vehicleId. Today there is only one vehicle so
 * everything writes/reads under the SELF_VEHICLE_ID constant. When swarming
 * lands, callers will pass the relevant vehicle id and per-vehicle overlays
 * appear naturally.
 *
 * Lives outside the MapPanel local state because:
 *   1. Switching 2D ↔ 3D unmounts/remounts MapPanel children → local state is
 *      lost → orbit ring vanishes mid-flight.
 *   2. The 3D map renderer needs to render the same target from a different
 *      component subtree.
 *   3. Future: a sidebar / mini-map / mission tab may want to show "vehicle 2
 *      is currently orbiting here" without coupling to the map panel.
 */
import { create } from 'zustand';
import type { ActiveCommandTarget } from '../components/map/map-command-types';

/** Stable id used until multi-vehicle support lands. */
export const SELF_VEHICLE_ID = 'self';

interface CommandTargetStore {
  /** vehicleId → currently-active target (null while idle / undefined if never set). */
  targets: Record<string, ActiveCommandTarget | null>;

  /** Set the active target for a vehicle. Pass null to clear. */
  setTarget: (vehicleId: string, target: ActiveCommandTarget | null) => void;
  /** Read a vehicle's active target (or null). */
  getTarget: (vehicleId: string) => ActiveCommandTarget | null;
  /** Clear all targets — used on disconnect. */
  clearAll: () => void;
}

export const useCommandTargetStore = create<CommandTargetStore>((set, get) => ({
  targets: {},
  setTarget: (vehicleId, target) =>
    set((state) => ({ targets: { ...state.targets, [vehicleId]: target } })),
  getTarget: (vehicleId) => get().targets[vehicleId] ?? null,
  clearAll: () => set({ targets: {} }),
}));

/** Convenience selector: subscribe to the SELF vehicle's active target. */
export const useSelfActiveTarget = () =>
  useCommandTargetStore((s) => s.targets[SELF_VEHICLE_ID] ?? null);
