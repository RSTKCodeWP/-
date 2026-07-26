import { beforeEach, describe, expect, it } from "vitest";

import type { ContactRecord, DetectionMessage } from "../types/wire";
import { useContactStore } from "./contacts";

/** A minimal valid ContactRecord with sensible defaults; override per test. */
function makeContact(over: Partial<ContactRecord> = {}): ContactRecord {
  return {
    type: "contact",
    frame_id: 0,
    track_id: 1,
    lat: 30.21487,
    lon: -88.52103,
    r95_m: 18,
    actionability_class: "PINPOINT",
    semi_major_m: 22,
    semi_minor_m: 14,
    orientation_deg: 30,
    priority_tier: "strong",
    convergence_state: "STABLE",
    heading_limited: false,
    aspect_spread_deg: 40,
    detection_conf: 0.94,
    localization_conf: 0.71,
    mc_reject_fraction: 0.02,
    moving_suspected: false,
    age_frames: 3,
    ...over,
  };
}

function makeDetection(over: Partial<DetectionMessage> = {}): DetectionMessage {
  return {
    type: "detection",
    frame_id: 0,
    timestamp: 0,
    boxes: [{ box_xyxy: [10, 20, 30, 50], conf: 0.9, cls: "person" }],
    ...over,
  };
}

describe("contact store", () => {
  beforeEach(() => {
    useContactStore.getState().reset();
  });

  it("ingests a ContactRecord and exposes it keyed by track_id", () => {
    useContactStore.getState().ingestContact(makeContact({ track_id: 42 }));

    const contacts = useContactStore.getState().contacts;
    expect(contacts.size).toBe(1);
    expect(contacts.get(42)?.track_id).toBe(42);
  });

  it("dedups by track_id, keeping the latest record for that track", () => {
    const store = useContactStore.getState();
    store.ingestContact(makeContact({ track_id: 7, frame_id: 1, r95_m: 50 }));
    store.ingestContact(makeContact({ track_id: 7, frame_id: 9, r95_m: 12 }));

    const contacts = useContactStore.getState().contacts;
    expect(contacts.size).toBe(1);
    expect(contacts.get(7)?.frame_id).toBe(9);
    expect(contacts.get(7)?.r95_m).toBe(12); // refined record won
  });

  it("keeps distinct tracks separate (concurrent survivors)", () => {
    const store = useContactStore.getState();
    store.ingestContact(makeContact({ track_id: 1 }));
    store.ingestContact(makeContact({ track_id: 2 }));

    expect(useContactStore.getState().contacts.size).toBe(2);
  });

  it("preserves a CUE_ONLY contact with null lat/lon (no false Null-Island pin)", () => {
    useContactStore
      .getState()
      .ingestContact(makeContact({ track_id: 5, lat: null, lon: null, actionability_class: "CUE_ONLY" }));

    const c = useContactStore.getState().contacts.get(5);
    expect(c?.lat).toBeNull();
    expect(c?.lon).toBeNull();
    expect(c?.actionability_class).toBe("CUE_ONLY");
  });

  it("ingests the latest DetectionMessage and exposes it by frame_id", () => {
    useContactStore.getState().ingestDetection(makeDetection({ frame_id: 100 }));

    expect(useContactStore.getState().latestDetection?.frame_id).toBe(100);
  });

  it("advances latestDetection to the newest frame, not an older straggler", () => {
    const store = useContactStore.getState();
    store.ingestDetection(makeDetection({ frame_id: 100 }));
    store.ingestDetection(makeDetection({ frame_id: 50 })); // out-of-order straggler

    expect(useContactStore.getState().latestDetection?.frame_id).toBe(100);
  });

  it("routes a JsonMessage by its discriminator", () => {
    const store = useContactStore.getState();
    store.ingestJson(makeContact({ track_id: 3 }));
    store.ingestJson(makeDetection({ frame_id: 200 }));

    expect(useContactStore.getState().contacts.get(3)?.track_id).toBe(3);
    expect(useContactStore.getState().latestDetection?.frame_id).toBe(200);
  });

  it("addManualContact creates an honest CUE_ONLY contact with a fresh negative track id", () => {
    const store = useContactStore.getState();
    const a = store.addManualContact();
    const b = store.addManualContact();
    const contacts = useContactStore.getState().contacts;
    expect(contacts.size).toBe(2);
    // manual contacts use negative ids so they never collide with the tracker's positive ids
    expect(a).toBeLessThan(0);
    expect(b).not.toBe(a);
    const c = contacts.get(a)!;
    expect(c.actionability_class).toBe("CUE_ONLY"); // operator marks a cue; doesn't claim a fix
    expect(c.lat).toBeNull();
    expect(c.lon).toBeNull();
  });
});
