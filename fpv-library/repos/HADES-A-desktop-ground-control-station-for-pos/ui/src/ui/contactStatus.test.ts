import { describe, expect, it } from "vitest";

import type { ContactRecord } from "../types/wire";
import { contactStatus } from "./contactStatus";

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
    detection_conf: 0.9,
    localization_conf: 0.6,
    mc_reject_fraction: 0,
    moving_suspected: false,
    age_frames: 30,
    ...over,
  };
}

/* The pin/row status encoding (DESIGN-SYSTEM §2.4 / §6.4): a contact's actionability +
 * tier map to the closed status set. CUE_ONLY (no fix) is stale; a strong PINPOINT is
 * world-urgency (warning/orange). */

describe("contactStatus", () => {
  it("CUE_ONLY → stale (we don't have a fix)", () => {
    expect(contactStatus(c({ actionability_class: "CUE_ONLY" }))).toBe("stale");
  });

  it("PINPOINT strong → warning (world-urgency: a survivor needs you)", () => {
    expect(contactStatus(c({ actionability_class: "PINPOINT", priority_tier: "strong" }))).toBe("warning");
  });

  it("SWEEP → caution", () => {
    expect(contactStatus(c({ actionability_class: "SWEEP" }))).toBe("caution");
  });

  it("AREA candidate → info", () => {
    expect(contactStatus(c({ actionability_class: "AREA", priority_tier: "candidate" }))).toBe("info");
  });

  it("never returns critical — that hue is reserved for SYSTEM failure (P0), not contacts", () => {
    for (const ac of ["PINPOINT", "SWEEP", "AREA", "CUE_ONLY"] as const) {
      for (const t of ["contact", "candidate", "strong"] as const) {
        expect(contactStatus(c({ actionability_class: ac, priority_tier: t }))).not.toBe("critical");
      }
    }
  });
});
