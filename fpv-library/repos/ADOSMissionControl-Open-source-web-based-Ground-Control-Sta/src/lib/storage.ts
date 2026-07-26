/**
 * @module storage
 * @description Shared IndexedDB storage engine for Zustand persist middleware.
 * Uses idb-keyval (~600 bytes) for simple key-value storage in IndexedDB.
 * All Command GCS persistent data flows through this module.
 * @license GPL-3.0-only
 */

import { get, set, del } from "idb-keyval";
import type { StateStorage } from "zustand/middleware";

const idbStorage: StateStorage = {
  getItem: async (name: string): Promise<string | null> => {
    return (await get(name)) ?? null;
  },
  setItem: async (name: string, value: string): Promise<void> => {
    await set(name, value);
  },
  removeItem: async (name: string): Promise<void> => {
    await del(name);
  },
};

export const indexedDBStorage = { storage: () => idbStorage };
