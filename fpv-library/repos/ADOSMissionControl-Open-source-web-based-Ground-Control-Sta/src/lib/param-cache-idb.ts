/**
 * @module param-cache-idb
 * @description IndexedDB-backed parameter cache for offline access.
 * Persists panel params so they can be viewed when disconnected.
 * @license GPL-3.0-only
 */

import { get, set, del, keys } from "idb-keyval";

const IDB_PREFIX = "param-cache:";

export interface CachedPanelData {
  panelId: string;
  params: Record<string, number>;
  timestamp: number;
}

function key(panelId: string): string {
  return IDB_PREFIX + panelId;
}

/** Save panel params to IndexedDB. */
export async function cachePanelToIDB(
  panelId: string,
  params: Map<string, number>,
): Promise<void> {
  const data: CachedPanelData = {
    panelId,
    params: Object.fromEntries(params),
    timestamp: Date.now(),
  };
  await set(key(panelId), data);
}

/** Load cached panel params from IndexedDB. Returns null if not cached. */
export async function getCachedPanelFromIDB(
  panelId: string,
): Promise<CachedPanelData | null> {
  const data = await get<CachedPanelData>(key(panelId));
  return data ?? null;
}

/** Remove a cached panel from IndexedDB. */
export async function removeCachedPanelFromIDB(
  panelId: string,
): Promise<void> {
  await del(key(panelId));
}

/** List all cached panel IDs. */
export async function listCachedPanelIds(): Promise<string[]> {
  const allKeys = await keys();
  return (allKeys as string[])
    .filter((k) => k.startsWith(IDB_PREFIX))
    .map((k) => k.slice(IDB_PREFIX.length));
}
