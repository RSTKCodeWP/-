/**
 * @module connection-presets
 * @description Connection presets — IndexedDB-backed saved connection configs.
 * On first load, migrates any existing localStorage data to IndexedDB.
 * @license GPL-3.0-only
 */

import { get, set } from "idb-keyval";

export interface ConnectionPreset {
  id: string;
  name: string;
  type: "serial" | "websocket" | "udp-proxy" | "tcp";
  config: {
    baudRate?: number;
    url?: string;
    // UDP/TCP direct-link fields
    proto?: "udp" | "tcp";
    host?: string;
    port?: number;
    mode?: "listen" | "target";
    bridgeUrl?: string;
  };
  createdAt: number;
}

const STORAGE_KEY = "command:connection-presets";

// One-time migration
async function migratePresetsFromLocalStorage(): Promise<void> {
  if (typeof window === "undefined") return;
  const migrated = await get("command:presets-migrated");
  if (migrated) return;
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) {
      await set(STORAGE_KEY, JSON.parse(raw));
      localStorage.removeItem(STORAGE_KEY);
    }
    await set("command:presets-migrated", true);
  } catch {
    // silent
  }
}

if (typeof window !== "undefined") {
  migratePresetsFromLocalStorage();
}

export async function getPresets(): Promise<ConnectionPreset[]> {
  try {
    return (await get<ConnectionPreset[]>(STORAGE_KEY)) ?? [];
  } catch {
    return [];
  }
}

export async function savePreset(preset: ConnectionPreset): Promise<void> {
  const presets = await getPresets();
  const idx = presets.findIndex((p) => p.id === preset.id);
  if (idx >= 0) {
    presets[idx] = preset;
  } else {
    presets.push(preset);
  }
  await set(STORAGE_KEY, presets);
}

export async function deletePreset(id: string): Promise<void> {
  const presets = await getPresets();
  await set(STORAGE_KEY, presets.filter((p) => p.id !== id));
}
