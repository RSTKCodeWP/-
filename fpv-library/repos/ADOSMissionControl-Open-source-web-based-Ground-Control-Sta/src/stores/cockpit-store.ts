/**
 * Cockpit feature flag. Gates the immersive cockpit Skill Bar so the surface
 * ships inert (default off) and an operator opts in. Persisted on its own so it
 * is independent of the larger settings store and survives a reload.
 *
 * @module cockpit-store
 * @license GPL-3.0-only
 */

import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";

interface CockpitState {
  /** Whether the cockpit surfaces (Skill Bar) are enabled. */
  enabled: boolean;
  setEnabled: (enabled: boolean) => void;
  toggle: () => void;
}

/** Current localStorage key. */
const STORAGE_KEY = "altcmd:cockpit";
/** Prior localStorage key, honored once on read then migrated over. */
const LEGACY_STORAGE_KEY = "altcmd:fly-mode";

/**
 * Storage that rename-migrates the prior key on read: if nothing is stored
 * under the current key but a value exists under the old one, adopt it (and
 * clear the old key) so an operator's opt-in survives the rename.
 */
const cockpitStorage = createJSONStorage(() =>
  typeof window !== "undefined"
    ? {
        getItem: (name: string) => {
          const current = window.localStorage.getItem(name);
          if (current !== null) return current;
          const legacy = window.localStorage.getItem(LEGACY_STORAGE_KEY);
          if (legacy !== null) {
            window.localStorage.setItem(name, legacy);
            window.localStorage.removeItem(LEGACY_STORAGE_KEY);
            return legacy;
          }
          return null;
        },
        setItem: (name: string, value: string) =>
          window.localStorage.setItem(name, value),
        removeItem: (name: string) => window.localStorage.removeItem(name),
      }
    : {
        getItem: () => null,
        setItem: () => {},
        removeItem: () => {},
      },
);

export const useCockpitStore = create<CockpitState>()(
  persist(
    (set, get) => ({
      enabled: false,
      setEnabled: (enabled) => set({ enabled }),
      toggle: () => set({ enabled: !get().enabled }),
    }),
    {
      name: STORAGE_KEY,
      storage: cockpitStorage,
      version: 2,
      // Shape is unchanged across versions; the rename-on-read above carries
      // the old key's value, and this passes the persisted state through.
      migrate: (persisted) => persisted as CockpitState,
    },
  ),
);
