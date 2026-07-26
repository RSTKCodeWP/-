import { beforeEach, describe, expect, it } from "vitest";

import {
  streamKey,
  useVisionDetectionsStore,
  type VisionDetectionBatch,
} from "@/stores/vision-detections-store";

function batch(
  over: Partial<Omit<VisionDetectionBatch, "receivedAt">>,
): Omit<VisionDetectionBatch, "receivedAt"> {
  return {
    modelId: "coco",
    cameraId: "uvc-0",
    frameId: 1,
    tsMs: 0,
    frameWidth: 1280,
    frameHeight: 720,
    detections: [],
    ...over,
  };
}

const DRONE = "node:d1";

describe("vision-detections-store stream keying", () => {
  beforeEach(() => useVisionDetectionsStore.getState().clear());

  it("keeps a per-stream batch per (model, camera) without clobbering", () => {
    const s = useVisionDetectionsStore.getState();
    s.setBatch(DRONE, batch({ modelId: "person", cameraId: "uvc-0" }));
    s.setBatch(DRONE, batch({ modelId: "depth", cameraId: "uvc-0" }));
    // Two models -> two distinct streams (the second no longer overwrites the
    // first, the bug the re-key fixes).
    const streams = useVisionDetectionsStore.getState().streamsForDrone(DRONE);
    expect(streams).toHaveLength(2);
    const models = streams.map((b) => b.modelId).sort();
    expect(models).toEqual(["depth", "person"]);
  });

  it("splits streams by camera too", () => {
    const s = useVisionDetectionsStore.getState();
    s.setBatch(DRONE, batch({ modelId: "person", cameraId: "uvc-0" }));
    s.setBatch(DRONE, batch({ modelId: "person", cameraId: "uvc-1" }));
    expect(useVisionDetectionsStore.getState().streamsForDrone(DRONE)).toHaveLength(2);
  });

  it("a re-published stream replaces only its own key", () => {
    const s = useVisionDetectionsStore.getState();
    s.setBatch(DRONE, batch({ modelId: "person", frameId: 1 }));
    s.setBatch(DRONE, batch({ modelId: "person", frameId: 2 }));
    const streams = useVisionDetectionsStore.getState().streamsForDrone(DRONE);
    expect(streams).toHaveLength(1);
    expect(streams[0].frameId).toBe(2);
  });

  it("still exposes the latest-across-streams batch for the cockpit", () => {
    const s = useVisionDetectionsStore.getState();
    s.setBatch(DRONE, batch({ modelId: "person" }));
    s.setBatch(DRONE, batch({ modelId: "depth" }));
    // The simple per-drone `batches` view is the most-recent batch.
    expect(useVisionDetectionsStore.getState().batches[DRONE].modelId).toBe("depth");
  });

  it("clearBatch drops both the latest and the streams", () => {
    const s = useVisionDetectionsStore.getState();
    s.setBatch(DRONE, batch({ modelId: "person" }));
    s.clearBatch(DRONE);
    const st = useVisionDetectionsStore.getState();
    expect(st.batches[DRONE]).toBeUndefined();
    expect(st.streamsForDrone(DRONE)).toEqual([]);
  });

  it("streamKey is model::camera", () => {
    expect(streamKey("person", "uvc-0")).toBe("person::uvc-0");
  });
});
