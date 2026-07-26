/* Overlay freshness classification (DESIGN-SYSTEM §7.5). The cardinal video rule: a frozen
 * frame must NEVER look live. LINK_LOST dominates everything (the feed is dead → loud
 * banner, dimmed frame). Otherwise FRESH means the box is for the frame on screen; COASTING
 * means the tracker is bridging between detections (box older than the displayed frame, or
 * no current detection) — rendered distinctly so the operator knows it's interpolated. */

export type Freshness = "LINK_LOST" | "FRESH" | "COASTING";

export interface FreshnessInput {
  linkUp: boolean;
  displayedFrameId: number;
  detectionFrameId: number | null;
}

export function overlayFreshness({ linkUp, displayedFrameId, detectionFrameId }: FreshnessInput): Freshness {
  if (!linkUp) return "LINK_LOST";
  if (detectionFrameId !== null && detectionFrameId === displayedFrameId) return "FRESH";
  return "COASTING";
}
