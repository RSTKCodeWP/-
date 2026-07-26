import type { ContactRecord, DetectionMessage } from "../types/wire";
import type { MockFrame } from "./mock-ws";

/* A small canned mission for the mock-driven UI (impl-plan Task 5.1 review fix: the binary
 * channel must carry frames so the video panel has something to paint). Deterministic, so
 * the demo + Playwright runs are reproducible. A tiny synthetic JPEG-ish frame is fine — the
 * panel only needs bytes per frame_id; the real recorded feed replaces this in 5.9/P6.
 *
 * NOTE: lat/lon here are illustrative (a Gulf-coast scene near the design's reference origin).
 * Real coordinates come from the localizer over the wire. */

// a minimal valid 1x1 JPEG (gray) as bytes — enough for the canvas decode path
const TINY_JPEG = Uint8Array.from(
  atob(
    "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/wAALCAABAAEBAREA/8QAFAABAAAAAAAAAAAAAAAAAAAAAv/EABQQAQAAAAAAAAAAAAAAAAAAAAD/2gAIAQEAAD8AfwD/2Q==",
  ),
  (c) => c.charCodeAt(0),
);

export interface CannedMission {
  frames: MockFrame[];
  json: (DetectionMessage | ContactRecord)[];
}

function contact(over: Partial<ContactRecord>): ContactRecord {
  return {
    type: "contact",
    frame_id: 0,
    track_id: 1,
    lat: 30.215,
    lon: -88.52,
    r95_m: 30,
    actionability_class: "SWEEP",
    semi_major_m: 28,
    semi_minor_m: 16,
    orientation_deg: 40,
    priority_tier: "candidate",
    convergence_state: "CONVERGING",
    heading_limited: false,
    aspect_spread_deg: 35,
    detection_conf: 0.85,
    localization_conf: 0.6,
    mc_reject_fraction: 0.03,
    moving_suspected: false,
    age_frames: 0,
    ...over,
  };
}

export function cannedMission(frameCount = 90): CannedMission {
  const frames: MockFrame[] = [];
  const json: (DetectionMessage | ContactRecord)[] = [];

  for (let fid = 0; fid < frameCount; fid++) {
    frames.push({ frame_id: fid, timestamp: fid / 30, jpeg: TINY_JPEG });

    // a detection box on most frames (one person centered-ish in the 960x540 frame)
    json.push({
      type: "detection",
      frame_id: fid,
      timestamp: fid / 30,
      boxes: fid % 7 === 6 ? [] : [{ box_xyxy: [440, 250, 480, 320], conf: 0.86, cls: "person" }],
    });

    // track 42 appears early and REFINES over time (PINPOINT, r95 tightening — eased glide)
    if (fid === 10) json.push(contact({ frame_id: fid, track_id: 42, lat: 30.2168, lon: -88.5205, r95_m: 55, actionability_class: "SWEEP" }));
    if (fid === 40) json.push(contact({ frame_id: fid, track_id: 42, lat: 30.2169, lon: -88.5206, r95_m: 28, actionability_class: "PINPOINT", priority_tier: "strong", convergence_state: "STABLE", localization_conf: 0.78 }));

    // track 37 — a SWEEP-grade contact
    if (fid === 25) json.push(contact({ frame_id: fid, track_id: 37, lat: 30.2138, lon: -88.5175, r95_m: 70 }));

    // track 19 — a CUE_ONLY (no fix) contact: heading-limited, big honest uncertainty
    if (fid === 55) json.push(contact({ frame_id: fid, track_id: 19, lat: null, lon: null, r95_m: 0, actionability_class: "CUE_ONLY", heading_limited: true, localization_conf: 0.2 }));
  }

  return { frames, json };
}
