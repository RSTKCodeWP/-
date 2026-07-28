/**
 * Per-view fleet collapse state so the fleet surfaces (strip, sim-world pills, Fleet
 * Ops rows) scale to many fleets: each fleet is one line by default once there are
 * more than a handful, and the operator expands the ones they care about. This is a
 * view preference, not shared across windows.
 */

import { create } from 'zustand';

/** Above this many fleets, collapse everything by default (operator expands on demand). */
export const AUTO_COLLAPSE_ABOVE = 5;

interface FleetUiState {
  /** Explicit per-fleet expand choices (leaderKey -> expanded). Absent = smart default. */
  overrides: Record<string, boolean>;
  toggle: (leaderKey: string, expandedNow: boolean) => void;
  setAll: (leaderKeys: string[], expanded: boolean) => void;
}

export const useFleetUiStore = create<FleetUiState>((set, get) => ({
  overrides: {},
  toggle: (leaderKey, expandedNow) =>
    set({ overrides: { ...get().overrides, [leaderKey]: !expandedNow } }),
  setAll: (leaderKeys, expanded) => {
    const next = { ...get().overrides };
    for (const k of leaderKeys) next[k] = expanded;
    set({ overrides: next });
  },
}));

/** Whether a fleet is expanded: an explicit choice wins, else auto-collapse when many. */
export function isFleetExpanded(overrides: Record<string, boolean>, leaderKey: string, fleetCount: number): boolean {
  return overrides[leaderKey] ?? fleetCount <= AUTO_COLLAPSE_ABOVE;
}
