/**
 * @module BrowserIdentityStore
 * @description Per-browser stable UUID used as the local pair's
 * ``user_id`` when claiming an agent over LAN. The agent's
 * ``/api/pairing/claim`` accepts any string; we use a browser-local
 * UUID so the same browser keeps a consistent owner identity across
 * paired nodes without ever round-tripping through a cloud account.
 *
 * Persisted to localStorage. Generated once on first read.
 *
 * THREAT MODEL (local-first credential storage):
 *   - The UUID is the pair OWNER identifier the agent uses to scope
 *     unpair / re-pair requests. Anyone with access to this UUID can
 *     unpair the agent from this browser.
 *   - localStorage is plaintext. XSS that runs on the GCS origin
 *     reads everything. Browser-extension access also reads
 *     localStorage; devtools sees the same. This is the local-first
 *     trade-off: no cloud account means no server-side credential
 *     anchor.
 *   - If localStorage is cleared, the operator loses ownership of
 *     every locally-paired node. Recovery: unpair the agent from
 *     its own setup webapp (`http://<host>:8080/setup.html`), then
 *     re-pair from the GCS.
 *   - Future hardening (WebCrypto wrapping key + per-browser
 *     passphrase) is intentionally deferred. The pragmatic posture
 *     for now is "operator trusts their own browser session".
 *
 * @license GPL-3.0-only
 */

import { create } from "zustand";
import { persist } from "zustand/middleware";

interface BrowserIdentityState {
  browserId: string;
  /** Epoch ms when the operator dismissed the first-pair UX warning,
   * or 0 if it has never been dismissed. */
  localPairWarningDismissedAt: number;
  ensureBrowserId: () => string;
  dismissLocalPairWarning: () => void;
}

function generateBrowserId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return `browser_${crypto.randomUUID()}`;
  }
  // Fallback for older browsers — collision-resistant enough for a
  // local pair identity, never used for auth.
  const rand = () => Math.random().toString(36).slice(2, 10);
  return `browser_${rand()}${rand()}${Date.now().toString(36)}`;
}

export const useBrowserIdentityStore = create<BrowserIdentityState>()(
  persist(
    (set, get) => ({
      browserId: "",
      localPairWarningDismissedAt: 0,
      ensureBrowserId: () => {
        let id = get().browserId;
        if (!id) {
          id = generateBrowserId();
          set({ browserId: id });
        }
        return id;
      },
      dismissLocalPairWarning: () => {
        set({ localPairWarningDismissedAt: Date.now() });
      },
    }),
    {
      name: "altcmd:browser-identity",
      version: 1,
      // TODO(schema-bump): when a future version adds a required
      // field, replace this identity passthrough with an explicit
      // version branch that validates and back-fills the persisted
      // payload (see src/stores/settings-store/migrations.ts for a
      // reference chain).
      migrate: (persisted, _version) => persisted as BrowserIdentityState,
    },
  ),
);

/** Read or generate the browser-local UUID synchronously. */
export function getBrowserId(): string {
  return useBrowserIdentityStore.getState().ensureBrowserId();
}
