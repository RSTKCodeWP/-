import { create } from "zustand";

import type { ContactRecord, DetectionMessage, JsonMessage } from "../types/wire";

/* The contact store — pure data ingestion from the WS JSON channel, outside React render
 * (DESIGN.md / impl-plan Task 5.1). Selection state is NOT here; it's the separate spine
 * (Task 5.2). The store dedups contacts by `track_id` (latest record wins — the localizer
 * re-emits a refined record for the same track) and tracks the newest detection frame for
 * the video overlay. A CUE_ONLY contact with null lat/lon is preserved as-is (the UI
 * special-cases "no fix" rather than plotting a false pin). */

interface ContactState {
  /** All known contacts keyed by track_id (latest record per track). */
  contacts: Map<number, ContactRecord>;
  /** The newest per-frame detection message (for the video box overlay). */
  latestDetection: DetectionMessage | null;

  ingestContact: (record: ContactRecord) => void;
  ingestDetection: (msg: DetectionMessage) => void;
  /** Route a JSON-channel message by its discriminator. */
  ingestJson: (msg: JsonMessage) => void;
  /** Operator marks an AI-missed person on the video (recall-first backstop). Returns the
   *  new contact's track_id (negative, so it never collides with the tracker's positive ids). */
  addManualContact: () => number;
  reset: () => void;
}

let nextManualId = -1;

export const useContactStore = create<ContactState>((set, get) => ({
  contacts: new Map(),
  latestDetection: null,

  ingestContact: (record) => {
    const contacts = new Map(get().contacts);
    contacts.set(record.track_id, record);
    set({ contacts });
  },

  ingestDetection: (msg) => {
    const current = get().latestDetection;
    // Ignore out-of-order stragglers — only advance to a newer frame (drop-to-latest).
    if (current && msg.frame_id < current.frame_id) return;
    set({ latestDetection: msg });
  },

  ingestJson: (msg) => {
    if (msg.type === "contact") get().ingestContact(msg);
    else get().ingestDetection(msg);
  },

  addManualContact: () => {
    const track_id = nextManualId--;
    const det = get().latestDetection;
    get().ingestContact({
      type: "contact",
      frame_id: det?.frame_id ?? 0,
      track_id,
      // operator marks a CUE, does not claim a localized fix (honest: null coord, big radius)
      lat: null,
      lon: null,
      r95_m: 0,
      actionability_class: "CUE_ONLY",
      semi_major_m: 0,
      semi_minor_m: 0,
      orientation_deg: 0,
      priority_tier: "candidate",
      convergence_state: "CONVERGING",
      heading_limited: false,
      aspect_spread_deg: 0,
      detection_conf: 1.0, // a human SAW this person — detection certainty is the point
      localization_conf: 0.0, // but it isn't localized
      mc_reject_fraction: 0,
      moving_suspected: false,
      age_frames: 0,
    });
    return track_id;
  },

  reset: () => set({ contacts: new Map(), latestDetection: null }),
}));
