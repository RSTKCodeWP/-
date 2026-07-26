import type { ClearanceState } from "./clearance";

/* The clearance state machine for the core dispatch loop (design doc "core loop one-click
 * under stress"): one-click forward transitions, every one REVERSIBLE (life-safety undo —
 * a mis-dispatch is one click to back out). One primary verb per state (the canonical
 * command panel). The dispatch chain is NEW → ASSIGNED → EN_ROUTE → FOUND; SEARCHED_NEGATIVE
 * is the other terminal (set explicitly, not via the forward chain). */

const FORWARD: Record<ClearanceState, ClearanceState> = {
  NEW: "ASSIGNED",
  ASSIGNED: "EN_ROUTE",
  EN_ROUTE: "FOUND",
  FOUND: "FOUND", // terminal
  SEARCHED_NEGATIVE: "SEARCHED_NEGATIVE", // terminal
};

const BACK: Record<ClearanceState, ClearanceState> = {
  NEW: "NEW",
  ASSIGNED: "NEW",
  EN_ROUTE: "ASSIGNED",
  FOUND: "EN_ROUTE",
  SEARCHED_NEGATIVE: "NEW",
};

const VERB: Record<ClearanceState, string> = {
  NEW: "Dispatch",
  ASSIGNED: "Mark en route",
  EN_ROUTE: "Mark found",
  FOUND: "Reopen",
  SEARCHED_NEGATIVE: "Reopen",
};

export function nextClearance(s: ClearanceState): ClearanceState {
  return FORWARD[s];
}

export function prevClearance(s: ClearanceState): ClearanceState {
  return BACK[s];
}

export function primaryVerb(s: ClearanceState): string {
  return VERB[s];
}
