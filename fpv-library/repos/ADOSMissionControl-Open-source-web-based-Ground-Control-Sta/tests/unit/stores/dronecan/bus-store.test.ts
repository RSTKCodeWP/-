import { describe, it, expect, beforeEach, vi, afterEach } from "vitest";
import {
  useDroneCanBusStore,
  type DecodedFrame,
} from "@/stores/dronecan/bus-store";
import { RingBuffer } from "@/lib/ring-buffer";

function makeFrame(overrides: Partial<DecodedFrame> = {}): DecodedFrame {
  return {
    t: Date.now(),
    dir: "in",
    canId: 0x1abcdef0,
    decoded: {
      kind: "message",
      dataTypeId: 341,
      srcNodeId: 1,
    },
    payload: new Uint8Array(7),
    ...overrides,
  };
}

describe("useDroneCanBusStore", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date(2026, 0, 1, 12, 0, 0));
    useDroneCanBusStore.setState({
      frames: new RingBuffer<DecodedFrame>(4096),
      counters: { fps: 0, errorsPs: 0, bytesIn: 0, bytesOut: 0 },
      paused: false,
      _version: 0,
      _lastTallyAt: Date.now(),
      _framesSinceTally: 0,
      _errorsSinceTally: 0,
    });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("pushFrame respects 4096 cap", () => {
    const { pushFrame } = useDroneCanBusStore.getState();
    for (let i = 0; i < 5000; i++) pushFrame(makeFrame());
    expect(useDroneCanBusStore.getState().frames.length).toBe(4096);
  });

  it("pause() stops accepting new frames", () => {
    const store = useDroneCanBusStore.getState();
    store.pushFrame(makeFrame());
    store.pushFrame(makeFrame());
    expect(useDroneCanBusStore.getState().frames.length).toBe(2);

    useDroneCanBusStore.getState().pause();
    for (let i = 0; i < 10; i++) {
      useDroneCanBusStore.getState().pushFrame(makeFrame());
    }
    expect(useDroneCanBusStore.getState().frames.length).toBe(2);
  });

  it("resume() restarts frame intake and resets counters tally window", () => {
    const store = useDroneCanBusStore.getState();
    store.pause();
    store.pushFrame(makeFrame());
    expect(useDroneCanBusStore.getState().frames.length).toBe(0);

    useDroneCanBusStore.getState().resume();
    useDroneCanBusStore.getState().pushFrame(makeFrame());
    expect(useDroneCanBusStore.getState().frames.length).toBe(1);
  });

  it("counters accumulate bytes by direction", () => {
    const { pushFrame } = useDroneCanBusStore.getState();
    pushFrame(makeFrame({ dir: "in", payload: new Uint8Array(8) }));
    pushFrame(makeFrame({ dir: "out", payload: new Uint8Array(4) }));
    const counters = useDroneCanBusStore.getState().counters;
    expect(counters.bytesIn).toBe(8);
    expect(counters.bytesOut).toBe(4);
  });

  it("fps tallies on a 1s rolling window", () => {
    const { pushFrame } = useDroneCanBusStore.getState();
    for (let i = 0; i < 30; i++) pushFrame(makeFrame());
    expect(useDroneCanBusStore.getState().counters.fps).toBe(0);
    vi.advanceTimersByTime(1_001);
    pushFrame(makeFrame());
    expect(useDroneCanBusStore.getState().counters.fps).toBeGreaterThan(0);
  });

  it("clear() resets buffer and counters", () => {
    const { pushFrame } = useDroneCanBusStore.getState();
    pushFrame(makeFrame({ dir: "in", payload: new Uint8Array(8) }));
    useDroneCanBusStore.getState().clear();
    const after = useDroneCanBusStore.getState();
    expect(after.frames.length).toBe(0);
    expect(after.counters.bytesIn).toBe(0);
  });
});
