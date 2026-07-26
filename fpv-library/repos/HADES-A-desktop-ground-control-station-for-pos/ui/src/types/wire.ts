/* Wire types — the UI mirror of the Python service's WS schema
 * (service/src/hades/ws/schema.py). Two localhost channels aligned by `frame_id`:
 * a binary JPEG channel and this JSON channel (DetectionMessage + ContactRecord).
 *
 * These are the contract; if the Python schema changes, this changes with it. Coordinate
 * convention (DESIGN.md §3.1): (lat, lon) degrees WGS84; lat/lon are null for a CUE_ONLY
 * contact with no fused fix (a hard 0,0 would plot at Null Island as a false survivor). */

export type ActionabilityClass = "PINPOINT" | "SWEEP" | "AREA" | "CUE_ONLY";
export type PriorityTier = "contact" | "candidate" | "strong";
export type ConvergenceState = "CONVERGING" | "STABLE";

/** One detected box on the wire (mirrors BoxMessage / detect.Detection, DESIGN.md §3.2).
 *  box_xyxy = (x_min, y_min, x_max, y_max) in ORIGINAL (pre-letterbox) frame pixels. */
export interface BoxMessage {
  box_xyxy: [number, number, number, number];
  conf: number; // [0, 1]
  cls: string; // "person" in v1
}

/** Per-frame detections on the JSON channel, aligned to video by `frame_id`. */
export interface DetectionMessage {
  type: "detection";
  frame_id: number;
  timestamp: number; // frame presentation time, seconds
  boxes: BoxMessage[];
}

/** A taskable, localized contact (mirrors ws.schema.ContactRecord, Task 4.6).
 *  `detection_conf` and `localization_conf` are SEPARATE axes (never merge — the gap is a
 *  trust field). `r95_m` is the honest equal-coverage sweep radius (the empirical MC
 *  quantile, NOT the major semi-axis); the ellipse is the expert overlay. */
export interface ContactRecord {
  type: "contact";
  frame_id: number;
  track_id: number;

  // (lat, lon) degrees WGS84; null for a CUE_ONLY contact with no fused coordinate.
  lat: number | null;
  lon: number | null;

  r95_m: number;
  actionability_class: ActionabilityClass;
  semi_major_m: number;
  semi_minor_m: number;
  orientation_deg: number;

  priority_tier: PriorityTier;
  convergence_state: ConvergenceState;
  heading_limited: boolean;
  aspect_spread_deg: number;

  detection_conf: number; // [0, 1]
  localization_conf: number; // [0, 1]

  mc_reject_fraction: number; // [0, 1]
  moving_suspected: boolean;
  age_frames: number;
}

/** Any message arriving on the JSON channel. */
export type JsonMessage = DetectionMessage | ContactRecord;
