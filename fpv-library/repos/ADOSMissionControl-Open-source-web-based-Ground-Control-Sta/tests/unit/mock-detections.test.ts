/**
 * Tests for the demo-mode synthetic vision-detection generator: it pushes
 * well-formed, in-frame, tracked detection batches into the vision-detections
 * store at inference cadence, retargets onto a new drone, exercises the
 * lock-state ramp over time, and cleans up on stop.
 *
 * @license GPL-3.0-only
 */

import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { mockDetectionStream } from "@/mock/mock-detections";
import { useVisionDetectionsStore } from "@/stores/vision-detections-store";

describe("mock detection stream", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    useVisionDetectionsStore.getState().clear();
  });

  afterEach(() => {
    mockDetectionStream.stop();
    vi.useRealTimers();
  });

  it("pushes a batch for the target drone on the first tick", () => {
    mockDetectionStream.start("drone-1");
    vi.advanceTimersByTime(100);
    const batch = useVisionDetectionsStore.getState().batches["drone-1"];
    expect(batch).toBeDefined();
    expect(batch.frameWidth).toBe(640);
    expect(batch.frameHeight).toBe(480);
    expect(batch.detections.length).toBeGreaterThanOrEqual(1);
    expect(batch.detections.length).toBeLessThanOrEqual(3);
  });

  it("produces tracked, in-frame person boxes with a lock state", () => {
    mockDetectionStream.start("drone-1");
    vi.advanceTimersByTime(100);
    const batch = useVisionDetectionsStore.getState().batches["drone-1"];
    for (const d of batch.detections) {
      expect(d.classLabel).toBe("person");
      expect(typeof d.trackId).toBe("number");
      expect(["locked", "uncertain", "lost"]).toContain(d.lockState);
      // Box stays inside the frame (the mock always emits a box).
      expect(d.bbox).toBeDefined();
      if (!d.bbox) continue;
      expect(d.bbox.x).toBeGreaterThanOrEqual(0);
      expect(d.bbox.y).toBeGreaterThanOrEqual(0);
      expect(d.bbox.x + d.bbox.width).toBeLessThanOrEqual(640);
      expect(d.bbox.y + d.bbox.height).toBeLessThanOrEqual(480);
      expect(d.confidence).toBeGreaterThan(0);
      expect(d.confidence).toBeLessThanOrEqual(1);
    }
  });

  it("advances the frame id across ticks", () => {
    mockDetectionStream.start("drone-1");
    vi.advanceTimersByTime(100);
    const first = useVisionDetectionsStore.getState().batches["drone-1"].frameId;
    vi.advanceTimersByTime(100);
    const second =
      useVisionDetectionsStore.getState().batches["drone-1"].frameId;
    expect(second).toBeGreaterThan(first);
  });

  it("boxes drift between ticks (the track moves)", () => {
    mockDetectionStream.start("drone-1");
    vi.advanceTimersByTime(100);
    const a = useVisionDetectionsStore.getState().batches["drone-1"]
      .detections[0].bbox;
    vi.advanceTimersByTime(2000); // skip ahead enough for a visible move
    const b = useVisionDetectionsStore.getState().batches["drone-1"]
      .detections[0].bbox;
    expect(a).toBeDefined();
    expect(b).toBeDefined();
    expect(a?.x !== b?.x || a?.y !== b?.y).toBe(true);
  });

  it("retargets onto a new drone and stops feeding the old one", () => {
    mockDetectionStream.start("drone-1");
    vi.advanceTimersByTime(100);
    expect(useVisionDetectionsStore.getState().batches["drone-1"]).toBeDefined();

    mockDetectionStream.start("drone-2");
    vi.advanceTimersByTime(100);
    // The previous drone's batch is cleared on retarget.
    expect(
      useVisionDetectionsStore.getState().batches["drone-1"],
    ).toBeUndefined();
    expect(useVisionDetectionsStore.getState().batches["drone-2"]).toBeDefined();
  });

  it("clears the batch and stops ticking on stop()", () => {
    mockDetectionStream.start("drone-1");
    vi.advanceTimersByTime(100);
    mockDetectionStream.stop();
    expect(
      useVisionDetectionsStore.getState().batches["drone-1"],
    ).toBeUndefined();
    expect(mockDetectionStream.isRunning()).toBe(false);

    // No further batches after stop.
    vi.advanceTimersByTime(500);
    expect(
      useVisionDetectionsStore.getState().batches["drone-1"],
    ).toBeUndefined();
  });

  it("cycles the lock state over a full period", () => {
    mockDetectionStream.start("drone-1");
    const seen = new Set<string>();
    // ~7s lock cycle; sample across 8s.
    for (let i = 0; i < 80; i++) {
      vi.advanceTimersByTime(100);
      const batch = useVisionDetectionsStore.getState().batches["drone-1"];
      for (const d of batch.detections) {
        if (d.lockState) seen.add(d.lockState);
      }
    }
    // Over a full cycle the ramp exercises at least locked + uncertain.
    expect(seen.has("locked")).toBe(true);
    expect(seen.size).toBeGreaterThanOrEqual(2);
  });
});
