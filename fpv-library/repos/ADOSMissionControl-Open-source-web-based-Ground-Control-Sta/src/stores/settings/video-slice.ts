/**
 * Video slice for the persisted settings store. Owns video-transport
 * preferences: WHEP endpoint URL, transport mode (auto / lan-whep /
 * p2p-mqtt / off), and the HDMI kiosk auto-claim-PIC-on-first-button
 * toggle.
 *
 * @license GPL-3.0-only
 */

import type { SettingsSliceFactory, SettingsStoreState } from "./types";

export const videoDefaults: Partial<SettingsStoreState> = {
  videoWhepUrl: "",
  videoTransportMode: "auto",
  hudAutoClaimPicOnFirstButton: false,
};

export const createVideoActions: SettingsSliceFactory<
  Pick<
    SettingsStoreState,
    | "setVideoWhepUrl"
    | "setVideoTransportMode"
    | "setHudAutoClaimPicOnFirstButton"
  >
> = (set) => ({
  setVideoWhepUrl: (videoWhepUrl) => set({ videoWhepUrl }),
  setVideoTransportMode: (videoTransportMode) => set({ videoTransportMode }),
  setHudAutoClaimPicOnFirstButton: (hudAutoClaimPicOnFirstButton) =>
    set({ hudAutoClaimPicOnFirstButton }),
});
