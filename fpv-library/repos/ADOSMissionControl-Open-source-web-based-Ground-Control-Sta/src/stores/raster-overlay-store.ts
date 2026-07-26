/**
 * @module raster-overlay-store
 * @description Session-only store for a single georeferenced raster (orthophoto)
 * overlay on the planner map. The rasterized PNG is a large in-memory object, so
 * this store is deliberately NOT persisted — it resets on reload. Holds the
 * loaded raster (bounds + data URL), a visibility flag, a load-in-progress flag,
 * and an error code (`"unreadable"` when a file could not be placed).
 * @license GPL-3.0-only
 */

import { create } from "zustand";

import { loadGeoTIFF, type RasterBounds } from "@/lib/formats/geotiff-loader";

export interface RasterOverlay {
  bounds: RasterBounds;
  dataUrl: string;
  name?: string;
}

/** Error codes surfaced to the UI (mapped to translated hints by the control). */
export type RasterError = "unreadable";

interface RasterOverlayState {
  raster: RasterOverlay | null;
  visible: boolean;
  loading: boolean;
  error: RasterError | null;
  loadFromFile: (file: File) => Promise<void>;
  toggleVisible: () => void;
  clear: () => void;
}

export const useRasterOverlayStore = create<RasterOverlayState>((set) => ({
  raster: null,
  visible: true,
  loading: false,
  error: null,

  loadFromFile: async (file) => {
    set({ loading: true, error: null });
    try {
      const buffer = await file.arrayBuffer();
      const result = await loadGeoTIFF(buffer);
      if (!result) {
        set({ loading: false, error: "unreadable" });
        return;
      }
      set({
        raster: {
          bounds: result.bounds,
          dataUrl: result.dataUrl,
          name: result.name ?? file.name,
        },
        visible: true,
        loading: false,
        error: null,
      });
    } catch {
      set({ loading: false, error: "unreadable" });
    }
  },

  toggleVisible: () => set((s) => ({ visible: !s.visible })),

  clear: () => set({ raster: null, visible: true, loading: false, error: null }),
}));
