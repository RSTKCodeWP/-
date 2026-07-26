/**
 * Ephemeral per-user UI preferences that are not part of the settings store:
 * the last node-detail tab visited per node, so re-opening a node returns you
 * to where you left off (first open falls back to the per-profile default).
 * Keyed by the stable node deviceId. Local-first, per browser.
 *
 * @module ui-prefs-store
 * @license GPL-3.0-only
 */

import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";

interface UiPrefsState {
  /** Last node-detail tab id, keyed by node deviceId. */
  lastTabByNode: Record<string, string>;
  setLastTab: (deviceId: string, tabId: string) => void;
  getLastTab: (deviceId: string) => string | undefined;
  /** Last Agent-page sub-page id, keyed by node deviceId, so re-opening the
   * Agent tab returns to where you left off (independent of the top-level tab). */
  lastAgentPanelByNode: Record<string, string>;
  setLastAgentPanel: (deviceId: string, panelId: string) => void;
  getLastAgentPanel: (deviceId: string) => string | undefined;
}

export const useUiPrefsStore = create<UiPrefsState>()(
  persist(
    (set, get) => ({
      lastTabByNode: {},
      setLastTab: (deviceId, tabId) =>
        set((s) => ({
          lastTabByNode: { ...s.lastTabByNode, [deviceId]: tabId },
        })),
      getLastTab: (deviceId) => get().lastTabByNode[deviceId],
      lastAgentPanelByNode: {},
      setLastAgentPanel: (deviceId, panelId) =>
        set((s) => ({
          lastAgentPanelByNode: {
            ...s.lastAgentPanelByNode,
            [deviceId]: panelId,
          },
        })),
      getLastAgentPanel: (deviceId) => get().lastAgentPanelByNode[deviceId],
    }),
    {
      name: "altcmd:ui-prefs",
      storage: createJSONStorage(() =>
        typeof window !== "undefined"
          ? window.localStorage
          : {
              getItem: () => null,
              setItem: () => {},
              removeItem: () => {},
            },
      ),
      version: 1,
    },
  ),
);
