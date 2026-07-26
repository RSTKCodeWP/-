/* Clearance state — a UI-owned, mission-log-mutated field (DESIGN.md: deferred from the
 * wire schema because the localizer cannot honestly fill it; the operator owns it). The
 * closed state machine for dispatch (design doc "core loop"): NEW → ASSIGNED → EN_ROUTE →
 * SEARCHED_NEGATIVE / FOUND. Transitions are one-click and REVERSIBLE (life-safety undo). */

export type ClearanceState =
  | "NEW"
  | "ASSIGNED"
  | "EN_ROUTE"
  | "SEARCHED_NEGATIVE"
  | "FOUND";

/** Cleared = resolved; these demote in the list (never vanish). */
export const CLEARED_STATES: ReadonlySet<ClearanceState> = new Set([
  "SEARCHED_NEGATIVE",
  "FOUND",
]);

export function isCleared(state: ClearanceState): boolean {
  return CLEARED_STATES.has(state);
}
