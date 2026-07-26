/**
 * @module AgentPluginInventoryStore
 * @description Zustand store that mirrors the agent's webapp plugin
 * inventory per device. The agent publishes the inventory in its
 * cloud heartbeat (`cmd_droneStatus.pluginInventory`) so the GCS can
 * surface installs the operator made directly from the agent's
 * webapp at port 8080 (which bypasses the Convex install path the
 * GCS Plugins tab uses).
 *
 * Convex's `cmdPlugins:listForDevice` remains the authority for
 * installs the GCS knows about. This store is purely additive: the
 * per-drone Plugins tab merges its entries with any inventory rows
 * that share a `pluginId` with a Convex row, and renders inventory-
 * only entries (those without a Convex match) with a "from agent"
 * marker so the operator can still see they exist.
 *
 * Keyed by `deviceId` so multi-drone sessions keep each drone's
 * inventory independent. CloudStatusBridge writes when a heartbeat
 * lands; consumers read by id.
 *
 * @license GPL-3.0-only
 */

import { create } from "zustand";

/**
 * Per-model delivery outcome the agent reports for a plugin's declared
 * vision model references (one entry per model id). Mirrors the agent's
 * `ModelResolution.to_dict()`: the framework resolved the board-appropriate
 * variant from cache/registry (`resolved`, with a `path`), or it could not
 * (`needs_model` — sideload or fix the source) / a fetched file failed its
 * pinned-digest check (`verify_failed`). `reason` carries the human detail.
 */
export interface PluginModelStatusEntry {
  state: "resolved" | "needs_model" | "verify_failed" | string;
  model_id: string;
  runtime?: string | null;
  path?: string | null;
  reason?: string | null;
}

/**
 * Readiness of a service a plugin declares (one entry per service). `ready`
 * reflects the agent's probe (unit active / an HTTP 2xx / a command exit 0);
 * `reason` carries the human detail when not ready ("unit not active",
 * "http status 503", and similar).
 */
export interface PluginServiceStatusEntry {
  name: string;
  ready: boolean;
  reason?: string | null;
}

export interface AgentPluginInventoryEntry {
  plugin_id: string;
  version: string | null;
  status: string | null;
  /** Model-delivery outcome, present only when the plugin declares models. */
  model_status?: PluginModelStatusEntry[] | null;
  /** Per-service readiness, present only when the plugin declares services. */
  service_status?: PluginServiceStatusEntry[] | null;
}

interface AgentPluginInventoryState {
  byDevice: Record<string, AgentPluginInventoryEntry[]>;
}

interface AgentPluginInventoryActions {
  setForDevice: (
    deviceId: string,
    entries: AgentPluginInventoryEntry[],
  ) => void;
  clearDevice: (deviceId: string) => void;
  clear: () => void;
}

export type AgentPluginInventoryStore = AgentPluginInventoryState &
  AgentPluginInventoryActions;

export const useAgentPluginInventoryStore = create<AgentPluginInventoryStore>(
  (set) => ({
    byDevice: {},

    setForDevice(deviceId, entries) {
      if (!deviceId) return;
      set((state) => ({
        byDevice: { ...state.byDevice, [deviceId]: entries },
      }));
    },

    clearDevice(deviceId) {
      set((state) => {
        if (!(deviceId in state.byDevice)) return state;
        const next = { ...state.byDevice };
        delete next[deviceId];
        return { byDevice: next };
      });
    },

    clear() {
      set({ byDevice: {} });
    },
  }),
);
