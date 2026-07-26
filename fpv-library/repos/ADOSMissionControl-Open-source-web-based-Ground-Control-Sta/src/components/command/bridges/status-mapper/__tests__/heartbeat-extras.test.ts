/**
 * @license GPL-3.0-only
 *
 * A3 regression for buildHeartbeatExtras — the perception offload-target field.
 * The tier + offload target travel together on the wire, but the Rust beacon
 * OMITS the target (skip_serializing_if) when there is none. So when the tier IS
 * present but the target is absent, the drone stopped offloading and the target
 * must map to null (cleared), NOT undefined (keep-prior) — otherwise a card
 * keeps naming a stale workstation (Rule 44). An absent target with an ALSO
 * absent tier is a sparse tick and keeps prior (undefined).
 */

import { describe, it, expect } from "vitest";
import { buildHeartbeatExtras } from "../heartbeat-extras";

describe("buildHeartbeatExtras — perception offload target", () => {
  it("clears the target (null) when a later heartbeat sends a tier but no target", () => {
    // First heartbeat: offloading to a workstation.
    const first = buildHeartbeatExtras({
      perceptionTier: "offload",
      perceptionOffloadTarget: "workstation.local:8092",
    });
    expect(first.perceptionTier).toBe("offload");
    expect(first.perceptionOffloadTarget).toBe("workstation.local:8092");

    // Second heartbeat: back to local — the tier travels, the target field is
    // omitted. The mapped target must be null (cleared), not undefined.
    const second = buildHeartbeatExtras({ perceptionTier: "local" });
    expect(second.perceptionTier).toBe("local");
    expect(second.perceptionOffloadTarget).toBeNull();
  });

  it("keeps prior (undefined) when neither tier nor target is present", () => {
    const extras = buildHeartbeatExtras({ version: "1.0.0" });
    expect(extras.perceptionTier).toBeUndefined();
    expect(extras.perceptionOffloadTarget).toBeUndefined();
  });

  it("passes an explicit string target through", () => {
    const extras = buildHeartbeatExtras({
      perceptionTier: "offload",
      perceptionOffloadTarget: "10.0.0.5:8092",
    });
    expect(extras.perceptionOffloadTarget).toBe("10.0.0.5:8092");
  });

  it("passes an explicit null target through as cleared", () => {
    const extras = buildHeartbeatExtras({
      perceptionTier: "local",
      perceptionOffloadTarget: null,
    });
    expect(extras.perceptionOffloadTarget).toBeNull();
  });
});
