import { cleanup, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { useVisionPipelines } from "@/hooks/use-vision-pipelines";
import {
  useVisionDetectionsStore,
  type VisionDetection,
} from "@/stores/vision-detections-store";

const DRONE = "node:d1";

function seed(modelId: string, cameraId: string, detections: VisionDetection[] = []) {
  useVisionDetectionsStore.getState().setBatch(DRONE, {
    modelId,
    cameraId,
    frameId: 1,
    tsMs: 0,
    frameWidth: 1280,
    frameHeight: 720,
    detections,
  });
}

describe("useVisionPipelines", () => {
  beforeEach(() => useVisionDetectionsStore.getState().clear());
  afterEach(cleanup);

  it("returns nothing when no streams are flowing", () => {
    const { result } = renderHook(() => useVisionPipelines(DRONE));
    expect(result.current).toEqual([]);
  });

  it("shows one pipeline per (model, camera) stream, active + counting", () => {
    seed("person", "uvc-0", [
      { bbox: { x: 0, y: 0, width: 1, height: 1 }, classLabel: "person", confidence: 0.9, trackId: 7, lockState: "locked" },
      { bbox: { x: 0, y: 0, width: 1, height: 1 }, classLabel: "person", confidence: 0.6 },
    ]);
    seed("depth", "uvc-0", []);
    const { result } = renderHook(() => useVisionPipelines(DRONE));
    expect(result.current).toHaveLength(2);
    const person = result.current.find((p) => p.modelId === "person")!;
    expect(person.detectionCount).toBe(2);
    expect(person.lockedCount).toBe(1);
    expect(person.active).toBe(true);
    expect(person.cameraId).toBe("uvc-0");
  });

  it("keys are stable and sorted", () => {
    seed("zebra", "uvc-1");
    seed("alpha", "uvc-0");
    const { result } = renderHook(() => useVisionPipelines(DRONE));
    expect(result.current.map((p) => p.modelId)).toEqual(["alpha", "zebra"]);
  });
});
