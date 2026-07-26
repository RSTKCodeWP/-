/**
 * @module mcp-tab-store
 * @description In-page UI state for the `/mcp` tab: the active view in the
 * grouped sidebar, rail state (expanded plugin nodes, the plugin filter, the
 * selected credential for the detail drawer), and the mint / reveal-once /
 * revoke modal state. No credential is ever persisted here; the whole store
 * resets to Overview each visit and on sign-out.
 * @license GPL-3.0-only
 */

import { create } from "zustand";

export interface RevealedCredential {
  credential: string;
  label: string;
  tokenId: string;
}

/**
 * The active view in the MCP tab's grouped sidebar. A discriminated union so a
 * view can carry its own arguments (a per-plugin page carries its `pluginId`).
 */
export type McpView =
  | { kind: "overview" }
  | { kind: "connect" }
  | { kind: "credentials" }
  | { kind: "scopes" }
  | { kind: "catalog" }
  | { kind: "plugins" }
  | { kind: "plugin"; pluginId: string }
  | { kind: "audit" };

interface McpTabState {
  /** The active sidebar view. */
  view: McpView;
  /** Expanded plugin nodes in the rail (their tool leaves are shown). */
  expandedPlugins: string[];
  /** The plugins-segment filter box text. */
  pluginFilter: string;
  /** The credential whose detail drawer is open (its `tokenId`), or null. */
  selectedCredentialId: string | null;
  generateOpen: boolean;
  /** The guided setup wizard (prerequisites → get → mint → add → verify). */
  wizardOpen: boolean;
  revealed: RevealedCredential | null;
  revokeTokenId: string | null;
  navigate: (view: McpView) => void;
  openWizard: () => void;
  closeWizard: () => void;
  togglePlugin: (pluginId: string) => void;
  setPluginFilter: (q: string) => void;
  selectCredential: (tokenId: string | null) => void;
  openGenerate: () => void;
  closeGenerate: () => void;
  reveal: (r: RevealedCredential) => void;
  clearRevealed: () => void;
  askRevoke: (tokenId: string | null) => void;
}

export const useMcpTabStore = create<McpTabState>((set) => ({
  view: { kind: "overview" },
  expandedPlugins: [],
  pluginFilter: "",
  selectedCredentialId: null,
  generateOpen: false,
  wizardOpen: false,
  revealed: null,
  revokeTokenId: null,
  navigate: (view) => set({ view }),
  openWizard: () => set({ wizardOpen: true }),
  closeWizard: () => set({ wizardOpen: false }),
  togglePlugin: (pluginId) =>
    set((s) => ({
      expandedPlugins: s.expandedPlugins.includes(pluginId)
        ? s.expandedPlugins.filter((x) => x !== pluginId)
        : [...s.expandedPlugins, pluginId],
    })),
  setPluginFilter: (pluginFilter) => set({ pluginFilter }),
  selectCredential: (selectedCredentialId) => set({ selectedCredentialId }),
  openGenerate: () => set({ generateOpen: true }),
  closeGenerate: () => set({ generateOpen: false }),
  reveal: (revealed) => set({ revealed, generateOpen: false }),
  clearRevealed: () => set({ revealed: null }),
  askRevoke: (revokeTokenId) => set({ revokeTokenId }),
}));

/** The reset applied on unmount + sign-out (drops any un-dismissed secret). */
export const MCP_TAB_RESET: Pick<
  McpTabState,
  | "view"
  | "expandedPlugins"
  | "pluginFilter"
  | "selectedCredentialId"
  | "generateOpen"
  | "wizardOpen"
  | "revealed"
  | "revokeTokenId"
> = {
  view: { kind: "overview" },
  expandedPlugins: [],
  pluginFilter: "",
  selectedCredentialId: null,
  generateOpen: false,
  wizardOpen: false,
  revealed: null,
  revokeTokenId: null,
};
