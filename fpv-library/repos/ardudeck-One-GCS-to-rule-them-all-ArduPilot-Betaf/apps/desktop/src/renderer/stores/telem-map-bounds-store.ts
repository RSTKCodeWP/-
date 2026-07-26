/**
 * Last-known telemetry map viewport bounds, published by MapPanel so the (now
 * free-floating) fleet minimap can draw the viewport rectangle even though it no longer
 * lives inside the map panel.
 */

import { create } from 'zustand';

export interface MapBounds { north: number; south: number; east: number; west: number }

interface State {
  bounds: MapBounds | null;
  setBounds: (b: MapBounds | null) => void;
}

export const useTelemMapBoundsStore = create<State>((set) => ({
  bounds: null,
  setBounds: (bounds) => set({ bounds }),
}));
