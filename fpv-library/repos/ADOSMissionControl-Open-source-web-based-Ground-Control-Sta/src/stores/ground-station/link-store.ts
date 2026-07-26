/**
 * Link slice for the ground-station store. Tracks WFB-ng radio link state
 * (channel + bitrate profile), link health metrics (RSSI, FEC), and the
 * high-level paired-drone status.
 *
 * Consumers can subscribe through the aggregator hook `useGroundStationStore`
 * or via the narrower selector hook `useLinkSlice`.
 *
 * @license GPL-3.0-only
 */

import type { GroundStationSliceCreator } from "./state";
import { INITIAL_LINK_HEALTH, INITIAL_STATUS } from "./initial-state";
import type {
  GroundStationLinkHealth,
  GroundStationStatus,
  WfbConfig,
} from "./types";

export interface LinkSlice {
  linkHealth: GroundStationLinkHealth;
  wfbConfig: WfbConfig | null;
  status: GroundStationStatus;
  loading: boolean;
  lastError: string | null;
  lastFetchedAt: number | null;

  loadStatus: (
    status: GroundStationStatus,
    linkHealth?: Partial<GroundStationLinkHealth>,
  ) => void;
  loadWfb: (wfb: WfbConfig) => void;
  setWfbConfig: (partial: Partial<WfbConfig>) => void;
  setLoading: (loading: boolean) => void;
  setError: (message: string | null) => void;
  reset: () => void;
}

export const createLinkSlice: GroundStationSliceCreator<LinkSlice> = (
  set,
  get,
) => ({
  linkHealth: INITIAL_LINK_HEALTH,
  wfbConfig: null,
  status: INITIAL_STATUS,
  loading: false,
  lastError: null,
  lastFetchedAt: null,

  loadStatus: (status, linkHealth) => {
    const current = get().linkHealth;
    set({
      status,
      linkHealth: linkHealth ? { ...current, ...linkHealth } : current,
      lastFetchedAt: Date.now(),
      lastError: null,
    });
  },

  loadWfb: (wfb) => {
    set({ wfbConfig: wfb, lastFetchedAt: Date.now(), lastError: null });
  },

  setWfbConfig: (partial) => {
    const current = get().wfbConfig;
    if (!current) return;
    set({ wfbConfig: { ...current, ...partial } });
  },

  setLoading: (loading) => set({ loading }),

  setError: (message) => set({ lastError: message }),

  reset: () =>
    set({
      linkHealth: INITIAL_LINK_HEALTH,
      wfbConfig: null,
      status: INITIAL_STATUS,
      loading: false,
      lastError: null,
      lastFetchedAt: null,
    }),
});

