/**
 * @module lib/protocol/signing-prefs
 * @description Lightweight per-drone preferences for MAVLink signing.
 *
 * These are local-only intent flags. Cloud sync opt-in is the one we
 * care about today: the operator flips the toggle before any raw key
 * bytes exist in memory, so we need somewhere to stash "upload on the
 * next rotation" until an enroll or rotate actually produces fresh
 * bytes.
 *
 * Backed by `idb-keyval` under the `signing-prefs-v1` object store.
 * A missing record means "default". Defaults: cloud sync off.
 *
 * @license GPL-3.0-only
 */

import { createStore, get, set, del } from "idb-keyval";

const STORE_DB = "ados-signing-prefs";
const STORE_NAME = "signing-prefs-v1";

let _storePromise: ReturnType<typeof createStore> | null = null;
function prefsStore() {
  if (_storePromise === null) {
    _storePromise = createStore(STORE_DB, STORE_NAME);
  }
  return _storePromise;
}

export interface SigningDronePrefs {
  /**
   * When true, the next enroll or rotate for this drone should push the
   * fresh key to Convex cloud sync. Gated by the user being signed in
   * at the moment of upload.
   */
  cloudSyncIntent: boolean;
}

const DEFAULTS: SigningDronePrefs = {
  cloudSyncIntent: false,
};

export async function getPrefs(droneId: string): Promise<SigningDronePrefs> {
  const rec = (await get(droneId, await prefsStore())) as
    | SigningDronePrefs
    | undefined;
  if (!rec) return { ...DEFAULTS };
  return { ...DEFAULTS, ...rec };
}

export async function setCloudSyncIntent(
  droneId: string,
  cloudSyncIntent: boolean,
): Promise<void> {
  const current = await getPrefs(droneId);
  await set(
    droneId,
    { ...current, cloudSyncIntent },
    await prefsStore(),
  );
}

export async function clearPrefs(droneId: string): Promise<void> {
  await del(droneId, await prefsStore());
}
