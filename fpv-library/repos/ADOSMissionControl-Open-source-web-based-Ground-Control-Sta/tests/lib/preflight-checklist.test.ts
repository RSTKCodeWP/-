/**
 * @license GPL-3.0-only
 * Pure pre-flight checklist helpers: toggle, set-all, progress, grouping.
 */
import { describe, it, expect } from "vitest";
import {
  DEFAULT_CHECKLIST,
  CHECKLIST_CATEGORIES,
  toggleItem,
  setAllChecked,
  checklistProgress,
  groupByCategory,
  type CheckedMap,
  type ChecklistItem,
} from "@/lib/preflight-checklist";

describe("DEFAULT_CHECKLIST", () => {
  it("has around ten items with unique ids", () => {
    expect(DEFAULT_CHECKLIST.length).toBeGreaterThanOrEqual(8);
    const ids = DEFAULT_CHECKLIST.map((i) => i.id);
    expect(new Set(ids).size).toBe(ids.length);
  });

  it("every item has a namespaced labelKey and a known category", () => {
    for (const item of DEFAULT_CHECKLIST) {
      expect(item.labelKey).toMatch(/^item\./);
      expect(CHECKLIST_CATEGORIES).toContain(item.category);
    }
  });
});

describe("toggleItem()", () => {
  it("flips a missing key to true without mutating the input", () => {
    const state: CheckedMap = {};
    const next = toggleItem(state, "batteryCharged");
    expect(next.batteryCharged).toBe(true);
    expect(state).toEqual({}); // original untouched
  });

  it("flips a true key back to false", () => {
    const next = toggleItem({ propsSecure: true }, "propsSecure");
    expect(next.propsSecure).toBe(false);
  });

  it("leaves sibling keys intact", () => {
    const next = toggleItem({ a: true }, "b");
    expect(next).toEqual({ a: true, b: true });
  });
});

describe("setAllChecked()", () => {
  it("marks every item checked", () => {
    const next = setAllChecked(DEFAULT_CHECKLIST, true);
    for (const item of DEFAULT_CHECKLIST) expect(next[item.id]).toBe(true);
  });

  it("marks every item unchecked", () => {
    const next = setAllChecked(DEFAULT_CHECKLIST, false);
    expect(Object.values(next).every((v) => v === false)).toBe(true);
  });
});

describe("checklistProgress()", () => {
  it("reports zero for an empty checked map", () => {
    const p = checklistProgress(DEFAULT_CHECKLIST, {});
    expect(p.checked).toBe(0);
    expect(p.total).toBe(DEFAULT_CHECKLIST.length);
    expect(p.complete).toBe(false);
    expect(p.ratio).toBe(0);
  });

  it("counts partial progress and a fractional ratio", () => {
    const state = toggleItem({}, DEFAULT_CHECKLIST[0].id);
    const p = checklistProgress(DEFAULT_CHECKLIST, state);
    expect(p.checked).toBe(1);
    expect(p.ratio).toBeCloseTo(1 / DEFAULT_CHECKLIST.length, 6);
    expect(p.complete).toBe(false);
  });

  it("reports complete only when all items are ticked", () => {
    const all = setAllChecked(DEFAULT_CHECKLIST, true);
    const p = checklistProgress(DEFAULT_CHECKLIST, all);
    expect(p.checked).toBe(p.total);
    expect(p.complete).toBe(true);
    expect(p.ratio).toBe(1);
  });

  it("ignores stray checked keys not present in the item list", () => {
    const p = checklistProgress(DEFAULT_CHECKLIST, { notAnItem: true });
    expect(p.checked).toBe(0);
  });

  it("treats an empty item list as not complete", () => {
    const p = checklistProgress([], { anything: true });
    expect(p.total).toBe(0);
    expect(p.complete).toBe(false);
    expect(p.ratio).toBe(0);
  });
});

describe("groupByCategory()", () => {
  it("returns groups in the fixed category order", () => {
    const groups = groupByCategory(DEFAULT_CHECKLIST);
    const order = groups.map((g) => g.category);
    const expectedOrder = CHECKLIST_CATEGORIES.filter((c) =>
      DEFAULT_CHECKLIST.some((i) => i.category === c),
    );
    expect(order).toEqual(expectedOrder);
  });

  it("places every item into exactly one group", () => {
    const groups = groupByCategory(DEFAULT_CHECKLIST);
    const flattened = groups.flatMap((g) => g.items);
    expect(flattened.length).toBe(DEFAULT_CHECKLIST.length);
  });

  it("omits categories with no items", () => {
    const items: ChecklistItem[] = [
      { id: "x", labelKey: "item.x", category: "aircraft" },
    ];
    const groups = groupByCategory(items);
    expect(groups.length).toBe(1);
    expect(groups[0].category).toBe("aircraft");
  });
});
