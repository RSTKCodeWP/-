import { describe, expect, it, vi } from "vitest";

import type { ContactRecord, DetectionMessage } from "../types/wire";
import { MockWsServer, type MockFrame } from "./mock-ws";

/** A tiny canned mission: 3 frames, each with a JPEG blob + a detection, plus one contact. */
function cannedMission(): {
  frames: MockFrame[];
  json: (DetectionMessage | ContactRecord)[];
} {
  const frames: MockFrame[] = [0, 1, 2].map((frame_id) => ({
    frame_id,
    timestamp: frame_id / 30,
    // a stand-in for JPEG bytes — the panel only needs *bytes aligned by frame_id*
    jpeg: new Uint8Array([0xff, 0xd8, frame_id]),
  }));
  const json: (DetectionMessage | ContactRecord)[] = [
    { type: "detection", frame_id: 0, timestamp: 0, boxes: [{ box_xyxy: [1, 2, 3, 4], conf: 0.9, cls: "person" }] },
    { type: "detection", frame_id: 1, timestamp: 1 / 30, boxes: [] },
    {
      type: "contact",
      frame_id: 2,
      track_id: 42,
      lat: 30.21,
      lon: -88.52,
      r95_m: 18,
      actionability_class: "PINPOINT",
      semi_major_m: 22,
      semi_minor_m: 14,
      orientation_deg: 30,
      priority_tier: "strong",
      convergence_state: "STABLE",
      heading_limited: false,
      aspect_spread_deg: 40,
      detection_conf: 0.94,
      localization_conf: 0.71,
      mc_reject_fraction: 0.02,
      moving_suspected: false,
      age_frames: 3,
    },
  ];
  return { frames, json };
}

describe("MockWsServer", () => {
  it("emits canned JSON messages to the json-channel subscriber", async () => {
    const { frames, json } = cannedMission();
    const server = new MockWsServer({ frames, json, intervalMs: 0 });
    const seen: (DetectionMessage | ContactRecord)[] = [];
    server.onJson((m) => seen.push(m));

    await server.play();

    expect(seen).toHaveLength(3);
    expect(seen.filter((m) => m.type === "contact")).toHaveLength(1);
    expect(seen.find((m) => m.type === "contact")).toMatchObject({ track_id: 42 });
  });

  it("emits canned frames (binary channel) so the video panel has something to paint", async () => {
    const { frames, json } = cannedMission();
    const server = new MockWsServer({ frames, json, intervalMs: 0 });
    const painted: MockFrame[] = [];
    server.onFrame((f) => painted.push(f));

    await server.play();

    expect(painted).toHaveLength(3);
    expect(painted[0].jpeg).toBeInstanceOf(Uint8Array);
    expect(painted[2].frame_id).toBe(2);
  });

  it("keeps both channels aligned by frame_id (the cross-channel join key)", async () => {
    const { frames, json } = cannedMission();
    const server = new MockWsServer({ frames, json, intervalMs: 0 });
    const frameIds: number[] = [];
    const jsonIds: number[] = [];
    server.onFrame((f) => frameIds.push(f.frame_id));
    server.onJson((m) => jsonIds.push(m.frame_id));

    await server.play();

    // every JSON message's frame_id corresponds to an emitted frame
    expect(new Set(frameIds)).toEqual(new Set([0, 1, 2]));
    expect(jsonIds.every((id) => frameIds.includes(id))).toBe(true);
  });

  it("supports unsubscribe (no leak after a listener detaches)", async () => {
    const { frames, json } = cannedMission();
    const server = new MockWsServer({ frames, json, intervalMs: 0 });
    const cb = vi.fn();
    const off = server.onJson(cb);
    off();

    await server.play();

    expect(cb).not.toHaveBeenCalled();
  });

  it("stop() halts emission partway through", async () => {
    const { frames, json } = cannedMission();
    const server = new MockWsServer({ frames, json, intervalMs: 10 });
    const seen: number[] = [];
    server.onFrame((f) => {
      seen.push(f.frame_id);
      if (f.frame_id === 0) server.stop();
    });

    await server.play();

    expect(seen).toEqual([0]); // stopped after the first frame
  });
});
