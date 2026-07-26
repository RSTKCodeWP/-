/**
 * Locks the kinematic ViewerTrack wrapper's pass-through contract: it must attach the
 * tier + flags without transforming the sampled properties, so the primary track stays
 * byte-identical to the prior single-path rendering.
 * @license GPL-3.0-only
 */
import { describe, it, expect } from "vitest";
import { makeKinematicViewerTrack } from "@/lib/simulation/viewer-track";
import type { SampledProperties } from "@/lib/build-sampled-properties";

// A minimal stand-in for the Cesium-backed SampledProperties. The wrapper never reads
// into it, so an opaque token object is enough to assert reference pass-through.
const sampledStub = { sampledPosition: {}, sampledHeading: {}, startJulian: {} } as unknown as SampledProperties;

describe("makeKinematicViewerTrack", () => {
  it("passes the sampled properties through unchanged (same reference)", () => {
    const track = makeKinematicViewerTrack(sampledStub, true, false);
    expect(track.sampled).toBe(sampledStub);
    expect(track.id).toBe("kinematic");
    expect(track.sourceTier).toBe("kinematic");
    expect(track.useAbsoluteAlt).toBe(true);
    expect(track.visible).toBe(false);
  });

  it("carries a null sampled (unresolved terrain) without inventing data", () => {
    const track = makeKinematicViewerTrack(null, false, true);
    expect(track.sampled).toBeNull();
    expect(track.useAbsoluteAlt).toBe(false);
    expect(track.visible).toBe(true);
  });
});
