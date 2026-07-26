/**
 * How the telemetry map draws per-vehicle mission waypoints in a fleet.
 *
 *  - 'all'      : every group is drawn, colour-coded by its assigned vehicle.
 *                 Groups belonging to the active vehicle (and unassigned groups)
 *                 render solid; the rest render dimmed so the operator keeps the
 *                 whole picture while the selected vehicle's route stands out.
 *  - 'selected' : only the active vehicle's groups (plus unassigned groups) draw.
 *
 * Persisted so the operator's preference survives restarts.
 */

import { create } from 'zustand';

export type TelemWpViewMode = 'all' | 'selected';

const STORAGE_KEY = 'ardudeck.telemWpViewMode';

function load(): TelemWpViewMode {
  try {
    return localStorage.getItem(STORAGE_KEY) === 'selected' ? 'selected' : 'all';
  } catch {
    return 'all';
  }
}

interface TelemMissionViewStore {
  mode: TelemWpViewMode;
  setMode: (mode: TelemWpViewMode) => void;
}

export const useTelemMissionViewStore = create<TelemMissionViewStore>((set) => ({
  mode: load(),
  setMode: (mode) => {
    try {
      localStorage.setItem(STORAGE_KEY, mode);
    } catch {
      /* storage unavailable */
    }
    set({ mode });
  },
}));
