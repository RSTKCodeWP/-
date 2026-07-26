import { create } from "zustand";

import type { Provenance } from "../data/mission";

/* Holds the demo-mode provenance the banner reads (Phase 6). Null in the live app + in the
 * synthetic-mock fallback; set only when the static demo replays a baked `mission.json`. Keeping
 * it in a store (not a prop) lets the always-on banner read it without threading it through the
 * shell, mirroring how `useSystemStore` feeds the status strip. */

interface ProvenanceState {
  provenance: Provenance | null;
  setProvenance: (p: Provenance | null) => void;
}

export const useProvenanceStore = create<ProvenanceState>((set) => ({
  provenance: null,
  setProvenance: (p) => set({ provenance: p }),
}));
