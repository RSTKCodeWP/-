import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import {
  useDroneCanNodeStore,
  type NodeStatus,
} from "@/stores/dronecan/node-store";

function freshStatus(uptime = 1): NodeStatus {
  return {
    uptime_sec: uptime,
    health: 0,
    mode: 0,
    vendor_specific_status_code: 0,
  };
}

describe("useDroneCanNodeStore", () => {
  beforeEach(() => {
    useDroneCanNodeStore.getState().clear();
    vi.useFakeTimers();
    vi.setSystemTime(new Date(2026, 0, 1, 12, 0, 0));
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("upsertStatus appends to history and updates lastStatus + lastSeen", () => {
    const store = useDroneCanNodeStore.getState();
    store.upsertStatus(7, freshStatus(1));
    store.upsertStatus(7, freshStatus(2));
    store.upsertStatus(7, freshStatus(3));
    const entry = useDroneCanNodeStore.getState().getNode(7);
    expect(entry).toBeDefined();
    expect(entry?.statusHistory).toHaveLength(3);
    expect(entry?.lastStatus?.uptime_sec).toBe(3);
    expect(entry?.lastSeen).toBe(Date.now());
  });

  it("statusHistory caps at 60 entries", () => {
    const store = useDroneCanNodeStore.getState();
    for (let i = 0; i < 75; i++) store.upsertStatus(9, freshStatus(i));
    const entry = useDroneCanNodeStore.getState().getNode(9);
    expect(entry?.statusHistory).toHaveLength(60);
    // Oldest 15 should have been dropped — first remaining uptime is 15.
    expect(entry?.statusHistory[0].uptime_sec).toBe(15);
    expect(entry?.statusHistory[59].uptime_sec).toBe(74);
  });

  it("clearStale removes entries older than 10s", () => {
    const store = useDroneCanNodeStore.getState();
    store.upsertStatus(1, freshStatus());
    store.upsertStatus(2, freshStatus());
    vi.advanceTimersByTime(11_000);
    store.upsertStatus(3, freshStatus());
    useDroneCanNodeStore.getState().clearStale();
    const ids = useDroneCanNodeStore.getState().getNodeIds();
    expect(ids).toEqual([3]);
  });

  it("isOnline uses a 3s window", () => {
    const store = useDroneCanNodeStore.getState();
    store.upsertStatus(5, freshStatus());
    expect(useDroneCanNodeStore.getState().isOnline(5)).toBe(true);
    vi.advanceTimersByTime(2_900);
    expect(useDroneCanNodeStore.getState().isOnline(5)).toBe(true);
    vi.advanceTimersByTime(200);
    expect(useDroneCanNodeStore.getState().isOnline(5)).toBe(false);
  });

  it("getOnlineCount only counts nodes seen in the last 3s", () => {
    const store = useDroneCanNodeStore.getState();
    store.upsertStatus(1, freshStatus());
    store.upsertStatus(2, freshStatus());
    vi.advanceTimersByTime(4_000);
    store.upsertStatus(3, freshStatus());
    expect(useDroneCanNodeStore.getState().getOnlineCount()).toBe(1);
  });

  it("setNodeInfo preserves existing status and history", () => {
    const store = useDroneCanNodeStore.getState();
    store.upsertStatus(11, freshStatus(42));
    store.setNodeInfo(11, {
      status: freshStatus(42),
      software_version: {
        major: 1,
        minor: 0,
        optional_field_flags: 0,
        vcs_commit: 0,
        image_crc: BigInt(0),
      },
      hardware_version: {
        major: 1,
        minor: 0,
        unique_id: new Uint8Array(16),
        certificate_of_authenticity: new Uint8Array(0),
      },
      name: "test.node",
    });
    const entry = useDroneCanNodeStore.getState().getNode(11);
    expect(entry?.lastStatus?.uptime_sec).toBe(42);
    expect(entry?.nodeInfo?.name).toBe("test.node");
    expect(entry?.statusHistory).toHaveLength(1);
  });

  it("clear() drops everything", () => {
    const store = useDroneCanNodeStore.getState();
    store.upsertStatus(1, freshStatus());
    store.upsertStatus(2, freshStatus());
    useDroneCanNodeStore.getState().clear();
    expect(useDroneCanNodeStore.getState().getNodeIds()).toEqual([]);
  });
});
