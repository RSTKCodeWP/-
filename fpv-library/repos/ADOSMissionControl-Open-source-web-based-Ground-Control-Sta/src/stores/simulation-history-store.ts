/**
 * @module simulation-history-store
 * @description Persisted store for simulation run history. Max 20 entries.
 * @license GPL-3.0-only
 */

import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";
import type { SimHistoryEntry } from "@/lib/types";
import { indexedDBStorage } from "@/lib/storage";

const MAX_HISTORY = 20;

interface SimHistoryState {
  entries: SimHistoryEntry[];
  addEntry: (entry: Omit<SimHistoryEntry, "id">) => void;
  clearHistory: () => void;
}

export const useSimHistoryStore = create<SimHistoryState>()(
  persist(
    (set) => ({
      entries: [],

      addEntry: (entry) => {
        const id = Math.random().toString(36).substring(2, 10);
        set((s) => ({
          entries: [{ ...entry, id }, ...s.entries].slice(0, MAX_HISTORY),
        }));
      },

      clearHistory: () => set({ entries: [] }),
    }),
    {
      name: "altcmd:sim-history",
      storage: createJSONStorage(indexedDBStorage.storage),
      version: 1,
      migrate: (persisted, _version) => {
        // Bump `version` and branch on `_version` here when the SimHistoryState
        // shape changes. Returning the persisted blob unchanged is correct as
        // long as the schema is stable.
        return persisted as SimHistoryState;
      },
    }
  )
);
