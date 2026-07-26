/**
 * @module planner-history-store
 * @description Reactive mirror of the coordinated planner-history depth, for the
 * toolbar's undo/redo affordances.
 *
 * The undo/redo timeline itself lives in the plain `planner-history` module
 * (transient, module-level). The toolbar needs reactive `canUndo` / `canRedo`
 * flags, which a plain module cannot provide to React. This tiny store bridges
 * that gap. It is deliberately NOT persisted: a reload starts a fresh timeline,
 * and — unlike mirroring the depth into the persisted mission store — keeping
 * this store in sync never triggers a storage write.
 *
 * @license GPL-3.0-only
 */

import { create } from "zustand";
import { subscribeHistory } from "@/lib/planner-history";

interface PlannerHistoryState {
  /** True when there is at least one undo point on the coordinated timeline. */
  canUndo: boolean;
  /** True when there is at least one redo point on the coordinated timeline. */
  canRedo: boolean;
}

export const usePlannerHistoryStore = create<PlannerHistoryState>(() => ({
  canUndo: false,
  canRedo: false,
}));

// Keep the flags in step with the coordinated timeline. subscribeHistory fires
// immediately with the current depths, so the store initialises correctly.
subscribeHistory(({ undo, redo }) =>
  usePlannerHistoryStore.setState({ canUndo: undo > 0, canRedo: redo > 0 }),
);
