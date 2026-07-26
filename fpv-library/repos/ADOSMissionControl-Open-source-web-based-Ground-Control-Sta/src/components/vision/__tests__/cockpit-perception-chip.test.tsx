import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { CockpitPerceptionChip } from "@/components/vision/CockpitPerceptionChip";
import { useAgentCapabilitiesStore } from "@/stores/agent-capabilities-store";
import { useVisionDetectionsStore } from "@/stores/vision-detections-store";

const DRONE = "node:d1";

/** Seed one detection batch aged `ageMs` in the past (0 = fresh, >2000 = stale). */
function seedBatch(ageMs: number) {
  useVisionDetectionsStore.setState({
    batches: {
      [DRONE]: {
        cameraId: "uvc-0",
        frameId: 1,
        frameWidth: 640,
        frameHeight: 480,
        receivedAt: Date.now() - ageMs,
        detections: [],
      },
    },
  } as never);
}

function chip(): HTMLElement | null {
  return document.querySelector('[data-cockpit-widget="perception-health"]');
}

describe("CockpitPerceptionChip", () => {
  beforeEach(() => {
    useVisionDetectionsStore.setState({ batches: {} } as never);
    useAgentCapabilitiesStore.setState({
      perceptionTier: undefined,
      perceptionOffloadTarget: undefined,
    });
  });
  afterEach(cleanup);

  it("renders nothing when there is no feed and no running tier", () => {
    render(<CockpitPerceptionChip droneId={DRONE} />);
    expect(chip()).toBeNull();
  });

  it("shows LOCAL with a fresh feed dot when a batch is flowing", () => {
    seedBatch(0);
    useAgentCapabilitiesStore.setState({ perceptionTier: "local" });
    render(<CockpitPerceptionChip droneId={DRONE} />);
    const el = chip();
    expect(el).not.toBeNull();
    expect(el!.getAttribute("data-feed-state")).toBe("fresh");
    expect(el!.className).toContain("fresh");
    expect(screen.getByText("LOCAL")).toBeTruthy();
  });

  it("shows OFFLOAD with the workstation target when offloading", () => {
    seedBatch(0);
    useAgentCapabilitiesStore.setState({
      perceptionTier: "offload",
      perceptionOffloadTarget: "forge-1.local:8092",
    });
    render(<CockpitPerceptionChip droneId={DRONE} />);
    expect(screen.getByText("OFFLOAD")).toBeTruthy();
    expect(screen.getByText(/forge-1\.local:8092/)).toBeTruthy();
  });

  it("escalates a LIVE feed that went stale to 'Perception feed stale' (warn)", () => {
    seedBatch(5000);
    useAgentCapabilitiesStore.setState({ perceptionTier: "local" });
    render(<CockpitPerceptionChip droneId={DRONE} />);
    const el = chip();
    expect(el!.getAttribute("data-feed-state")).toBe("stale");
    expect(el!.className).toContain("warn");
    expect(screen.getByText("Perception feed stale")).toBeTruthy();
  });

  it("escalates a stale OFFLOAD feed to 'Offload link lost' (crit)", () => {
    seedBatch(5000);
    useAgentCapabilitiesStore.setState({ perceptionTier: "offload" });
    render(<CockpitPerceptionChip droneId={DRONE} />);
    const el = chip();
    expect(el!.className).toContain("crit");
    expect(screen.getByText("Offload link lost")).toBeTruthy();
  });

  it("shows an idle (grey, no reason) chip when a tier is set but no feed started", () => {
    useAgentCapabilitiesStore.setState({ perceptionTier: "local" });
    render(<CockpitPerceptionChip droneId={DRONE} />);
    const el = chip();
    expect(el).not.toBeNull();
    expect(el!.getAttribute("data-feed-state")).toBe("idle");
    // No stale escalation when a feed never started (that is "no detections yet").
    expect(screen.queryByText("Perception feed stale")).toBeNull();
    expect(screen.getByText("LOCAL")).toBeTruthy();
  });
});
