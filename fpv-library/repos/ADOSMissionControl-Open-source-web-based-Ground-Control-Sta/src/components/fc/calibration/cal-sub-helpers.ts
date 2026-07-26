/**
 * Shared subscription management helpers for calibration.
 * Used by both calibration-subscriptions.ts and compass-cal-subscriptions.ts.
 */

import { useDiagnosticsStore } from "@/stores/diagnostics-store";
import {
  type CalibrationState,
  CAL_TIMEOUTS,
} from "./calibration-types";

export interface SubsManager {
  subsRef: React.MutableRefObject<Map<string, (() => void)[]>>;
  timeoutRef: React.MutableRefObject<Map<string, ReturnType<typeof setTimeout>>>;
}

export function addSub(manager: SubsManager, type: string, unsub: () => void) {
  if (!manager.subsRef.current.has(type)) manager.subsRef.current.set(type, []);
  manager.subsRef.current.get(type)!.push(unsub);
}

export function cleanupSubs(manager: SubsManager, type: string) {
  manager.subsRef.current.get(type)?.forEach((unsub) => unsub());
  manager.subsRef.current.delete(type);
  manager.timeoutRef.current.delete(type);
}

export function resetTimeout(
  manager: SubsManager,
  type: string,
  setter: React.Dispatch<React.SetStateAction<CalibrationState>>,
  duration?: number,
  // Optional graceful finalizer. When the timer fires, this receives the current
  // in-progress state and returns the terminal state to apply (e.g. a compass cal
  // that stalled but has good offsets should land on "waiting_accept", not a bare
  // error). Subscriptions are torn down before it runs. Defaults to a plain error.
  onTimeout?: (prev: CalibrationState) => CalibrationState,
) {
  const old = manager.timeoutRef.current.get(type);
  if (old) clearTimeout(old);
  const ms = duration ?? CAL_TIMEOUTS[type] ?? 60_000;
  const newTimeout = setTimeout(() => {
    setter((prev) => {
      if (prev.status !== "in_progress") return prev;
      cleanupSubs(manager, type);
      if (onTimeout) return onTimeout(prev);
      useDiagnosticsStore.getState().logCalibration(type, "failed");
      return { ...prev, status: "error", message: "Calibration timed out — no response from flight controller" };
    });
  }, ms);
  manager.timeoutRef.current.set(type, newTimeout);
  addSub(manager, type, () => clearTimeout(newTimeout));
}
