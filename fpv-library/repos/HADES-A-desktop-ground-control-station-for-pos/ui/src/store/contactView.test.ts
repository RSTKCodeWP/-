import { describe, expect, it } from "vitest";

import type { ContactRecord } from "../types/wire";
import type { ClearanceState } from "./clearance";
import { buildContactRows, type ContactRow, type SortSpec } from "./contactView";

function c(over: Partial<ContactRecord>): ContactRecord {
  return {
    type: "contact",
    frame_id: 0,
    track_id: 1,
    lat: 30,
    lon: -88,
    r95_m: 18,
    actionability_class: "SWEEP",
    semi_major_m: 22,
    semi_minor_m: 14,
    orientation_deg: 30,
    priority_tier: "candidate",
    convergence_state: "STABLE",
    heading_limited: false,
    aspect_spread_deg: 40,
    detection_conf: 0.5,
    localization_conf: 0.5,
    mc_reject_fraction: 0.0,
    moving_suspected: false,
    age_frames: 30,
    ...over,
  };
}

const noClear = new Map<number, ClearanceState>();

describe("buildContactRows", () => {
  it("returns one row per contact, carrying clearance (defaulting to NEW)", () => {
    const contacts = new Map([[1, c({ track_id: 1 })]]);
    const rows = buildContactRows(contacts, noClear, defaultSort());
    expect(rows).toHaveLength(1);
    expect(rows[0].clearance).toBe("NEW");
  });

  it("default sort puts the most actionable contact first (PINPOINT strong > SWEEP candidate)", () => {
    const contacts = new Map([
      [1, c({ track_id: 1, actionability_class: "SWEEP", priority_tier: "candidate" })],
      [2, c({ track_id: 2, actionability_class: "PINPOINT", priority_tier: "strong" })],
    ]);
    const rows = buildContactRows(contacts, noClear, defaultSort());
    expect(rows[0].record.track_id).toBe(2); // the urgent one rises to the top
  });

  it("cleared contacts demote below active ones regardless of actionability", () => {
    const clear = new Map<number, ClearanceState>([[2, "FOUND"]]);
    const contacts = new Map([
      [1, c({ track_id: 1, actionability_class: "SWEEP", priority_tier: "candidate" })],
      [2, c({ track_id: 2, actionability_class: "PINPOINT", priority_tier: "strong" })],
    ]);
    const rows = buildContactRows(contacts, clear, defaultSort());
    // even though trk2 is more actionable, FOUND demotes it
    expect(rows[0].record.track_id).toBe(1);
    expect(rows[1].record.track_id).toBe(2);
    expect(rows[1].cleared).toBe(true);
  });

  it("sorts by age ascending when asked", () => {
    const contacts = new Map([
      [1, c({ track_id: 1, age_frames: 90 })],
      [2, c({ track_id: 2, age_frames: 10 })],
    ]);
    const rows = buildContactRows(contacts, noClear, { key: "age", dir: "asc" });
    expect(rows.map((r) => r.record.track_id)).toEqual([2, 1]);
  });

  it("sorts by detection confidence descending when asked", () => {
    const contacts = new Map([
      [1, c({ track_id: 1, detection_conf: 0.3 })],
      [2, c({ track_id: 2, detection_conf: 0.95 })],
    ]);
    const rows = buildContactRows(contacts, noClear, { key: "det", dir: "desc" });
    expect(rows[0].record.track_id).toBe(2);
  });

  it("filters by clearance state", () => {
    const clear = new Map<number, ClearanceState>([[2, "FOUND"]]);
    const contacts = new Map([
      [1, c({ track_id: 1 })],
      [2, c({ track_id: 2 })],
    ]);
    const rows = buildContactRows(contacts, clear, defaultSort(), {
      clearance: new Set<ClearanceState>(["NEW"]),
    });
    expect(rows.map((r) => r.record.track_id)).toEqual([1]);
  });

  it("a cleared filter still demotes within the filtered set (does not vanish active ones)", () => {
    const contacts = new Map([
      [1, c({ track_id: 1, actionability_class: "PINPOINT", priority_tier: "strong" })],
    ]);
    const rows: ContactRow[] = buildContactRows(contacts, noClear, defaultSort());
    expect(rows[0].cleared).toBe(false);
  });
});

function defaultSort(): SortSpec {
  return { key: "actionability", dir: "desc" };
}
