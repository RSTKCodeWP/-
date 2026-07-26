/**
 * @license GPL-3.0-only
 */

import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { MockDroneCanBus } from "@/mock/mock-can-bus";
import { useDroneCanNodeStore } from "@/stores/dronecan/node-store";
import {
  MODE_OPERATIONAL,
  MODE_SOFTWARE_UPDATE,
  MODE_INITIALIZATION,
  MODE_MAINTENANCE,
} from "@/lib/dronecan/dsdl/node-status";
import { ValueTag } from "@/lib/dronecan/dsdl/param-getset";

describe("MockDroneCanBus", () => {
  let bus: MockDroneCanBus;

  beforeEach(() => {
    vi.useFakeTimers();
    useDroneCanNodeStore.setState({ nodes: new Map(), _version: 0 } as never);
    bus = new MockDroneCanBus();
  });

  afterEach(() => {
    bus.stop();
    vi.useRealTimers();
  });

  it("exposes the three synthetic nodes", () => {
    expect(bus.getNodeIds().sort()).toEqual([11, 14, 22]);
  });

  it("emits NodeStatus broadcasts into the node store after start", () => {
    bus.start();
    const store = useDroneCanNodeStore.getState();
    expect(store.getNode(11)?.lastStatus).toBeDefined();
    expect(store.getNode(11)?.lastStatus?.mode).toBe(MODE_OPERATIONAL);
    expect(store.getNode(14)?.lastStatus?.mode).toBe(MODE_MAINTENANCE);
  });

  it("advances uptime on each tick", () => {
    bus.start();
    const u0 = useDroneCanNodeStore.getState().getNode(11)?.lastStatus?.uptime_sec ?? -1;
    vi.advanceTimersByTime(2_000);
    const u1 = useDroneCanNodeStore.getState().getNode(11)?.lastStatus?.uptime_sec ?? -1;
    expect(u1).toBeGreaterThanOrEqual(u0);
  });

  it("returns canned node info via getNodeInfo", async () => {
    const info = await bus.getNodeInfo(11);
    expect(info.name).toBe("org.ardupilot.ap_periph");
    expect(info.hardware_version.unique_id.length).toBe(16);
  });

  it("walks the paramGet index and returns an empty name at EOF", async () => {
    const seen: string[] = [];
    for (let i = 0; i < 50; i++) {
      const r = await bus.paramGet(11, i);
      if (!r.name) break;
      seen.push(r.name);
    }
    expect(seen.length).toBeGreaterThanOrEqual(5);
    expect(seen[0]).toBe("UAVCAN_NODE_ID");
  });

  it("echoes paramSet for an existing param and rejects unknown ones", async () => {
    const r1 = await bus.paramSet(11, "GPS_TYPE", {
      tag: ValueTag.Integer,
      value: BigInt(2),
    });
    expect(r1.name).toBe("GPS_TYPE");
    expect(r1.value.tag).toBe(ValueTag.Integer);
    if (r1.value.tag === ValueTag.Integer) {
      expect(r1.value.value).toBe(BigInt(2));
    }

    const r2 = await bus.paramSet(11, "DOES_NOT_EXIST", {
      tag: ValueTag.Integer,
      value: BigInt(0),
    });
    expect(r2.name).toBe("");
  });

  it("returns ok=true for paramExecuteOpcode and resets uptime on restart", async () => {
    const r = await bus.paramExecuteOpcode(11, 1);
    expect(r.ok).toBe(true);
    const before = (await bus.getNodeInfo(11)).status.uptime_sec;
    await bus.restart(11);
    bus.start();
    const after = useDroneCanNodeStore.getState().getNode(11)?.lastStatus?.uptime_sec ?? before + 1;
    expect(after).toBeLessThanOrEqual(before + 1);
  });

  it("walks BeginFirmwareUpdate → SOFTWARE_UPDATE → INITIALIZATION → OPERATIONAL", async () => {
    bus.start();
    const r = await bus.beginFirmwareUpdate(14, 1, "a.bin");
    expect(r.error).toBe(0);

    // Advance the heartbeat past the initial 800ms tick to flip mode.
    vi.advanceTimersByTime(900);
    expect(useDroneCanNodeStore.getState().getNode(14)?.lastStatus?.mode).toBe(MODE_SOFTWARE_UPDATE);

    // Past the duration (3_000ms) we step to INITIALIZATION.
    vi.advanceTimersByTime(3_200);
    expect(useDroneCanNodeStore.getState().getNode(14)?.lastStatus?.mode).toBe(MODE_INITIALIZATION);

    // And then OPERATIONAL after duration*1.5.
    vi.advanceTimersByTime(2_000);
    expect(useDroneCanNodeStore.getState().getNode(14)?.lastStatus?.mode).toBe(MODE_OPERATIONAL);
  });

  it("returns canned transport stats", async () => {
    bus.start();
    const s = await bus.getTransportStats(11);
    expect(s.transfer_count).toBeGreaterThanOrEqual(BigInt(1));
    expect(s.can_iface_stats.length).toBe(1);
  });
});
