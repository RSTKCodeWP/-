import type { ContactRecord } from "../types/wire";
import { isCleared, type ClearanceState } from "./clearance";

/* The list view-model — pure derivation of the displayed, ordered, filtered rows from the
 * contact store + the operator's clearance map + a sort/filter spec (impl-plan Task 5.4).
 * Kept pure (no store access) so it is exhaustively unit-testable; the component just feeds
 * it state and renders the result.
 *
 * Two ordering invariants the design fixes:
 *   - DEFAULT sort = actionability: the contact that needs action sits at the top-left where
 *     the eye lands first (<2s find).
 *   - CLEARED contacts always DEMOTE below active ones (never vanish) — a resolved contact
 *     stays auditable but out of the way. This overrides the active sort key. */

export type SortKey =
  | "actionability"
  | "track"
  | "det"
  | "loc"
  | "age"
  | "convergence";
export type SortDir = "asc" | "desc";

export interface SortSpec {
  key: SortKey;
  dir: SortDir;
}

export interface FilterSpec {
  clearance?: ReadonlySet<ClearanceState>;
  cls?: ReadonlySet<string>;
}

export interface ContactRow {
  record: ContactRecord;
  clearance: ClearanceState;
  cleared: boolean;
}

// Higher = more urgent → sorts to the top under the default actionability sort.
const ACTIONABILITY_RANK: Record<ContactRecord["actionability_class"], number> = {
  PINPOINT: 3,
  SWEEP: 2,
  AREA: 1,
  CUE_ONLY: 0,
};
const TIER_RANK: Record<ContactRecord["priority_tier"], number> = {
  strong: 2,
  candidate: 1,
  contact: 0,
};

function actionabilityScore(r: ContactRecord): number {
  // tier breaks ties within an actionability class
  return ACTIONABILITY_RANK[r.actionability_class] * 10 + TIER_RANK[r.priority_tier];
}

function compareBy(key: SortKey, a: ContactRow, b: ContactRow): number {
  switch (key) {
    case "actionability":
      return actionabilityScore(a.record) - actionabilityScore(b.record);
    case "track":
      return a.record.track_id - b.record.track_id;
    case "det":
      return a.record.detection_conf - b.record.detection_conf;
    case "loc":
      return a.record.localization_conf - b.record.localization_conf;
    case "age":
      return a.record.age_frames - b.record.age_frames;
    case "convergence":
      // STABLE > CONVERGING
      return (
        Number(a.record.convergence_state === "STABLE") -
        Number(b.record.convergence_state === "STABLE")
      );
  }
}

export function buildContactRows(
  contacts: ReadonlyMap<number, ContactRecord>,
  clearance: ReadonlyMap<number, ClearanceState>,
  sort: SortSpec,
  filter: FilterSpec = {},
): ContactRow[] {
  let rows: ContactRow[] = [...contacts.values()].map((record) => {
    const state = clearance.get(record.track_id) ?? "NEW";
    return { record, clearance: state, cleared: isCleared(state) };
  });

  if (filter.clearance) {
    rows = rows.filter((r) => filter.clearance!.has(r.clearance));
  }
  if (filter.cls) {
    rows = rows.filter((r) => filter.cls!.has(r.record.actionability_class));
  }

  const sign = sort.dir === "asc" ? 1 : -1;
  rows.sort((a, b) => {
    // cleared always demotes below active, regardless of the active sort key
    if (a.cleared !== b.cleared) return a.cleared ? 1 : -1;
    const c = compareBy(sort.key, a, b) * sign;
    if (c !== 0) return c;
    return a.record.track_id - b.record.track_id; // stable tiebreak
  });

  return rows;
}
