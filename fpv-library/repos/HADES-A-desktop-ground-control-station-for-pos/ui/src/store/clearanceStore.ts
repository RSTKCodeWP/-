import { create } from "zustand";

import type { ClearanceState } from "./clearance";

/* Operator-owned clearance map, keyed by track_id (impl-plan Task 5.4 / core loop 5.7a).
 * The wire ContactRecord deliberately omits clearance (the localizer can't fill it); the
 * UI owns it here. A track with no entry reads as NEW. Transitions (one-click, reversible)
 * are driven from the detail panel in 5.7a — this is the storage. */

interface Coord {
  lat: number;
  lon: number;
}

interface ClearanceStoreState {
  states: Map<number, ClearanceState>;
  /** Coordinate captured at dispatch, so later motion can be measured (design "core loop"). */
  dispatchSnapshot: Map<number, Coord>;
  get: (trackId: number) => ClearanceState;
  set: (trackId: number, state: ClearanceState) => void;
  snapshot: (trackId: number, lat: number, lon: number) => void;
  /** Meters between the dispatched coordinate and a current one; null if never dispatched. */
  deltaMeters: (trackId: number, lat: number, lon: number) => number | null;
  reset: () => void;
}

const METERS_PER_DEG_LAT = 111_320;

export const useClearanceStore = create<ClearanceStoreState>((set, get) => ({
  states: new Map(),
  dispatchSnapshot: new Map(),
  get: (trackId) => get().states.get(trackId) ?? "NEW",
  set: (trackId, state) => {
    const states = new Map(get().states);
    states.set(trackId, state);
    set({ states });
  },
  snapshot: (trackId, lat, lon) => {
    const dispatchSnapshot = new Map(get().dispatchSnapshot);
    dispatchSnapshot.set(trackId, { lat, lon });
    set({ dispatchSnapshot });
  },
  deltaMeters: (trackId, lat, lon) => {
    const snap = get().dispatchSnapshot.get(trackId);
    if (!snap) return null;
    const dLat = (lat - snap.lat) * METERS_PER_DEG_LAT;
    const dLon = (lon - snap.lon) * METERS_PER_DEG_LAT * Math.cos((lat * Math.PI) / 180);
    return Math.hypot(dLat, dLon);
  },
  reset: () => set({ states: new Map(), dispatchSnapshot: new Map() }),
}));
