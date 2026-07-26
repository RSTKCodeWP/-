import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { WhatsLockedChip } from "@/components/vision/WhatsLockedChip";
import { useAgentCapabilitiesStore } from "@/stores/agent-capabilities-store";
import { useSelectedTargetStore } from "@/stores/selected-target-store";
import { useVisionDetectionsStore } from "@/stores/vision-detections-store";

const DRONE = "node:d1";

function seedBatch(
  trackId: number,
  lockState: "locked" | "uncertain" | "lost",
  ageMs = 0,
) {
  useVisionDetectionsStore.setState({
    batches: {
      [DRONE]: {
        cameraId: "uvc-0",
        frameId: 1,
        frameWidth: 1280,
        frameHeight: 720,
        receivedAt: Date.now() - ageMs,
        detections: [
          {
            bbox: { x: 0, y: 0, width: 10, height: 10 },
            classLabel: "person",
            confidence: 0.8,
            trackId,
            lockState,
          },
        ],
      },
    },
  } as never);
}

function selectTrack7(classLabel = "person") {
  useSelectedTargetStore.setState({
    selected: {
      droneId: DRONE,
      cameraId: "uvc-0",
      trackId: 7,
      bbox: { x: 0, y: 0, width: 10, height: 10 },
      classLabel,
      confidence: 0.5,
    },
  });
}

describe("WhatsLockedChip", () => {
  beforeEach(() => {
    useSelectedTargetStore.setState({ selected: null });
    useVisionDetectionsStore.setState({ batches: {} } as never);
    useAgentCapabilitiesStore.setState({
      perceptionTier: undefined,
      perceptionOffloadTarget: undefined,
    });
  });
  afterEach(cleanup);

  it("renders nothing when no target is selected", () => {
    const { container } = render(<WhatsLockedChip droneId={DRONE} />);
    expect(container.firstChild).toBeNull();
  });

  it("renders nothing when the selection is for another drone", () => {
    useSelectedTargetStore.setState({
      selected: {
        droneId: "node:other",
        cameraId: "uvc-0",
        trackId: 7,
        bbox: { x: 0, y: 0, width: 10, height: 10 },
        classLabel: "person",
        confidence: 0.9,
      },
    });
    const { container } = render(<WhatsLockedChip droneId={DRONE} />);
    expect(container.firstChild).toBeNull();
  });

  it("shows the class, track id and LIVE lock state for the selection", () => {
    seedBatch(7, "locked");
    selectTrack7();
    render(<WhatsLockedChip droneId={DRONE} />);
    expect(screen.getByText(/person · trk 7/)).toBeTruthy();
    expect(screen.getByText("Locked")).toBeTruthy();
    // Confidence comes from the LIVE detection (0.8), not the stale selection.
    expect(screen.getByText("80%")).toBeTruthy();
  });

  it("reflects a changed live lock state (uncertain)", () => {
    seedBatch(7, "uncertain");
    selectTrack7("car");
    render(<WhatsLockedChip droneId={DRONE} />);
    expect(screen.getByText("Uncertain")).toBeTruthy();
  });

  it("shows the tracker's Lost state while the feed is still FRESH", () => {
    // Feed is live (age 0), the tracker itself could not re-associate the target.
    seedBatch(7, "lost", 0);
    selectTrack7();
    render(<WhatsLockedChip droneId={DRONE} />);
    expect(screen.getByText("Lost")).toBeTruthy();
  });

  it("shows 'Perception feed stale' (not a tracker Lost) when a live feed went stale", () => {
    // The batch WAS flowing but has aged out — we can no longer see, so the
    // honest reason is a stale feed, NOT the tracker losing the target.
    seedBatch(7, "locked", 5000);
    selectTrack7();
    render(<WhatsLockedChip droneId={DRONE} />);
    expect(screen.getByText("Perception feed stale")).toBeTruthy();
    expect(screen.queryByText("Locked")).toBeNull();
  });

  it("shows 'Offload link lost' when a stale feed was running on the offload tier", () => {
    useAgentCapabilitiesStore.setState({ perceptionTier: "offload" });
    seedBatch(7, "locked", 5000);
    selectTrack7();
    render(<WhatsLockedChip droneId={DRONE} />);
    expect(screen.getByText("Offload link lost")).toBeTruthy();
  });
});
