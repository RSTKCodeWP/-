/**
 * @module preflight-checklist
 * @description Pre-flight checklist model + pure state helpers for the mission
 * planner. A flat list of default check items (grouped by category) that the
 * operator ticks off before uploading a mission to the aircraft.
 *
 * Pure module: no React, no Zustand, no side effects. The item catalogue is
 * static data and the toggle / progress / grouping helpers are pure functions
 * of their inputs, so the whole surface is unit-testable in isolation. The
 * rendering component owns the checked state and calls these helpers.
 *
 * @license GPL-3.0-only
 */

/**
 * The section a checklist item belongs to. Used purely to group items under a
 * heading in the UI; the category label is translated via
 * `planner.checklist.category.<category>`.
 */
export type ChecklistCategory =
  | "aircraft"
  | "mission"
  | "airspace"
  | "environment"
  | "payload";

/** Fixed display order of the categories (headings render in this order). */
export const CHECKLIST_CATEGORIES: readonly ChecklistCategory[] = [
  "aircraft",
  "mission",
  "airspace",
  "environment",
  "payload",
] as const;

/** One line in the checklist. */
export interface ChecklistItem {
  /** Stable identifier, also the key into the checked-state map. */
  readonly id: string;
  /**
   * Translation key relative to the `planner.checklist` namespace, e.g.
   * `item.batteryCharged`. The component resolves it with `useTranslations`.
   */
  readonly labelKey: string;
  /** Grouping section. */
  readonly category: ChecklistCategory;
}

/**
 * Default pre-flight checklist. Generic, aircraft-agnostic items that apply to
 * any small drone mission. The operator can tick each one off before upload.
 */
export const DEFAULT_CHECKLIST: readonly ChecklistItem[] = [
  { id: "batteryCharged", labelKey: "item.batteryCharged", category: "aircraft" },
  { id: "propsSecure", labelKey: "item.propsSecure", category: "aircraft" },
  { id: "gpsLock", labelKey: "item.gpsLock", category: "aircraft" },
  { id: "firmwareCurrent", labelKey: "item.firmwareCurrent", category: "aircraft" },
  { id: "homePointSet", labelKey: "item.homePointSet", category: "mission" },
  { id: "failsafeConfigured", labelKey: "item.failsafeConfigured", category: "mission" },
  { id: "geofenceReviewed", labelKey: "item.geofenceReviewed", category: "mission" },
  { id: "airspaceClear", labelKey: "item.airspaceClear", category: "airspace" },
  { id: "weatherChecked", labelKey: "item.weatherChecked", category: "environment" },
  { id: "payloadSecure", labelKey: "item.payloadSecure", category: "payload" },
] as const;

/** Which items are ticked, keyed by item id. A missing key means unchecked. */
export type CheckedMap = Readonly<Record<string, boolean>>;

/**
 * Return a new checked-state map with the given item id flipped. Pure: the
 * input map is never mutated. Treats a missing key as `false`.
 */
export function toggleItem(state: CheckedMap, id: string): CheckedMap {
  return { ...state, [id]: !state[id] };
}

/**
 * Return a new checked-state map with every item set to `checked`. Handy for a
 * "check all" / "clear all" affordance.
 */
export function setAllChecked(
  items: readonly ChecklistItem[],
  checked: boolean,
): CheckedMap {
  const next: Record<string, boolean> = {};
  for (const item of items) next[item.id] = checked;
  return next;
}

/** Progress summary over a set of items given the current checked state. */
export interface ChecklistProgress {
  /** How many items are ticked. */
  readonly checked: number;
  /** Total number of items. */
  readonly total: number;
  /** True only when every item is ticked (and there is at least one item). */
  readonly complete: boolean;
  /** Fraction ticked in the range 0..1 (0 when there are no items). */
  readonly ratio: number;
}

/**
 * Compute the checked / total progress for the given items and state. Pure and
 * side-effect free; an empty list reports `complete: false` and `ratio: 0`.
 */
export function checklistProgress(
  items: readonly ChecklistItem[],
  state: CheckedMap,
): ChecklistProgress {
  const total = items.length;
  const checked = items.reduce(
    (count, item) => (state[item.id] ? count + 1 : count),
    0,
  );
  return {
    checked,
    total,
    complete: total > 0 && checked === total,
    ratio: total > 0 ? checked / total : 0,
  };
}

/**
 * Group items by their category, preserving the {@link CHECKLIST_CATEGORIES}
 * order and each item's order within its category. Categories with no items
 * are omitted from the result. Pure.
 */
export function groupByCategory(
  items: readonly ChecklistItem[],
): readonly { readonly category: ChecklistCategory; readonly items: readonly ChecklistItem[] }[] {
  return CHECKLIST_CATEGORIES.map((category) => ({
    category,
    items: items.filter((item) => item.category === category),
  })).filter((group) => group.items.length > 0);
}
