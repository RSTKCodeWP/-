import { create } from "zustand";

interface FcPanelActionsState {
  saveToRam: (() => Promise<void>) | null;
  refresh: (() => Promise<void>) | null;
  register: (saveToRam: () => Promise<void>, refresh: () => Promise<void>) => void;
  unregister: () => void;
}

export const useFcPanelActionsStore = create<FcPanelActionsState>((set) => ({
  saveToRam: null,
  refresh: null,
  register: (saveToRam, refresh) => set({ saveToRam, refresh }),
  unregister: () => set({ saveToRam: null, refresh: null }),
}));
