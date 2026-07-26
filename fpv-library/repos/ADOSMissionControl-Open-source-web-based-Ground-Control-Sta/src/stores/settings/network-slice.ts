/**
 * Network slice for the persisted settings store. Owns connection-time
 * preferences: auto-reconnect on transport drop, auto-connect to last
 * device on page load, GCS-side location-sharing toggle.
 *
 * @license GPL-3.0-only
 */

import type { SettingsSliceFactory, SettingsStoreState } from "./types";

export const networkDefaults: Partial<SettingsStoreState> = {
  autoReconnect: true,
  autoConnectOnLoad: true,
  locationEnabled: false,
};

export const createNetworkActions: SettingsSliceFactory<
  Pick<
    SettingsStoreState,
    "setAutoReconnect" | "setAutoConnectOnLoad" | "setLocationEnabled"
  >
> = (set) => ({
  setAutoReconnect: (autoReconnect) => set({ autoReconnect }),
  setAutoConnectOnLoad: (autoConnectOnLoad) => set({ autoConnectOnLoad }),
  setLocationEnabled: (locationEnabled) => set({ locationEnabled }),
});
