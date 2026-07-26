/**
 * Host-prop contract for the `video.overlay` slot.
 *
 * The cockpit pushes one `VideoOverlayHostProps` payload to each mounted
 * overlay iframe as a non-gated bridge event (`video.overlay.props`). The
 * payload carries everything an overlay needs to draw in the video's own
 * coordinate space and to map a click back to a frame pixel: the rendered
 * (letterbox-corrected) video rect, the stream resolution, the latest
 * attitude, and the latest detection batch.
 *
 * Cadence: pushed at DETECTION rate (when a new batch lands), not video rate.
 * Geometry is re-pushed only on resize / resolution change. When no batch has
 * arrived within the staleness window the host pushes `detections: null` so
 * overlays drop their boxes.
 *
 * @module plugins/video-overlay-props
 * @license GPL-3.0-only
 */

/** The non-gated bridge event method overlay host-props ride. */
export const VIDEO_OVERLAY_PROPS_EVENT = "video.overlay.props";

/** Capability tag carried on the event (events are not gated; this is the
 * slot's capability so an overlay can sanity-check the source). */
export const VIDEO_OVERLAY_PROPS_CAPABILITY = "ui.slot.video-overlay";

/** The letterbox-corrected rendered video rect, in CSS px relative to the
 * overlay wrapper's top-left. */
export interface RenderedRect {
  left: number;
  top: number;
  width: number;
  height: number;
}

/** One detection mapped into the host-props shape (a plain serializable
 * subset of the store's VisionDetection). */
export interface VideoOverlayDetectionItem {
  bbox: { x: number; y: number; width: number; height: number };
  classLabel: string;
  confidence: number;
  trackId: number | null;
  lockState: "locked" | "uncertain" | "lost" | null;
}

/** The detection batch carried on the host props, or null when stale/absent. */
export interface VideoOverlayDetections {
  frameWidth: number;
  frameHeight: number;
  frameId: number;
  receivedAt: number;
  items: VideoOverlayDetectionItem[];
}

/** Host props pushed to a `video.overlay` iframe. */
export interface VideoOverlayHostProps {
  droneId: string;
  cameraId: string;
  /** Stream resolution (intrinsic video dimensions). */
  streamWidth: number;
  streamHeight: number;
  /** Letterbox-corrected rendered rect (CSS px, relative to wrapper). */
  renderedRect: RenderedRect;
  /** Timestamp (ms) of the frame the detections/attitude are coalesced to. */
  frameTimestampMs: number;
  attitude: { rollDeg: number; pitchDeg: number; yawDeg: number };
  detections: VideoOverlayDetections | null;
}
