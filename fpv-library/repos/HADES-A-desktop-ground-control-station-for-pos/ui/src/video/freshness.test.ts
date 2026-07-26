import { describe, expect, it } from "vitest";

import { overlayFreshness } from "./freshness";

/* Fresh vs coasting vs link-lost overlay state (DESIGN-SYSTEM §7.5). A frozen frame must
 * NEVER look live: if the link is down → LINK_LOST; if the detection's frame_id matches the
 * displayed frame → FRESH; if we're showing a box older than the displayed frame (tracker
 * coasting between detections) → COASTING. */

describe("overlayFreshness", () => {
  it("LINK_LOST when the link is down (frozen frame, never looks live)", () => {
    expect(overlayFreshness({ linkUp: false, displayedFrameId: 10, detectionFrameId: 10 })).toBe("LINK_LOST");
  });

  it("FRESH when the detection is for the displayed frame", () => {
    expect(overlayFreshness({ linkUp: true, displayedFrameId: 10, detectionFrameId: 10 })).toBe("FRESH");
  });

  it("COASTING when the displayed frame is newer than the detection (tracker bridging)", () => {
    expect(overlayFreshness({ linkUp: true, displayedFrameId: 12, detectionFrameId: 10 })).toBe("COASTING");
  });

  it("COASTING when there is no current detection at all", () => {
    expect(overlayFreshness({ linkUp: true, displayedFrameId: 12, detectionFrameId: null })).toBe("COASTING");
  });

  it("link-lost dominates even if frame ids happen to match", () => {
    expect(overlayFreshness({ linkUp: false, displayedFrameId: 7, detectionFrameId: 7 })).toBe("LINK_LOST");
  });
});
