/**
 * @module vision-detections-mqtt.test
 * @description Tests the cloud-relay detection path: a JSON detection batch on
 * the `ados/{deviceId}/vision/detections` MQTT topic parses via
 * `parseWireDetectionJson` and routes into the SAME `setBatch` seam the LAN
 * WebSocket feeds, and malformed payloads are dropped (never thrown).
 * @license GPL-3.0-only
 */

import { beforeEach, describe, expect, it } from "vitest";

import { parseWireDetectionJson } from "@/lib/agent/vision-detections-ws";
import { useVisionDetectionsStore } from "@/stores/vision-detections-store";

const DEVICE = "charlie-3";

/** A detection batch as the agent forwards it (contract snake_case) — the
 * exact shape the LAN WebSocket already parses, so the cloud path maps
 * identically. */
const WIRE = JSON.stringify({
  model_id: "yolov8n",
  camera_id: "cam-0",
  frame_id: 42,
  ts_ms: 123456,
  frame_width: 1280,
  frame_height: 720,
  detections: [
    {
      bbox: { x: 10, y: 20, width: 30, height: 40 },
      class_label: "person",
      confidence: 0.9,
      track_id: 7,
      lock_state: "locked",
    },
  ],
});

describe("parseWireDetectionJson", () => {
  it("maps the contract snake_case JSON onto the store's camelCase batch", () => {
    const batch = parseWireDetectionJson(WIRE);
    expect(batch).not.toBeNull();
    expect(batch!.modelId).toBe("yolov8n");
    expect(batch!.cameraId).toBe("cam-0");
    expect(batch!.frameId).toBe(42);
    expect(batch!.tsMs).toBe(123456);
    expect(batch!.frameWidth).toBe(1280);
    expect(batch!.frameHeight).toBe(720);
    expect(batch!.detections).toHaveLength(1);
    const d = batch!.detections[0]!;
    expect(d.classLabel).toBe("person");
    expect(d.trackId).toBe(7);
    expect(d.lockState).toBe("locked");
    expect(d.bbox).toEqual({ x: 10, y: 20, width: 30, height: 40 });
  });

  it("drops malformed / non-object payloads (returns null, never throws)", () => {
    expect(parseWireDetectionJson("not json {")).toBeNull();
    expect(parseWireDetectionJson("[1,2,3]")).toBeNull();
    expect(parseWireDetectionJson("42")).toBeNull();
    expect(parseWireDetectionJson("null")).toBeNull();
  });
});

describe("cloud-relay detection routing", () => {
  beforeEach(() => {
    useVisionDetectionsStore.getState().clear();
  });

  it("routes a parsed batch into setBatch under the device id", () => {
    const batch = parseWireDetectionJson(WIRE);
    expect(batch).not.toBeNull();
    // This is exactly what MqttBridge does on a vision/detections message.
    useVisionDetectionsStore.getState().setBatch(DEVICE, batch!);

    const stored = useVisionDetectionsStore.getState().batches[DEVICE];
    expect(stored).toBeDefined();
    expect(stored!.modelId).toBe("yolov8n");
    expect(stored!.detections[0]!.classLabel).toBe("person");
    expect(typeof stored!.receivedAt).toBe("number");
    // And the receipt window (throughput source) picked it up.
    expect(
      useVisionDetectionsStore.getState().receiptTimes(DEVICE),
    ).toHaveLength(1);
  });
});
