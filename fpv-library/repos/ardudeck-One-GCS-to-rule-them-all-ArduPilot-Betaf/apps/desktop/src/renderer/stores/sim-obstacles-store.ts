/**
 * Authored simulator obstacles store.
 *
 * Holds the user-placed obstacles for the current test site (geographic coords),
 * persisted to the main process electron-store keyed by a site id derived from
 * the home/origin. Obstacles convert into ArduPilot exclusion fences elsewhere
 * (the "fence hack") so the flight controller genuinely avoids them.
 */
import { create } from 'zustand';
import type { AuthoredObstacle } from '../../shared/sim-obstacle-types';

/** Round home lat/lon to ~100 m so a field keeps one obstacle set. */
export function siteIdFromOrigin(lat: number, lon: number): string {
  return `${lat.toFixed(3)}_${lon.toFixed(3)}`;
}

/** Defaults applied to the next click-placed obstacle. */
export interface ObstacleDraft {
  shape: 'cylinder' | 'box';
  radius: number;
  height: number;
}

interface SimObstaclesStore {
  obstacles: AuthoredObstacle[];
  siteId: string | null;
  loaded: boolean;
  /** When true, a ground click in the 3D world drops a new obstacle. */
  placing: boolean;
  draft: ObstacleDraft;
  setPlacing: (placing: boolean) => void;
  setDraft: (patch: Partial<ObstacleDraft>) => void;
  loadForSite: (lat: number, lon: number) => Promise<void>;
  add: (o: Omit<AuthoredObstacle, 'id'>) => void;
  update: (id: string, patch: Partial<AuthoredObstacle>) => void;
  remove: (id: string) => void;
  clear: () => void;
}

function persist(siteId: string | null, obstacles: AuthoredObstacle[]): void {
  if (!siteId) return;
  void window.electronAPI?.saveSimObstacles?.(siteId, obstacles);
}

export const useSimObstaclesStore = create<SimObstaclesStore>((set, get) => ({
  obstacles: [],
  siteId: null,
  loaded: false,
  placing: false,
  draft: { shape: 'cylinder', radius: 10, height: 20 },

  setPlacing: (placing) => set({ placing }),
  setDraft: (patch) => set({ draft: { ...get().draft, ...patch } }),

  loadForSite: async (lat, lon) => {
    const siteId = siteIdFromOrigin(lat, lon);
    if (siteId === get().siteId && get().loaded) return;
    let obstacles: AuthoredObstacle[] = [];
    try {
      obstacles = (await window.electronAPI?.getSimObstacles?.(siteId)) ?? [];
    } catch {
      /* ignore — start empty */
    }
    set({ siteId, obstacles, loaded: true });
  },

  add: (o) => {
    const obstacle: AuthoredObstacle = { id: crypto.randomUUID(), ...o };
    const obstacles = [...get().obstacles, obstacle];
    set({ obstacles });
    persist(get().siteId, obstacles);
  },

  update: (id, patch) => {
    const obstacles = get().obstacles.map((o) => (o.id === id ? { ...o, ...patch } : o));
    set({ obstacles });
    persist(get().siteId, obstacles);
  },

  remove: (id) => {
    const obstacles = get().obstacles.filter((o) => o.id !== id);
    set({ obstacles });
    persist(get().siteId, obstacles);
  },

  clear: () => {
    set({ obstacles: [] });
    persist(get().siteId, []);
  },
}));
