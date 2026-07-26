/**
 * ContactCache — merges contacts from all providers, keyed by id, and expires
 * stale ones. Poll providers re-emit their whole set each tick (every upsert
 * refreshes lastSeen); OGN emits incrementally. Either way an unseen contact
 * ages out by its source TTL. Pure + timer-free so it's unit-testable.
 */

import type { TrafficContact, TrafficSource } from '../../shared/traffic-types.js';

/** How long a contact survives without a fresh report, per source. Gliders
 *  report far less often than ADS-B, so they get a longer grace. */
export const TTL_BY_SOURCE: Record<TrafficSource, number> = {
  adsb: 15_000,
  ogn: 60_000,
  // Remote ID broadcasts ~1 Hz but a UAS can dip behind terrain; give it a
  // moderate grace between the fast ADS-B and slow OGN values.
  remoteid: 30_000,
};

export class ContactCache {
  private byId = new Map<string, TrafficContact>();

  /** Insert or refresh contacts. Newer lastSeen wins (ignores out-of-order). */
  upsert(contacts: TrafficContact[]): void {
    for (const c of contacts) {
      const prev = this.byId.get(c.id);
      if (!prev || c.lastSeen >= prev.lastSeen) this.byId.set(c.id, c);
    }
  }

  /** Live contacts at nowMs, dropping any past their source TTL. Expiry is
   *  applied as a side effect so the map doesn't grow unbounded. */
  snapshot(nowMs: number): TrafficContact[] {
    const out: TrafficContact[] = [];
    for (const [id, c] of this.byId) {
      if (nowMs - c.lastSeen > TTL_BY_SOURCE[c.source]) {
        this.byId.delete(id);
        continue;
      }
      out.push(c);
    }
    return out;
  }

  /** Forget every contact from a source (used when a toggle turns it off). */
  dropSource(source: TrafficSource): void {
    for (const [id, c] of this.byId) {
      if (c.source === source) this.byId.delete(id);
    }
  }

  clear(): void {
    this.byId.clear();
  }
}
