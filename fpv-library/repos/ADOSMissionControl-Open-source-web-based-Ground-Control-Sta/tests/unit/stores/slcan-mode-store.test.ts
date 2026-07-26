import { describe, it, expect, beforeEach, vi, afterEach } from "vitest";
import {
  useSlcanModeStore,
  getCountdownLabel,
  type SlcanModeSnapshot,
} from "@/stores/slcan-mode-store";

function snapshot(): SlcanModeSnapshot {
  const s = useSlcanModeStore.getState();
  return {
    state: s.state,
    droneId: s.droneId,
    bus: s.bus,
    bitrate: s.bitrate,
    timeoutSec: s.timeoutSec,
    enteredAt: s.enteredAt,
    autoRevertAt: s.autoRevertAt,
    errorMessage: s.errorMessage,
    tickMs: s.tickMs,
    exitFn: s.exitFn,
  };
}

describe("useSlcanModeStore — transitions", () => {
  beforeEach(() => {
    useSlcanModeStore.getState().reset();
  });

  it("starts IDLE with null fields", () => {
    const s = snapshot();
    expect(s.state).toBe("IDLE");
    expect(s.droneId).toBeNull();
    expect(s.bus).toBeNull();
  });

  it("beginEntering transitions IDLE → ENTERING_SLCAN and captures args", () => {
    useSlcanModeStore.getState().beginEntering({
      droneId: "drone-1",
      bus: 1,
      bitrate: 1_000_000,
      timeoutSec: 300,
    });
    const s = snapshot();
    expect(s.state).toBe("ENTERING_SLCAN");
    expect(s.droneId).toBe("drone-1");
    expect(s.bus).toBe(1);
    expect(s.bitrate).toBe(1_000_000);
    expect(s.timeoutSec).toBe(300);
  });

  it("markActive transitions ENTERING_SLCAN → SLCAN_ACTIVE and sets deadlines", () => {
    const fixed = 1_700_000_000_000;
    vi.spyOn(Date, "now").mockReturnValue(fixed);
    useSlcanModeStore.getState().beginEntering({
      droneId: "d", bus: 1, bitrate: 1_000_000, timeoutSec: 60,
    });
    useSlcanModeStore.getState().markActive();
    const s = snapshot();
    expect(s.state).toBe("SLCAN_ACTIVE");
    expect(s.enteredAt).toBe(fixed);
    expect(s.autoRevertAt).toBe(fixed + 60_000);
  });

  it("beginExiting only transitions from SLCAN_ACTIVE", () => {
    useSlcanModeStore.getState().beginEntering({
      droneId: "d", bus: 1, bitrate: 1_000_000, timeoutSec: 60,
    });
    useSlcanModeStore.getState().beginExiting();
    // Should not transition from ENTERING_SLCAN.
    expect(snapshot().state).toBe("ENTERING_SLCAN");

    useSlcanModeStore.getState().markActive();
    useSlcanModeStore.getState().beginExiting();
    expect(snapshot().state).toBe("EXITING_SLCAN");
  });

  it("markReconnecting then reset return to IDLE", () => {
    useSlcanModeStore.getState().beginEntering({
      droneId: "d", bus: 2, bitrate: 500_000, timeoutSec: 30,
    });
    useSlcanModeStore.getState().markActive();
    useSlcanModeStore.getState().beginExiting();
    useSlcanModeStore.getState().markReconnecting();
    expect(snapshot().state).toBe("RECONNECTING_MAVLINK");
    useSlcanModeStore.getState().reset();
    expect(snapshot().state).toBe("IDLE");
    expect(snapshot().droneId).toBeNull();
  });

  it("markError captures message and moves to ERROR", () => {
    useSlcanModeStore.getState().beginEntering({
      droneId: "d", bus: 1, bitrate: 1_000_000, timeoutSec: 60,
    });
    useSlcanModeStore.getState().markError("BEL on open");
    expect(snapshot().state).toBe("ERROR");
    expect(snapshot().errorMessage).toBe("BEL on open");
  });
});

describe("useSlcanModeStore — single-flight", () => {
  beforeEach(() => {
    useSlcanModeStore.getState().reset();
  });

  it("rejects a second beginEntering while ENTERING_SLCAN", () => {
    useSlcanModeStore.getState().beginEntering({
      droneId: "d", bus: 1, bitrate: 1_000_000, timeoutSec: 60,
    });
    expect(() =>
      useSlcanModeStore.getState().beginEntering({
        droneId: "d2", bus: 2, bitrate: 500_000, timeoutSec: 30,
      }),
    ).toThrowError(/Cannot begin SLCAN entry/);
  });

  it("rejects a second beginEntering while SLCAN_ACTIVE", () => {
    useSlcanModeStore.getState().beginEntering({
      droneId: "d", bus: 1, bitrate: 1_000_000, timeoutSec: 60,
    });
    useSlcanModeStore.getState().markActive();
    expect(() =>
      useSlcanModeStore.getState().beginEntering({
        droneId: "d2", bus: 1, bitrate: 1_000_000, timeoutSec: 60,
      }),
    ).toThrow();
  });

  it("allows re-entry from ERROR after a prior failure", () => {
    useSlcanModeStore.getState().beginEntering({
      droneId: "d", bus: 1, bitrate: 1_000_000, timeoutSec: 60,
    });
    useSlcanModeStore.getState().markError("boom");
    expect(() =>
      useSlcanModeStore.getState().beginEntering({
        droneId: "d", bus: 1, bitrate: 1_000_000, timeoutSec: 60,
      }),
    ).not.toThrow();
    expect(snapshot().state).toBe("ENTERING_SLCAN");
  });
});

describe("useSlcanModeStore — exitFn registry", () => {
  beforeEach(() => {
    useSlcanModeStore.getState().reset();
  });

  it("stores the exitFn registered after markActive", () => {
    const fn = async () => {};
    useSlcanModeStore.getState().beginEntering({
      droneId: "d", bus: 1, bitrate: 1_000_000, timeoutSec: 60,
    });
    useSlcanModeStore.getState().markActive();
    useSlcanModeStore.getState().setExitFn(fn);
    expect(snapshot().exitFn).toBe(fn);
  });

  it("clears exitFn on beginExiting", () => {
    const fn = async () => {};
    useSlcanModeStore.getState().beginEntering({
      droneId: "d", bus: 1, bitrate: 1_000_000, timeoutSec: 60,
    });
    useSlcanModeStore.getState().markActive();
    useSlcanModeStore.getState().setExitFn(fn);
    useSlcanModeStore.getState().beginExiting();
    expect(snapshot().exitFn).toBeNull();
  });

  it("clears exitFn on reset", () => {
    const fn = async () => {};
    useSlcanModeStore.getState().beginEntering({
      droneId: "d", bus: 1, bitrate: 1_000_000, timeoutSec: 60,
    });
    useSlcanModeStore.getState().markActive();
    useSlcanModeStore.getState().setExitFn(fn);
    useSlcanModeStore.getState().reset();
    expect(snapshot().exitFn).toBeNull();
  });
});

describe("getCountdownLabel", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("returns null when not active", () => {
    useSlcanModeStore.getState().reset();
    expect(getCountdownLabel(snapshot())).toBeNull();
  });

  it("formats mm:ss countdown from deadline minus tickMs", () => {
    const base = 1_700_000_000_000;
    vi.spyOn(Date, "now").mockReturnValue(base);
    useSlcanModeStore.getState().reset();
    useSlcanModeStore.getState().beginEntering({
      droneId: "d", bus: 1, bitrate: 1_000_000, timeoutSec: 125,
    });
    useSlcanModeStore.getState().markActive();
    // Simulate the 1Hz ticker advancing 5 seconds.
    useSlcanModeStore.setState({ tickMs: base + 5_000 });
    // 125s - 5s = 120s = 02:00
    expect(getCountdownLabel(snapshot())).toBe("02:00");
  });

  it("clamps to 00:00 once deadline elapses", () => {
    const base = 1_700_000_000_000;
    vi.spyOn(Date, "now").mockReturnValue(base);
    useSlcanModeStore.getState().reset();
    useSlcanModeStore.getState().beginEntering({
      droneId: "d", bus: 1, bitrate: 1_000_000, timeoutSec: 1,
    });
    useSlcanModeStore.getState().markActive();
    useSlcanModeStore.setState({ tickMs: base + 60_000 });
    expect(getCountdownLabel(snapshot())).toBe("00:00");
  });
});
