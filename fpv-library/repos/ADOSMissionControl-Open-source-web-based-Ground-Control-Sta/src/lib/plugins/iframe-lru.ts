/**
 * LRU cache for mounted plugin iframes in the per-drone slot
 * (`node.detail.tab`). Caps the live iframe count at a configurable
 * capacity (default 8) per drone-detail panel. When a new iframe is
 * added past capacity, the entry with the lowest `lastFocusedAt`
 * timestamp is evicted and its `unmount()` callback is invoked.
 *
 * Contract:
 *   - `add()` is idempotent on `pluginInstallId`: a repeat add updates
 *     the entry's `lastFocusedAt` and replaces the metadata in place
 *     without invoking either the old or new `unmount()` callback.
 *   - `touch()` updates `lastFocusedAt` for an existing entry; no-op
 *     if the entry is unknown.
 *   - `remove()` explicitly removes an entry and calls its `unmount()`.
 *   - `clear()` unmounts every entry in reverse insertion order
 *     (most-recently-added first), suitable for drone-switch teardown.
 *   - `list()` returns a read-only snapshot of current entries in
 *     insertion order.
 *
 * Eviction logs `iframe_evicted` via `console.info` with
 * `{ pluginInstallId, slot }` so observability tooling can surface
 * memory-pressure events.
 *
 * Synchronous throughout. Safe to invoke inside React render commit
 * phases (no microtasks, no scheduled work).
 */

import type { PluginSlotName } from "./types";

export interface MountedIframe {
  pluginInstallId: string;
  deviceId: string;
  slot: PluginSlotName;
  lastFocusedAt: number;
  unmount: () => void;
}

const DEFAULT_CAPACITY = 8;

export class IframeLRU {
  private readonly entries = new Map<string, MountedIframe>();
  private readonly capacity: number;

  constructor(capacity: number = DEFAULT_CAPACITY) {
    if (!Number.isFinite(capacity) || capacity < 1) {
      throw new RangeError(
        `IframeLRU capacity must be a positive integer, received ${capacity}`,
      );
    }
    this.capacity = Math.floor(capacity);
  }

  /**
   * Insert or refresh an entry. If `pluginInstallId` is already mounted
   * the call is idempotent: the entry's metadata (including
   * `lastFocusedAt`) is updated in place and no `unmount()` runs.
   *
   * Otherwise, if the cache is at capacity, the entry with the lowest
   * `lastFocusedAt` is evicted first; its `unmount()` is invoked and
   * an `iframe_evicted` log line is emitted.
   */
  add(entry: MountedIframe): void {
    const existing = this.entries.get(entry.pluginInstallId);
    if (existing) {
      // Idempotent refresh. Keep the original unmount handle (the
      // caller may have passed a stale closure on the second call).
      existing.lastFocusedAt = entry.lastFocusedAt;
      existing.deviceId = entry.deviceId;
      existing.slot = entry.slot;
      return;
    }

    if (this.entries.size >= this.capacity) {
      this.evictLeastRecentlyFocused();
    }

    this.entries.set(entry.pluginInstallId, { ...entry });
  }

  /**
   * Bump `lastFocusedAt` for an existing entry. Used by tab focus to
   * keep frequently-used plugin iframes out of the eviction set. No-op
   * if the install id is unknown.
   */
  touch(pluginInstallId: string, focusedAt: number = Date.now()): void {
    const entry = this.entries.get(pluginInstallId);
    if (!entry) {
      return;
    }
    entry.lastFocusedAt = focusedAt;
  }

  /**
   * Explicit removal. Invokes the entry's `unmount()` if present.
   * No-op if the install id is unknown.
   */
  remove(pluginInstallId: string): void {
    const entry = this.entries.get(pluginInstallId);
    if (!entry) {
      return;
    }
    this.entries.delete(pluginInstallId);
    safeUnmount(entry);
  }

  /**
   * Unmount every cached iframe. Walks in reverse insertion order so
   * the most-recently-mounted iframes are torn down first; matches
   * the drone-switch teardown contract where the freshest entries
   * are the ones the operator was just interacting with.
   */
  clear(): void {
    const snapshot = Array.from(this.entries.values()).reverse();
    this.entries.clear();
    for (const entry of snapshot) {
      safeUnmount(entry);
    }
  }

  /**
   * Read-only snapshot of current entries in insertion order. Callers
   * must not mutate the returned objects; the LRU owns them.
   */
  list(): readonly MountedIframe[] {
    return Array.from(this.entries.values());
  }

  /** Eviction helper. Picks the lowest `lastFocusedAt`. */
  private evictLeastRecentlyFocused(): void {
    let victim: MountedIframe | undefined;
    for (const entry of this.entries.values()) {
      if (!victim || entry.lastFocusedAt < victim.lastFocusedAt) {
        victim = entry;
      }
    }
    if (!victim) {
      return;
    }
    this.entries.delete(victim.pluginInstallId);
    console.info("iframe_evicted", {
      pluginInstallId: victim.pluginInstallId,
      slot: victim.slot,
    });
    safeUnmount(victim);
  }
}

/**
 * Defensively invoke a plugin's unmount callback. A throwing plugin
 * must not prevent the host from continuing to unmount its siblings.
 */
function safeUnmount(entry: MountedIframe): void {
  try {
    entry.unmount();
  } catch (err) {
    console.error("iframe_unmount_failed", {
      pluginInstallId: entry.pluginInstallId,
      slot: entry.slot,
      error: err instanceof Error ? err.message : String(err),
    });
  }
}
