/**
 * Formation geometry + transient UI state for the fleet's RTS-style formation controls.
 *
 * Geometry is PER FLEET, keyed by leader key. Several fleets fly at once and each one
 * keeps its own shape / spacing / alt-step: a single shared value made the glyph bars
 * of every fleet light up together (pick "column" on one fleet and all of them read
 * "column"), and worse, any later re-issue of another fleet's follow.leader - adding a
 * wingman, dropping one - silently pushed the last-touched fleet's geometry onto it.
 *
 * `defaults` is the seed for the NEXT fleet only; it is never read for a fleet that
 * already has an entry in `byFleet`. Configs are dropped when a fleet disbands, so a
 * leader key reused later starts from the defaults again.
 *
 * The glyph bar (FleetCoordination) and the right-click menu (FleetContextMenu, on
 * cards and map markers) both read/write here, so a fleet's geometry stays in sync
 * across surfaces and a busy intent disables every trigger at once. `contextMenu`
 * holds the open right-click target.
 */

import { create } from 'zustand';

export interface FleetContextMenuState {
  x: number;
  y: number;
  vehicleKey: string;
}

/** One fleet's formation geometry. */
export interface FleetFormationConfig {
  /** Formation shape (sent verbatim to the orchestrator). */
  shape: string;
  /** Metres between vehicles. */
  spacing: number;
  /** Altitude layer step (m) per rank. */
  altStep: number;
}

export const DEFAULT_FORMATION_CONFIG: FleetFormationConfig = {
  shape: 'vee',
  spacing: 15,
  altStep: 5,
};

interface FormationState {
  /** Geometry seed for the next fleet formed. Never read for an existing fleet. */
  defaults: FleetFormationConfig;
  /** Live geometry per fleet, keyed by leader key. */
  byFleet: Record<string, FleetFormationConfig>;
  /** An orchestration intent is in flight - disables every trigger. */
  busy: boolean;
  /** Open right-click menu target, or null. */
  contextMenu: FleetContextMenuState | null;
  /**
   * Patch one fleet's geometry, or the defaults when `leaderKey` is null. A fleet with
   * no entry yet inherits the defaults before the patch applies.
   */
  setConfig: (leaderKey: string | null, patch: Partial<FleetFormationConfig>) => void;
  /** Forget a disbanded fleet's geometry. */
  dropConfig: (leaderKey: string) => void;
  /** Forget every fleet's geometry (all formations broken). */
  clearConfigs: () => void;
  setBusy: (busy: boolean) => void;
  openContextMenu: (menu: FleetContextMenuState) => void;
  closeContextMenu: () => void;
}

export const useFormationStore = create<FormationState>((set, get) => ({
  defaults: DEFAULT_FORMATION_CONFIG,
  byFleet: {},
  busy: false,
  contextMenu: null,

  setConfig: (leaderKey, patch) => {
    if (leaderKey === null) {
      set({ defaults: { ...get().defaults, ...patch } });
      return;
    }
    const cur = get().byFleet[leaderKey] ?? get().defaults;
    set({ byFleet: { ...get().byFleet, [leaderKey]: { ...cur, ...patch } } });
  },

  dropConfig: (leaderKey) => {
    if (!(leaderKey in get().byFleet)) return;
    const next = { ...get().byFleet };
    delete next[leaderKey];
    set({ byFleet: next });
  },

  clearConfigs: () => set({ byFleet: {} }),

  setBusy: (busy) => set({ busy }),
  openContextMenu: (contextMenu) => set({ contextMenu }),
  closeContextMenu: () => set({ contextMenu: null }),
}));

/** A fleet's geometry, falling back to the defaults for a fleet with no entry yet. */
export function formationConfigOf(
  byFleet: Record<string, FleetFormationConfig>,
  defaults: FleetFormationConfig,
  leaderKey: string | null | undefined,
): FleetFormationConfig {
  return (leaderKey ? byFleet[leaderKey] : undefined) ?? defaults;
}
