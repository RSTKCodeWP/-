import { describe, it, expect, beforeEach } from "vitest";
import {
  useDroneCanFlashStore,
  type OtaSnapshot,
} from "@/stores/dronecan/flash-store";

function snap(over: Partial<OtaSnapshot> = {}): OtaSnapshot {
  return {
    state: "IDLE",
    percent: 0,
    bytesSent: 0,
    bytesTotal: 0,
    lastOffset: 0,
    lastChunkLen: 0,
    retries: 0,
    timeouts: 0,
    transitionLog: [],
    rpcTrace: [],
    ...over,
  };
}

describe("useDroneCanFlashStore", () => {
  beforeEach(() => {
    useDroneCanFlashStore.getState().reset();
  });

  it("setSnapshot replaces flat fields", () => {
    useDroneCanFlashStore.getState().setSnapshot(
      snap({
        state: "TRANSFERRING",
        percent: 42,
        bytesSent: 4200,
        bytesTotal: 10_000,
        lastOffset: 4096,
        lastChunkLen: 256,
        retries: 1,
        timeouts: 0,
      }),
    );
    const s = useDroneCanFlashStore.getState();
    expect(s.state).toBe("TRANSFERRING");
    expect(s.percent).toBe(42);
    expect(s.bytesSent).toBe(4200);
    expect(s.bytesTotal).toBe(10_000);
    expect(s.lastOffset).toBe(4096);
    expect(s.lastChunkLen).toBe(256);
    expect(s.retries).toBe(1);
  });

  it("state transitions are logged", () => {
    const { setSnapshot } = useDroneCanFlashStore.getState();
    setSnapshot(snap({ state: "ARMING" }));
    setSnapshot(snap({ state: "BEGIN_SENT" }));
    setSnapshot(snap({ state: "TRANSFERRING" }));
    const log = useDroneCanFlashStore.getState().transitionLog;
    expect(log).toHaveLength(3);
    expect(log[0].from).toBe("IDLE");
    expect(log[0].to).toBe("ARMING");
    expect(log[2].to).toBe("TRANSFERRING");
  });

  it("setSnapshot with same state does not duplicate transitions", () => {
    const { setSnapshot } = useDroneCanFlashStore.getState();
    setSnapshot(snap({ state: "TRANSFERRING", percent: 10 }));
    setSnapshot(snap({ state: "TRANSFERRING", percent: 20 }));
    setSnapshot(snap({ state: "TRANSFERRING", percent: 30 }));
    expect(useDroneCanFlashStore.getState().transitionLog).toHaveLength(1);
    expect(useDroneCanFlashStore.getState().percent).toBe(30);
  });

  it("reset() returns to IDLE and zeros fields", () => {
    const { setSnapshot, reset } = useDroneCanFlashStore.getState();
    setSnapshot(
      snap({
        state: "FAILED",
        percent: 99,
        errorMessage: "verify failed",
        retries: 4,
      }),
    );
    reset();
    const s = useDroneCanFlashStore.getState();
    expect(s.state).toBe("IDLE");
    expect(s.percent).toBe(0);
    expect(s.retries).toBe(0);
    expect(s.errorMessage).toBeUndefined();
    expect(s.transitionLog).toEqual([]);
  });

  it("error messages ride along on the transition note", () => {
    useDroneCanFlashStore
      .getState()
      .setSnapshot(snap({ state: "FAILED", errorMessage: "timeout" }));
    const log = useDroneCanFlashStore.getState().transitionLog;
    expect(log[0].note).toBe("timeout");
  });
});
