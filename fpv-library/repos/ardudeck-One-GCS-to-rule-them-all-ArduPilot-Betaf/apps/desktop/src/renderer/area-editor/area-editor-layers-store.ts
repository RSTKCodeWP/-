/**
 * area-editor-layers-store — base map layer + data overlay state for the Area
 * Editor's MapLibre surface. Kept separate from the geometry store so the
 * heavily-tested polygon model stays focused; this is purely view state.
 *
 * Mirrors the main app's map layer system (see shared/map-layers.ts and the
 * overlay set in components/map/overlays): the same base layers, plus the
 * raster/WMS overlays a pilot expects (Aviation = OpenAIP, Zones = DIPUL).
 */

import { create } from 'zustand';
import { subscribeWithSelector } from 'zustand/middleware';
import type { LayerKey } from '../../shared/map-layers';

/** Base layers offered in the editor — the planning-relevant subset of MAP_LAYERS. */
export const AREA_EDITOR_BASE_LAYERS: { key: LayerKey; label: string }[] = [
  { key: 'googleSat', label: 'Satellite' },
  { key: 'googleHybrid', label: 'Hybrid' },
  { key: 'osm', label: 'Street' },
  { key: 'terrain', label: 'Terrain' },
  { key: 'dark', label: 'Dark' },
];

export type AreaEditorOverlayId = 'aviation' | 'zones' | 'wind' | 'traffic' | 'gliders';

export const AREA_EDITOR_OVERLAYS: { id: AreaEditorOverlayId; label: string; hint: string }[] = [
  { id: 'aviation', label: 'Aviation', hint: 'OpenAIP airfields, navaids and airspace (needs an OpenAIP key)' },
  { id: 'zones', label: 'Zones', hint: 'DIPUL German UAS geo-zones (Germany only)' },
  { id: 'wind', label: 'Wind', hint: 'Animated forecast wind (Open-Meteo)' },
  { id: 'traffic', label: 'Traffic', hint: 'Live ADS-B aircraft' },
  { id: 'gliders', label: 'Gliders', hint: 'Live OGN/FLARM gliders' },
];

interface LayersState {
  baseLayer: LayerKey;
  overlays: Record<AreaEditorOverlayId, boolean>;
  setBaseLayer: (key: LayerKey) => void;
  toggleOverlay: (id: AreaEditorOverlayId) => void;
}

export const useAreaEditorLayersStore = create<LayersState>()(
  subscribeWithSelector((set) => ({
    baseLayer: 'googleSat',
    overlays: { aviation: false, zones: false, wind: false, traffic: false, gliders: false },
    setBaseLayer: (key) => set({ baseLayer: key }),
    toggleOverlay: (id) =>
      set((s) => ({ overlays: { ...s.overlays, [id]: !s.overlays[id] } })),
  })),
);
