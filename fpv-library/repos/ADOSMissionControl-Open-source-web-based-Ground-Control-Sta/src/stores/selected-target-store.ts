/**
 * @module selected-target-store
 * @description The host-owned SELECTED target — the detection the operator
 * clicked in the cockpit overlay. It is the shared anchor for target-scoped
 * actions: the target-action popup reads it, and every action (built-in or
 * plugin-contributed) operates on it. Ephemeral UI state (not persisted); it
 * clears on drone switch or when the operator dismisses the popup.
 *
 * @license GPL-3.0-only
 */

import { create } from "zustand";

import type { DetectionBox } from "@/stores/vision-detections-store";

export interface SelectedTarget {
  /** The node id (`node:<deviceId>`) whose overlay the target was clicked in. */
  droneId: string;
  /** The camera the detection came from. */
  cameraId: string;
  /** The tracker's stable id for this subject, or null for an untracked box. */
  trackId: number | null;
  /** The box in SOURCE-FRAME pixels (the detection's own coordinate space). */
  bbox: DetectionBox;
  classLabel: string;
  confidence: number;
}

interface SelectedTargetState {
  selected: SelectedTarget | null;
  select: (target: SelectedTarget) => void;
  clear: () => void;
}

export const useSelectedTargetStore = create<SelectedTargetState>()((set) => ({
  selected: null,
  select: (target) => set({ selected: target }),
  clear: () => set({ selected: null }),
}));
