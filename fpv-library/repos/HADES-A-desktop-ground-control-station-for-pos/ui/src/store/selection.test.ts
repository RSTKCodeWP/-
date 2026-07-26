import { beforeEach, describe, expect, it } from "vitest";

import { useContactStore } from "./contacts";
import { useSelectionStore } from "./selection";

/** Minimal contact factory for the survives-data-update test. */
function makeContact(track_id: number) {
  return {
    type: "contact" as const,
    frame_id: 0,
    track_id,
    lat: 30.21,
    lon: -88.52,
    r95_m: 18,
    actionability_class: "PINPOINT" as const,
    semi_major_m: 22,
    semi_minor_m: 14,
    orientation_deg: 30,
    priority_tier: "strong" as const,
    convergence_state: "STABLE" as const,
    heading_limited: false,
    aspect_spread_deg: 40,
    detection_conf: 0.94,
    localization_conf: 0.71,
    mc_reject_fraction: 0.02,
    moving_suspected: false,
    age_frames: 3,
  };
}

describe("selection spine", () => {
  beforeEach(() => {
    useSelectionStore.getState().reset();
    useContactStore.getState().reset();
  });

  it("starts with nothing selected and nothing hovered", () => {
    const s = useSelectionStore.getState();
    expect(s.selectedId).toBeNull();
    expect(s.hoveredId).toBeNull();
  });

  it("commits a selection (click) — global, one source of truth", () => {
    useSelectionStore.getState().select(42);
    expect(useSelectionStore.getState().selectedId).toBe(42);
  });

  it("hover preview is DISTINCT from a committed selection", () => {
    const s = useSelectionStore.getState();
    s.select(42);
    s.hover(7);

    const after = useSelectionStore.getState();
    expect(after.selectedId).toBe(42); // hover did NOT change the commit
    expect(after.hoveredId).toBe(7);
  });

  it("clearHover does not touch the committed selection", () => {
    const s = useSelectionStore.getState();
    s.select(42);
    s.hover(7);
    s.clearHover();

    const after = useSelectionStore.getState();
    expect(after.hoveredId).toBeNull();
    expect(after.selectedId).toBe(42);
  });

  it("selecting again replaces the previous selection (single-select)", () => {
    const s = useSelectionStore.getState();
    s.select(42);
    s.select(7);
    expect(useSelectionStore.getState().selectedId).toBe(7);
  });

  it("clear() deselects", () => {
    const s = useSelectionStore.getState();
    s.select(42);
    s.clear();
    expect(useSelectionStore.getState().selectedId).toBeNull();
  });

  it("toggle selects when unselected and deselects when already selected", () => {
    const s = useSelectionStore.getState();
    s.toggle(42);
    expect(useSelectionStore.getState().selectedId).toBe(42);
    useSelectionStore.getState().toggle(42);
    expect(useSelectionStore.getState().selectedId).toBeNull();
  });

  it("selection SURVIVES contact data updates (the spine is independent of the data store)", () => {
    // select a contact, then mutate the contact store (new + refined records arrive)
    useSelectionStore.getState().select(42);
    useContactStore.getState().ingestContact(makeContact(42));
    useContactStore.getState().ingestContact(makeContact(99)); // a new contact arrives
    useContactStore.getState().ingestContact({ ...makeContact(42), r95_m: 5 }); // 42 refines

    // selection is untouched by any of it
    expect(useSelectionStore.getState().selectedId).toBe(42);
  });

  it("isSelected / isHovered helpers reflect state", () => {
    const s = useSelectionStore.getState();
    s.select(42);
    s.hover(7);
    const after = useSelectionStore.getState();
    expect(after.isSelected(42)).toBe(true);
    expect(after.isSelected(7)).toBe(false);
    expect(after.isHovered(7)).toBe(true);
    expect(after.isHovered(42)).toBe(false);
  });
});
