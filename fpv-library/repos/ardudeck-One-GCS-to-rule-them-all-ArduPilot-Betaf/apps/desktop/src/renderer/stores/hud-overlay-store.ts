/**
 * Tracks whether the first-party fighter HUD overlay is currently drawn, so the
 * module host API (host.hud) can tell a `cameraOverlay` module when a
 * HUD-aligned reticle should render vs. draw nothing. Set by CameraOverlays as
 * the primary HUD mounts / unmounts.
 */

import { create } from 'zustand';

interface HudOverlayStore {
  /** True while the primary fighter HUD overlay is on screen. */
  active: boolean;
  setActive: (active: boolean) => void;
}

export const useHudOverlayStore = create<HudOverlayStore>((set) => ({
  active: false,
  setActive: (active) => set((s) => (s.active === active ? s : { active })),
}));
