/**
 * @module log-activity-store
 * @description Monotonic per-drone count of flight-log (STATUSTEXT) messages
 * received. Lets the Dashboard show an "updates available" indicator on the
 * collapsed Flight Logs rail without keeping the full logs panel mounted.
 * @license GPL-3.0-only
 */

import { create } from "zustand";

interface LogActivityState {
  /** Total messages seen per drone id since the probe mounted. */
  counts: Record<string, number>;
  bump: (droneId: string) => void;
  reset: (droneId: string) => void;
}

export const useLogActivityStore = create<LogActivityState>((set) => ({
  counts: {},
  bump: (droneId) =>
    set((s) => ({
      counts: { ...s.counts, [droneId]: (s.counts[droneId] ?? 0) + 1 },
    })),
  reset: (droneId) =>
    set((s) => ({ counts: { ...s.counts, [droneId]: 0 } })),
}));
