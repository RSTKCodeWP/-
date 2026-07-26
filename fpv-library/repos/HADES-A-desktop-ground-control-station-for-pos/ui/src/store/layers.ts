import { create } from "zustand";

/* Operator map-layer toggles (impl-plan Task 5.5d). Show/hide the non-pin layers so the
 * operator declutters under load (the configurability that earns its keep on an ops map —
 * research brief §3). Pins are never toggleable (a survivor must never be hidden); only the
 * context layers are. All visible by default. */

export type LayerKey = "coverage" | "track" | "footprint" | "uncertainty";

interface LayerState {
  visible: Record<LayerKey, boolean>;
  toggle: (key: LayerKey) => void;
  reset: () => void;
}

const ALL_VISIBLE: Record<LayerKey, boolean> = {
  coverage: true,
  track: true,
  footprint: true,
  uncertainty: true,
};

export const useLayerStore = create<LayerState>((set, get) => ({
  visible: { ...ALL_VISIBLE },
  toggle: (key) => set({ visible: { ...get().visible, [key]: !get().visible[key] } }),
  reset: () => set({ visible: { ...ALL_VISIBLE } }),
}));
