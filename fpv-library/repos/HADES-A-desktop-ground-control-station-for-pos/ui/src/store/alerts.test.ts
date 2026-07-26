import { beforeEach, describe, expect, it } from "vitest";

import { useAlertStore } from "./alerts";
import type { ContactRecord } from "../types/wire";

function c(over: Partial<ContactRecord>): ContactRecord {
  return {
    type: "contact",
    frame_id: 0,
    track_id: 1,
    lat: 30,
    lon: -88,
    r95_m: 18,
    actionability_class: "PINPOINT",
    semi_major_m: 22,
    semi_minor_m: 14,
    orientation_deg: 30,
    priority_tier: "strong",
    convergence_state: "STABLE",
    heading_limited: false,
    aspect_spread_deg: 40,
    detection_conf: 0.95,
    localization_conf: 0.85,
    mc_reject_fraction: 0,
    moving_suspected: false,
    age_frames: 3,
    ...over,
  };
}

/* Alarm-fatigue subsystem (impl-plan Task 5.7b; DESIGN-SYSTEM §4.7). Recall-first → a
 * detection firehose, so alerts are RATIONED: only a high-confidence PINPOINT/SWEEP fires
 * the loud (tier-3) alert; CUE_ONLY posts silently. Per-contact ack quiets it; the unack
 * count never silently resets; the same track never re-chimes; bursts coalesce. */

describe("alert store", () => {
  beforeEach(() => useAlertStore.getState().reset());

  it("a high-confidence PINPOINT raises a loud (tier-3) alert", () => {
    useAlertStore.getState().consider(c({ track_id: 42 }));
    expect(useAlertStore.getState().unacked()).toContain(42);
  });

  it("a CUE_ONLY posts SILENTLY — no loud alert", () => {
    useAlertStore.getState().consider(c({ track_id: 9, actionability_class: "CUE_ONLY", localization_conf: 0.2 }));
    expect(useAlertStore.getState().unacked()).not.toContain(9);
  });

  it("a low-confidence contact does not fire the loud alert", () => {
    useAlertStore.getState().consider(c({ track_id: 5, detection_conf: 0.4, localization_conf: 0.3 }));
    expect(useAlertStore.getState().unacked()).not.toContain(5);
  });

  it("never re-chimes the same track (idempotent per track)", () => {
    const s = useAlertStore.getState();
    s.consider(c({ track_id: 42 }));
    s.consider(c({ track_id: 42, r95_m: 10 })); // a refined record for the same track
    expect(useAlertStore.getState().chimeCount).toBe(1);
  });

  it("ack removes a contact from the unacked set", () => {
    const s = useAlertStore.getState();
    s.consider(c({ track_id: 42 }));
    s.ack(42);
    expect(useAlertStore.getState().unacked()).not.toContain(42);
  });

  it("unack count never silently resets on new data — only ack clears it", () => {
    const s = useAlertStore.getState();
    s.consider(c({ track_id: 42 }));
    s.consider(c({ track_id: 43 }));
    expect(useAlertStore.getState().unacked()).toHaveLength(2);
    s.consider(c({ track_id: 42, r95_m: 5 })); // refined; must NOT clear the unacked
    expect(useAlertStore.getState().unacked()).toHaveLength(2);
  });

  it("coalesces a burst into one count rather than N separate alerts", () => {
    const s = useAlertStore.getState();
    s.consider(c({ track_id: 1 }));
    s.consider(c({ track_id: 2 }));
    s.consider(c({ track_id: 3 }));
    // chime fires once per NEW track but the operator-facing unacked count is the burst size
    expect(useAlertStore.getState().unacked()).toHaveLength(3);
    expect(useAlertStore.getState().chimeCount).toBe(3); // one per new track, none repeated
  });
});
