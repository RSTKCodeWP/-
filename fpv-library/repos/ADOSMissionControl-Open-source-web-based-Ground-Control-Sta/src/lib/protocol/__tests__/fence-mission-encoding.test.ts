/**
 * @module protocol/fence-mission-encoding.test
 * @description Unit tests for the PX4 fence-as-mission encoding: the
 * FenceElement -> NAV_FENCE_* mission-item flattening, the round-trip decode,
 * and the byte-level MISSION_ITEM_INT wire format carrying mission_type = fence.
 * @license GPL-3.0-only
 */

import { describe, it, expect } from "vitest";
import {
  encodeFenceMissionItems,
  decodeFenceMissionItems,
  MAV_CMD_NAV_FENCE_POLYGON_VERTEX_INCLUSION,
  MAV_CMD_NAV_FENCE_POLYGON_VERTEX_EXCLUSION,
  MAV_CMD_NAV_FENCE_CIRCLE_INCLUSION,
  MAV_CMD_NAV_FENCE_CIRCLE_EXCLUSION,
  type FenceMissionItem,
} from "../mavlink-adapter-missions";
import { encodeMissionItemInt, MAV_MISSION_TYPE_FENCE } from "../mavlink-encoder";
import { decodeMissionItemInt } from "../mavlink-messages";
import type { FenceElement } from "../types";
import { MockProtocol } from "@/mock/mock-protocol";

/** Extract the payload bytes from a built MAVLink v2 frame (len at byte 1). */
function payloadOf(frame: Uint8Array): DataView {
  const payloadLen = frame[1];
  const payload = frame.subarray(10, 10 + payloadLen);
  return new DataView(payload.buffer, payload.byteOffset, payload.byteLength);
}

describe("encodeFenceMissionItems", () => {
  it("emits one item per polygon vertex with param1 = vertex count on every vertex", () => {
    const el: FenceElement = {
      kind: "polygon",
      role: "inclusion",
      vertices: [
        { lat: 47.1, lon: 8.1 },
        { lat: 47.2, lon: 8.2 },
        { lat: 47.3, lon: 8.3 },
      ],
      group: 2,
    };
    const items = encodeFenceMissionItems([el]);

    expect(items).toHaveLength(3);
    for (const it of items) {
      expect(it.command).toBe(MAV_CMD_NAV_FENCE_POLYGON_VERTEX_INCLUSION);
      expect(it.param1).toBe(3); // total vertex count, identical on every vertex
      expect(it.param2).toBe(2); // inclusion group
    }
    // Sequence is a flat 0..N-1 index; lat/lon scaled to int32 * 1e7.
    expect(items.map((i) => i.seq)).toEqual([0, 1, 2]);
    expect(items[0].x).toBe(Math.round(47.1 * 1e7));
    expect(items[0].y).toBe(Math.round(8.1 * 1e7));
    expect(items[0].z).toBe(0); // altitude is Reserved for polygon vertices
  });

  it("uses the exclusion command and drops the group for an exclusion polygon", () => {
    const el: FenceElement = {
      kind: "polygon",
      role: "exclusion",
      vertices: [
        { lat: 10, lon: 20 },
        { lat: 11, lon: 21 },
        { lat: 12, lon: 22 },
      ],
      group: 5,
    };
    const items = encodeFenceMissionItems([el]);
    expect(items).toHaveLength(3);
    for (const it of items) {
      expect(it.command).toBe(MAV_CMD_NAV_FENCE_POLYGON_VERTEX_EXCLUSION);
      expect(it.param2).toBe(0); // exclusion carries no inclusion group
    }
  });

  it("encodes a circle as one item with param1 = radius", () => {
    const incl: FenceElement = {
      kind: "circle",
      role: "inclusion",
      center: { lat: 51.5, lon: -0.12 },
      radius: 250,
      group: 1,
    };
    const excl: FenceElement = {
      kind: "circle",
      role: "exclusion",
      center: { lat: 51.6, lon: -0.13 },
      radius: 40,
    };
    const items = encodeFenceMissionItems([incl, excl]);

    expect(items).toHaveLength(2);
    expect(items[0].command).toBe(MAV_CMD_NAV_FENCE_CIRCLE_INCLUSION);
    expect(items[0].param1).toBe(250);
    expect(items[0].param2).toBe(1);
    expect(items[0].x).toBe(Math.round(51.5 * 1e7));
    expect(items[0].y).toBe(Math.round(-0.12 * 1e7));
    expect(items[1].command).toBe(MAV_CMD_NAV_FENCE_CIRCLE_EXCLUSION);
    expect(items[1].param1).toBe(40);
    expect(items[1].param2).toBe(0);
  });

  it("skips a degenerate polygon (< 3 vertices) and keeps a flat seq across elements", () => {
    const elements: FenceElement[] = [
      { kind: "polygon", role: "inclusion", vertices: [{ lat: 1, lon: 1 }, { lat: 2, lon: 2 }] }, // dropped
      {
        kind: "polygon",
        role: "inclusion",
        vertices: [
          { lat: 3, lon: 3 },
          { lat: 4, lon: 4 },
          { lat: 5, lon: 5 },
        ],
      },
      { kind: "circle", role: "exclusion", center: { lat: 6, lon: 6 }, radius: 100 },
    ];
    const items = encodeFenceMissionItems(elements);

    // 3 polygon vertices + 1 circle = 4 items; the 2-vertex polygon is gone.
    expect(items.map((i) => i.seq)).toEqual([0, 1, 2, 3]);
    expect(items.slice(0, 3).every((i) => i.command === MAV_CMD_NAV_FENCE_POLYGON_VERTEX_INCLUSION)).toBe(true);
    expect(items[3].command).toBe(MAV_CMD_NAV_FENCE_CIRCLE_EXCLUSION);
  });
});

describe("decodeFenceMissionItems (round-trip)", () => {
  it("reassembles polygons by vertex count and keeps circles standalone", () => {
    const original: FenceElement[] = [
      {
        kind: "polygon",
        role: "inclusion",
        vertices: [
          { lat: 47.1, lon: 8.1 },
          { lat: 47.2, lon: 8.2 },
          { lat: 47.3, lon: 8.3 },
          { lat: 47.4, lon: 8.4 },
        ],
        group: 0,
      },
      {
        kind: "polygon",
        role: "exclusion",
        vertices: [
          { lat: 40, lon: 5 },
          { lat: 41, lon: 6 },
          { lat: 42, lon: 7 },
        ],
      },
      { kind: "circle", role: "inclusion", center: { lat: 51.5, lon: -0.1 }, radius: 300, group: 0 },
    ];
    const decoded = decodeFenceMissionItems(encodeFenceMissionItems(original));

    expect(decoded).toHaveLength(3);

    const poly0 = decoded[0];
    expect(poly0.kind).toBe("polygon");
    expect(poly0.role).toBe("inclusion");
    if (poly0.kind === "polygon") {
      expect(poly0.vertices).toHaveLength(4);
      expect(poly0.vertices[0].lat).toBeCloseTo(47.1, 5);
      expect(poly0.vertices[3].lon).toBeCloseTo(8.4, 5);
    }

    const poly1 = decoded[1];
    expect(poly1.kind).toBe("polygon");
    expect(poly1.role).toBe("exclusion");
    if (poly1.kind === "polygon") expect(poly1.vertices).toHaveLength(3);

    const circle = decoded[2];
    expect(circle.kind).toBe("circle");
    if (circle.kind === "circle") {
      expect(circle.role).toBe("inclusion");
      expect(circle.radius).toBe(300);
      expect(circle.center.lat).toBeCloseTo(51.5, 5);
    }
  });

  it("ignores a return-point (5000) item and sorts by seq before grouping", () => {
    // Out-of-order items plus a return point that carries no modeled geometry.
    const items: FenceMissionItem[] = [
      { seq: 3, frame: 0, command: MAV_CMD_NAV_FENCE_CIRCLE_EXCLUSION, param1: 50, param2: 0, x: 60000000, y: 60000000, z: 0 },
      { seq: 0, frame: 0, command: MAV_CMD_NAV_FENCE_POLYGON_VERTEX_INCLUSION, param1: 3, param2: 0, x: 10000000, y: 10000000, z: 0 },
      { seq: 4, frame: 0, command: 5000, param1: 0, param2: 0, x: 12000000, y: 12000000, z: 100 },
      { seq: 1, frame: 0, command: MAV_CMD_NAV_FENCE_POLYGON_VERTEX_INCLUSION, param1: 3, param2: 0, x: 11000000, y: 11000000, z: 0 },
      { seq: 2, frame: 0, command: MAV_CMD_NAV_FENCE_POLYGON_VERTEX_INCLUSION, param1: 3, param2: 0, x: 12000000, y: 12000000, z: 0 },
    ];
    const decoded = decodeFenceMissionItems(items);

    expect(decoded).toHaveLength(2); // one polygon + one circle; the return point is skipped
    expect(decoded[0].kind).toBe("polygon");
    if (decoded[0].kind === "polygon") expect(decoded[0].vertices).toHaveLength(3);
    expect(decoded[1].kind).toBe("circle");
  });
});

describe("MISSION_ITEM_INT wire format with mission_type = fence", () => {
  it("appends the mission_type extension byte (= 1) so PX4 stores it as a fence", () => {
    const frame = encodeMissionItemInt(
      1, 1, // target sys/comp
      0, // seq
      0, // frame (MAV_FRAME_GLOBAL)
      MAV_CMD_NAV_FENCE_POLYGON_VERTEX_INCLUSION,
      0, // current
      1, // autocontinue
      3, // param1 = vertex count
      0, // param2 = inclusion group
      0, 0, // param3/param4 reserved
      Math.round(47.1 * 1e7), // x = lat * 1e7
      Math.round(8.1 * 1e7), // y = lon * 1e7
      0, // z reserved
      255, 190, // sender sys/comp
      MAV_MISSION_TYPE_FENCE,
    );

    // With mission_type the payload is 38 bytes; without it, 37.
    expect(frame[1]).toBe(38);

    const decoded = decodeMissionItemInt(payloadOf(frame));
    expect(decoded.missionType).toBe(MAV_MISSION_TYPE_FENCE);
    expect(decoded.command).toBe(MAV_CMD_NAV_FENCE_POLYGON_VERTEX_INCLUSION);
    expect(decoded.param1).toBeCloseTo(3, 5);
    expect(decoded.x).toBe(Math.round(47.1 * 1e7));
    expect(decoded.y).toBe(Math.round(8.1 * 1e7));
    expect(decoded.frame).toBe(0);
  });

  it("omits the extension byte for a plain waypoint mission (mission_type defaults to 0)", () => {
    const frame = encodeMissionItemInt(1, 1, 0, 3, 16, 0, 1, 0, 0, 0, 0, 471000000, 81000000, 50);
    expect(frame[1]).toBe(37); // no trailing mission_type byte
    expect(decodeMissionItemInt(payloadOf(frame)).missionType).toBe(0);
  });
});

describe("mock PX4 fence-mission round-trip (demo mode)", () => {
  it("exposes the mission-fence methods so the store's PX4 gate is not a no-op", () => {
    const px4 = new MockProtocol("px4");
    expect(px4.getVehicleInfo()?.firmwareType).toBe("px4");
    expect(typeof px4.uploadFenceMission).toBe("function");
    expect(typeof px4.downloadFenceMission).toBe("function");
  });

  it("round-trips uploaded fence elements through download", async () => {
    const px4 = new MockProtocol("px4");
    const elements: FenceElement[] = [
      {
        kind: "polygon",
        role: "inclusion",
        vertices: [
          { lat: 47.1, lon: 8.1 },
          { lat: 47.2, lon: 8.2 },
          { lat: 47.3, lon: 8.3 },
        ],
        group: 0,
      },
      { kind: "circle", role: "exclusion", center: { lat: 47.4, lon: 8.4 }, radius: 60 },
    ];
    const result = await px4.uploadFenceMission!(elements);
    expect(result.success).toBe(true);

    const back = await px4.downloadFenceMission!();
    expect(back).toHaveLength(2);
    expect(back[0].kind).toBe("polygon");
    expect(back[1].kind).toBe("circle");
    if (back[1].kind === "circle") expect(back[1].radius).toBe(60);
  });
});
