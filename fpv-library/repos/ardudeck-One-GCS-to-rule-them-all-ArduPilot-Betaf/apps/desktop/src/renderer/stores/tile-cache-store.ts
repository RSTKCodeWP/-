import { create } from 'zustand';
import type { TileCacheDownloadRegion } from '../../shared/ipc-channels';

const api = (window as any).electronAPI;

interface TileCacheState {
  regions: TileCacheDownloadRegion[];
  fetchRegions: () => Promise<void>;
  addRegion: (region: TileCacheDownloadRegion) => void;
  deleteRegion: (id: string) => Promise<void>;
  clearRegions: () => void;
}

export const useTileCacheStore = create<TileCacheState>((set, get) => ({
  regions: [],

  fetchRegions: async () => {
    try {
      const regions = await api.tileCacheGetRegions();
      set({ regions });
    } catch { /* ignore */ }
  },

  addRegion: (region) => {
    const existing = get().regions;
    if (existing.some(r => r.id === region.id)) return;
    set({ regions: [...existing, region] });
  },

  deleteRegion: async (id) => {
    await api.tileCacheDeleteRegion(id).catch(() => {});
    set({ regions: get().regions.filter(r => r.id !== id) });
  },

  clearRegions: () => set({ regions: [] }),
}));
