/**
 * Position of the free-floating Fleet Ops panel on the telemetry screen (viewport
 * pixel coords). Same shape/behaviour as sim-flight-control-panel-store: `setPos`
 * updates in memory per drag frame, `persist` writes to localStorage once on drop.
 * Null until first placed; the panel then seeds to the lower-left.
 */

import { create } from 'zustand';

const KEY = 'ardudeck.fleetActionsPanelPos';

function load(): { x: number | null; y: number | null; collapsed: boolean } {
  try {
    const raw = localStorage.getItem(KEY);
    if (raw) {
      const p = JSON.parse(raw);
      const collapsed = typeof p.collapsed === 'boolean' ? p.collapsed : false;
      if (typeof p.x === 'number' && typeof p.y === 'number') return { x: p.x, y: p.y, collapsed };
      return { x: null, y: null, collapsed };
    }
  } catch {
    /* ignore */
  }
  return { x: null, y: null, collapsed: false };
}

interface State {
  x: number | null;
  y: number | null;
  collapsed: boolean;
  setPos: (x: number, y: number) => void;
  persist: () => void;
  toggleCollapsed: () => void;
}

export const useFleetActionsPanelStore = create<State>((set, get) => ({
  ...load(),
  setPos: (x, y) => set({ x, y }),
  persist: () => {
    const { x, y, collapsed } = get();
    try {
      localStorage.setItem(KEY, JSON.stringify({ x, y, collapsed }));
    } catch {
      /* ignore */
    }
  },
  toggleCollapsed: () => {
    set({ collapsed: !get().collapsed });
    get().persist();
  },
}));
