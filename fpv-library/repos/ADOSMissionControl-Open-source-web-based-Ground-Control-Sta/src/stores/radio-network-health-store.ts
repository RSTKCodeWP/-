/**
 * @module RadioNetworkHealthStore
 * @description Zustand store backing the Radio / Network Health panel. The
 * live link/adapter indicators come from the heartbeat-backed
 * `agent-capabilities` store (read in the component); this store owns the
 * durable event history, read from `client.logging` for the radio/network
 * event kinds. Reads degrade gracefully: an older agent (no durable
 * store) or cloud mode (LAN store not reachable) leaves the feed empty and
 * `available=false` rather than throwing, so the panel falls back to the
 * live heartbeat indicators only.
 * @license GPL-3.0-only
 */

import { create } from "zustand";
import type { EventsRow } from "@/lib/agent/agent-client/logging";
import {
  RADIO_NETWORK_EVENT_KINDS,
  mapRadioNetworkEvents,
  type RadioNetworkActivity,
} from "@/lib/agent/radio-network-events";
import { useAgentConnectionStore } from "./agent-connection-store";

/** How many activity rows to keep + render. */
const MAX_ACTIVITY = 15;
/** How many rows to pull from the store before mapping + capping. A small
 * over-fetch covers the case where the newest rows span several kinds. */
const QUERY_LIMIT = 60;
/** Look back over the last day so a freshly-opened panel shows recent
 * boot-window reg-pins + self-heals without an unbounded scan. */
const LOOKBACK = "-24h";
/** A WiFi self-heal counts as "recent" (live indicator stays warning) for
 * this window after it fired. */
const WIFI_RECENT_WINDOW_MS = 5 * 60_000;

interface RadioNetworkHealthState {
  /** Recent radio/network events, newest first, capped at MAX_ACTIVITY. */
  recentEvents: RadioNetworkActivity[];
  /** True when the most recent onboard-WiFi self-heal fired inside the
   * recent window at load time. Derived in the store (not in render) so the
   * freshness clock read stays out of the component's pure body. */
  wifiReassocRecent: boolean;
  /** True once the durable store answered at least once this session. */
  available: boolean;
  loading: boolean;
  /** Set when the last load threw for a reason other than "store absent". */
  error: string | null;
  lastFetch: number | null;
}

interface RadioNetworkHealthActions {
  /** Query the durable store for the radio/network event kinds and refresh
   * the feed. Swallows unreachable-store errors (older agent / cloud mode)
   * so the panel still renders the live heartbeat indicators. */
  loadEvents: () => Promise<void>;
  /** Alias used by the panel's mount + manual refresh. */
  refresh: () => Promise<void>;
  /** Reset on agent disconnect / panel unmount. */
  clear: () => void;
}

export type RadioNetworkHealthStore = RadioNetworkHealthState &
  RadioNetworkHealthActions;

const initialState: RadioNetworkHealthState = {
  recentEvents: [],
  wifiReassocRecent: false,
  available: false,
  loading: false,
  error: null,
  lastFetch: null,
};

export const useRadioNetworkHealthStore = create<RadioNetworkHealthStore>(
  (set, get) => ({
    ...initialState,

    async loadEvents() {
      // Resolve the logging client defensively: any failure to read the
      // connection store (or a store with no logging surface) leaves the
      // feed empty and unavailable so the panel shows live state only.
      let client: ReturnType<
        typeof useAgentConnectionStore.getState
      >["client"] = null;
      try {
        client = useAgentConnectionStore.getState().client;
      } catch {
        set({ available: false, loading: false });
        return;
      }
      // No logging surface at all (older agent build): leave the feed empty
      // and stay unavailable so the panel shows live state only.
      if (!client?.logging) {
        set({ available: false, loading: false });
        return;
      }
      set({ loading: true });
      try {
        const envelope = await client.logging.query<EventsRow>({
          kind: "events",
          event_kind: [...RADIO_NETWORK_EVENT_KINDS],
          from: LOOKBACK,
          limit: QUERY_LIMIT,
        });
        const recentEvents = mapRadioNetworkEvents(envelope.data, MAX_ACTIVITY);
        // Freshness clock read happens here (the store), not in the
        // component's pure render body.
        const now = Date.now();
        const lastWifi = recentEvents.find(
          (e) => e.kind === "network.wifi_reassociated",
        );
        const wifiReassocRecent =
          lastWifi != null && now - lastWifi.tsUs / 1000 < WIFI_RECENT_WINDOW_MS;
        set({
          recentEvents,
          wifiReassocRecent,
          available: true,
          loading: false,
          error: null,
          lastFetch: now,
        });
      } catch (err) {
        // The durable store is unreachable (cloud mode, network error, or a
        // pre-logd agent). Degrade to "no events" without crashing; the
        // panel keeps showing the live heartbeat indicators.
        set({
          available: false,
          loading: false,
          error: err instanceof Error ? err.message : null,
        });
      }
    },

    async refresh() {
      await get().loadEvents();
    },

    clear() {
      set({ ...initialState });
    },
  }),
);
