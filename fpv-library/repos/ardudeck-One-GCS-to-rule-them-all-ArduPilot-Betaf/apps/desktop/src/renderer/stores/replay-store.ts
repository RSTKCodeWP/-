/**
 * Plan replay state: which survey group's planning pipeline is being animated
 * on the mission map. Pure trigger state - the timeline itself is computed in
 * components/mission/plan-replay.ts and driven by PlanReplayOverlay.
 */
import { create } from 'zustand';

interface ReplayState {
  /** Survey group being replayed, or null when idle. */
  groupId: string | null;
  /**
   * Bumped on every start so re-triggering the same group restarts the clock
   * (the overlay keys its timer effect on this).
   */
  startSeq: number;
  startReplay: (groupId: string) => void;
  stopReplay: () => void;
}

export const useReplayStore = create<ReplayState>()((set) => ({
  groupId: null,
  startSeq: 0,
  startReplay: (groupId) => set((s) => ({ groupId, startSeq: s.startSeq + 1 })),
  stopReplay: () => set({ groupId: null }),
}));
