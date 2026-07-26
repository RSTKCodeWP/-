/**
 * @module lib/protocol/private-browsing
 * @description Heuristic private/incognito window detection.
 *
 * Browsers do not expose a formal "am I in private mode" API. We probe
 * `navigator.storage.estimate()` and compare the quota: private windows
 * across Chrome/Firefox/Safari get a capped quota in the single-digit
 * GB range or smaller, while regular windows see tens or hundreds of
 * GB on modern desktops.
 *
 * The heuristic is not perfect. Mobile browsers and some sandboxed
 * desktop environments also cap quota. Treat it as advisory: the worst
 * case is a false positive notice, which is still accurate security
 * advice (keys lost on window close is always possible in restricted
 * storage contexts).
 *
 * @license GPL-3.0-only
 */

/** Below this byte count we consider storage "ephemeral" and warn. */
const LOW_QUOTA_THRESHOLD = 1_000_000_000; // 1 GB

export async function detectPrivateBrowsing(): Promise<boolean> {
  if (typeof navigator === "undefined") return false;
  if (!navigator.storage || typeof navigator.storage.estimate !== "function") {
    return false;
  }
  try {
    const { quota } = await navigator.storage.estimate();
    if (typeof quota !== "number") return false;
    return quota < LOW_QUOTA_THRESHOLD;
  } catch {
    return false;
  }
}

/** Low-quota threshold, exported for tests. */
export const PRIVATE_BROWSING_QUOTA_THRESHOLD = LOW_QUOTA_THRESHOLD;
