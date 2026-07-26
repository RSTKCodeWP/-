import { create } from "zustand";

import type { ContactRecord } from "../types/wire";

/* Alarm-fatigue subsystem (impl-plan Task 5.7b; DESIGN-SYSTEM §4.7). Recall-first means a
 * detection firehose, so the LOUD (tier-3) alert is rationed: it fires only for a
 * high-confidence PINPOINT/SWEEP, and only ONCE per track (no repeat-chime even as the
 * localizer re-emits refined records). CUE_ONLY / AREA / low-confidence post silently
 * (ambient/attention tiers, handled in the list/map, not here). Per-contact ack quiets a
 * contact; the unacked set NEVER silently resets on new data — only an explicit ack clears
 * it, so the operator can't lose track of what still needs a look. */

// loud-alert gate: a real, well-localized survivor worth pulling the operator's eyes
function isLoudWorthy(c: ContactRecord): boolean {
  const actionable = c.actionability_class === "PINPOINT" || c.actionability_class === "SWEEP";
  const confident = c.detection_conf >= 0.7 && c.localization_conf >= 0.5;
  return actionable && confident;
}

interface AlertState {
  /** tracks that have fired a loud alert and not yet been acked */
  unackedSet: Set<number>;
  /** tracks that have ever chimed (so we never re-chime the same track) */
  chimedSet: Set<number>;
  /** total chimes fired this session (one per new loud-worthy track) */
  chimeCount: number;

  consider: (c: ContactRecord) => void;
  ack: (trackId: number) => void;
  unacked: () => number[];
  reset: () => void;
}

export const useAlertStore = create<AlertState>((set, get) => ({
  unackedSet: new Set(),
  chimedSet: new Set(),
  chimeCount: 0,

  consider: (c) => {
    if (!isLoudWorthy(c)) return;
    if (get().chimedSet.has(c.track_id)) return; // already chimed for this track — never repeat
    const chimedSet = new Set(get().chimedSet).add(c.track_id);
    const unackedSet = new Set(get().unackedSet).add(c.track_id);
    set({ chimedSet, unackedSet, chimeCount: get().chimeCount + 1 });
  },

  ack: (trackId) => {
    const unackedSet = new Set(get().unackedSet);
    unackedSet.delete(trackId);
    set({ unackedSet });
  },

  unacked: () => [...get().unackedSet],

  reset: () => set({ unackedSet: new Set(), chimedSet: new Set(), chimeCount: 0 }),
}));
