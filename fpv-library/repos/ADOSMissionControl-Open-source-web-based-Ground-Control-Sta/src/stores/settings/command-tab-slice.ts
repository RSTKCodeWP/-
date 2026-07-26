/**
 * Command-tab slice for the persisted settings store. Owns Command-tab
 * preferences: last-active FC configure panel id and per-panel scroll
 * positions for the in-tab navigation.
 *
 * @license GPL-3.0-only
 */

import type { SettingsSliceFactory, SettingsStoreState } from "./types";

export const commandTabDefaults: Partial<SettingsStoreState> = {
  lastActivePanel: "outputs",
  panelScrollPositions: {},
};

export const createCommandTabActions: SettingsSliceFactory<
  Pick<SettingsStoreState, "setLastActivePanel" | "setPanelScrollPosition">
> = (set) => ({
  setLastActivePanel: (lastActivePanel) => set({ lastActivePanel }),
  setPanelScrollPosition: (panelId, scrollTop) =>
    set((s) => ({
      panelScrollPositions: {
        ...s.panelScrollPositions,
        [panelId]: scrollTop,
      },
    })),
});
