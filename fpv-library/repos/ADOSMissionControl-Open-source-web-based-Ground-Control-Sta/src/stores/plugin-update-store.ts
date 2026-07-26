/**
 * @module plugin-update-store
 * @description Volatile Zustand store for plugin update events surfaced
 * by the agent's auto-update loop. The agent publishes a
 * `plugin/update_available` MQTT event each time its registry sweep
 * finds a newer version that the loop will not auto-apply (major
 * version bump, new permission, board mismatch, or version pin). The
 * GCS subscribes via `MqttBridge.tsx` and dispatches events into this
 * store. The Plugins tab reads the store to render a small "Update
 * available" badge next to each affected plugin row; clicking the
 * badge opens the per-plugin update settings drawer.
 *
 * Events are de-duped on `(deviceId, pluginId)` so a repeat sweep does
 * not stack duplicate badges. State is not persisted: each session
 * starts empty and refills from incoming MQTT messages.
 *
 * @license GPL-3.0-only
 */

import { create } from "zustand";

export type PluginUpdateReason =
  | "major_bump"
  | "permission_delta"
  | "board_mismatch"
  | "pinned";

export interface PluginUpdateEvent {
  /** Cloud device id of the drone reporting the update. */
  deviceId: string;
  /** Plugin identifier the update applies to. */
  pluginId: string;
  /** Version currently installed on the agent. */
  currentVersion: string;
  /** Latest version published in the registry. */
  latestVersion: string;
  /** Why the auto-update loop did not apply the new version. */
  reason: PluginUpdateReason;
  /** Permissions added in the new version, if any. */
  newPermissions?: string[];
  /** Epoch milliseconds the agent emitted the event. */
  timestamp: number;
}

interface PluginUpdateState {
  pendingUpdates: PluginUpdateEvent[];
  addUpdate: (event: PluginUpdateEvent) => void;
  clearUpdate: (deviceId: string, pluginId: string) => void;
  clearForDevice: (deviceId: string) => void;
  getUpdatesForDevice: (deviceId: string) => PluginUpdateEvent[];
}

export const usePluginUpdateStore = create<PluginUpdateState>((set, get) => ({
  pendingUpdates: [],

  // Dedupe by (deviceId, pluginId): a fresh event replaces any prior
  // entry for the same plugin on the same drone so the badge always
  // reflects the latest registry sweep.
  addUpdate: (event) => {
    set((state) => {
      const filtered = state.pendingUpdates.filter(
        (e) =>
          !(e.deviceId === event.deviceId && e.pluginId === event.pluginId),
      );
      return { pendingUpdates: [...filtered, event] };
    });
  },

  clearUpdate: (deviceId, pluginId) => {
    set((state) => ({
      pendingUpdates: state.pendingUpdates.filter(
        (e) => !(e.deviceId === deviceId && e.pluginId === pluginId),
      ),
    }));
  },

  clearForDevice: (deviceId) => {
    set((state) => ({
      pendingUpdates: state.pendingUpdates.filter(
        (e) => e.deviceId !== deviceId,
      ),
    }));
  },

  getUpdatesForDevice: (deviceId) =>
    get().pendingUpdates.filter((e) => e.deviceId === deviceId),
}));
