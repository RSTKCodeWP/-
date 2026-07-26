import { describe, expect, it, beforeEach } from "vitest";
import { useVideoStore } from "@/stores/video-store";

/**
 * The frozen-stream watchdog raises a one-way stall edge that video
 * surfaces watch to re-fetch the offer. These tests pin the store
 * contract: the signal monotonically increments and the poll state
 * carries the progress timestamp the watchdog compares against.
 */
describe("video-store frozen-stream signal", () => {
  beforeEach(() => {
    useVideoStore.setState({ videoStallSignal: 0 });
    useVideoStore.getState().resetPollState();
  });

  it("starts at zero", () => {
    expect(useVideoStore.getState().videoStallSignal).toBe(0);
  });

  it("monotonically increments on each stall", () => {
    const before = useVideoStore.getState().videoStallSignal;
    useVideoStore.getState().signalVideoStall();
    useVideoStore.getState().signalVideoStall();
    expect(useVideoStore.getState().videoStallSignal).toBe(before + 2);
  });

  it("tracks lastProgressTime in poll state", () => {
    const ts = Date.now();
    useVideoStore.getState().setPollState({ lastProgressTime: ts });
    expect(useVideoStore.getState()._pollState.lastProgressTime).toBe(ts);
  });

  it("resetPollState clears the progress timestamp", () => {
    useVideoStore.getState().setPollState({ lastProgressTime: 12345 });
    useVideoStore.getState().resetPollState();
    expect(useVideoStore.getState()._pollState.lastProgressTime).toBe(0);
  });
});
