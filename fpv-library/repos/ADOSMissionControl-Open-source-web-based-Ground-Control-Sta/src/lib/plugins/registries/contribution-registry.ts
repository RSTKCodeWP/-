/**
 * @module plugins/registries/contribution-registry
 * @description A small generic host-registry factory. Each contribution kind
 * (tabs, settings sections, model registrations, mission templates, map
 * overlays, ...) holds its built-in and plugin contributions in one Zustand
 * store of the same shape, modeled on the Skill registry. The slot hosts read
 * from these registries to render whatever is currently registered.
 *
 * Resolution orders by an optional `order` field (ascending; an item lacking
 * `order` sorts after all ordered items), tie-broken by registration order so
 * the result is stable.
 *
 * @license GPL-3.0-only
 */

import { create } from "zustand";

export interface ContributionRegistryState<T extends { id: string }> {
  /** All registered contributions, keyed by id. */
  items: Map<string, T>;
  /** Registration order, used as a stable tie-breaker. */
  _order: Map<string, number>;
  /** Monotonic registration counter. */
  _seq: number;

  register: (item: T) => void;
  unregister: (id: string) => void;
  /** Resolve the registered items, optionally filtered, in display order. */
  resolve: (filter?: (item: T) => boolean) => T[];
}

/** Read an item's `order`, defaulting an absent/non-finite value to +Infinity
 * so unordered items sort after every ordered one. */
function readOrder(item: { id: string }): number {
  const o = (item as { order?: unknown }).order;
  return typeof o === "number" && Number.isFinite(o)
    ? o
    : Number.POSITIVE_INFINITY;
}

/**
 * Build a contribution registry store for one contribution kind. The returned
 * value is a Zustand hook; call `.getState()` for imperative access and use a
 * selector in React components.
 */
export function createContributionRegistry<T extends { id: string }>() {
  return create<ContributionRegistryState<T>>((set, get) => ({
    items: new Map<string, T>(),
    _order: new Map<string, number>(),
    _seq: 0,

    register: (item) =>
      set((s) => {
        const items = new Map(s.items);
        items.set(item.id, item);
        const order = new Map(s._order);
        // Preserve the original insertion slot if an item re-registers.
        const seq = order.has(item.id) ? s._seq : s._seq + 1;
        if (!order.has(item.id)) order.set(item.id, seq);
        return { items, _order: order, _seq: seq };
      }),

    unregister: (id) =>
      set((s) => {
        if (!s.items.has(id)) return s;
        const items = new Map(s.items);
        items.delete(id);
        const order = new Map(s._order);
        order.delete(id);
        return { items, _order: order };
      }),

    resolve: (filter) => {
      const { items, _order } = get();
      const list: T[] = [];
      for (const item of items.values()) {
        if (!filter || filter(item)) list.push(item);
      }
      list.sort((a, b) => {
        const oa = readOrder(a);
        const ob = readOrder(b);
        // Finite orders sort ascending; an unordered item (+Infinity) sorts
        // after any finite order. Equal buckets (incl. both unordered) fall
        // back to registration order.
        if (oa !== ob) return oa < ob ? -1 : 1;
        return (_order.get(a.id) ?? 0) - (_order.get(b.id) ?? 0);
      });
      return list;
    },
  }));
}
