import { create } from 'zustand';

/**
 * Edit mode determines which type of data the user is editing:
 * - mission: Waypoints (blue)
 * - geofence: Fence polygons/circles (green)
 * - rally: Rally points (orange)
 */
export type EditMode = 'mission' | 'geofence' | 'rally';
export type MapMode = '2d' | '3d';

/** Shared viewport state — synced between 2D and 3D panels on every camera move */
export interface MapViewport {
  center: [number, number]; // [lng, lat]
  zoom: number;
  pitch: number;  // always 0 from 2D
  bearing: number; // always 0 from 2D
}

interface EditModeStore {
  activeMode: EditMode;
  mapMode: MapMode;
  mapViewport: MapViewport | null;
  /** Shared map layer key — synced between 2D and 3D panels */
  mapLayer: string;
  setActiveMode: (mode: EditMode) => void;
  setMapMode: (mode: MapMode) => void;
  setMapViewport: (viewport: MapViewport) => void;
  setMapLayer: (layer: string) => void;
  reset: () => void;
}

export const useEditModeStore = create<EditModeStore>((set) => ({
  activeMode: 'mission',
  mapMode: '2d',
  mapViewport: null,
  mapLayer: 'googleSat',

  setActiveMode: (mode) => {
    set({ activeMode: mode });
  },

  setMapMode: (mode) => {
    set({ mapMode: mode });
  },

  setMapViewport: (viewport) => {
    set({ mapViewport: viewport });
  },

  setMapLayer: (layer) => {
    set({ mapLayer: layer });
  },

  reset: () => {
    set({ activeMode: 'mission', mapMode: '2d', mapViewport: null, mapLayer: 'googleSat' });
  },
}));
