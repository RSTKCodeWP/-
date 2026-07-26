/**
 * "Cache map area" mode for the telemetry map. When active, the map shows an adjustable
 * rectangle (OfflineCacheBox) and a control panel (OfflineCachePanel); the operator sizes
 * the box over the area to keep, picks a detail level, and downloads its tiles. Replaces
 * the old "cache whatever's in view" flow.
 */

import { create } from 'zustand';

export interface CacheBounds { north: number; south: number; east: number; west: number }

interface State {
  active: boolean;
  bounds: CacheBounds | null;
  setActive: (active: boolean) => void;
  setBounds: (bounds: CacheBounds | null) => void;
}

export const useTileCacheAreaStore = create<State>((set) => ({
  active: false,
  bounds: null,
  // Opening starts with a fresh box (re-fit to the current view); closing leaves the box.
  setActive: (active) => set(active ? { active: true, bounds: null } : { active: false }),
  setBounds: (bounds) => set({ bounds }),
}));
