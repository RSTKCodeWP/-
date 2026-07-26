/**
 * The cockpit quick-settings open state, lifted into a tiny store so any
 * cockpit surface can request the drawer without prop-drilling through the bar.
 *
 * The Skill Bar's per-slot affordance (a long-press / right-click / gamepad
 * chord on a PLUGIN skill) opens the drawer focused to that plugin via
 * `openFocused(pluginId)`; the cockpit top-bar button and the keybinding open
 * the full (unfocused) drawer via `open()`. `CockpitView` mounts the drawer when
 * `isOpen` is true and clears the state on close.
 *
 * @module stores/fly-quick-settings-store
 * @license GPL-3.0-only
 */

import { create } from "zustand";

interface FlyQuickSettingsState {
  /** Whether the quick-settings drawer is open. */
  isOpen: boolean;
  /** When set, the drawer shows only this plugin's settings. */
  focusPluginId: string | null;
  /** Open the full drawer (all parameter-bearing plugins + the model picker). */
  open: () => void;
  /** Open the drawer filtered to a single plugin (the per-skill affordance). */
  openFocused: (pluginId: string) => void;
  /** Toggle the full drawer open/closed (the keybinding + top-bar button). */
  toggle: () => void;
  /** Close the drawer and clear any focus. */
  close: () => void;
}

export const useFlyQuickSettingsStore = create<FlyQuickSettingsState>(
  (set, get) => ({
    isOpen: false,
    focusPluginId: null,
    open: () => set({ isOpen: true, focusPluginId: null }),
    openFocused: (pluginId) => set({ isOpen: true, focusPluginId: pluginId }),
    toggle: () => {
      // A toggle always lands on the full (unfocused) view; a focused open is
      // only ever explicit (the per-skill affordance), never a toggle target.
      if (get().isOpen) set({ isOpen: false, focusPluginId: null });
      else set({ isOpen: true, focusPluginId: null });
    },
    close: () => set({ isOpen: false, focusPluginId: null }),
  }),
);
