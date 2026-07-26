import { beforeEach, describe, expect, it } from "vitest";

import { useSystemStore } from "./system";

describe("system-health store", () => {
  beforeEach(() => {
    useSystemStore.getState().reset();
  });

  it("defaults to link OK, fresh telemetry, no GPS fix yet", () => {
    const s = useSystemStore.getState();
    expect(s.linkUp).toBe(true);
    expect(s.telemetryAgeS).toBe(0);
    expect(s.gpsFix).toBe("none");
  });

  it("setLink(false) marks the link down", () => {
    useSystemStore.getState().setLink(false);
    expect(useSystemStore.getState().linkUp).toBe(false);
  });

  it("link severity is CRITICAL (not warning) when down — P0 rule: system failure = magenta", () => {
    useSystemStore.getState().setLink(false);
    expect(useSystemStore.getState().linkSeverity()).toBe("critical");
  });

  it("link severity is nominal when up", () => {
    expect(useSystemStore.getState().linkSeverity()).toBe("nominal");
  });

  it("telemetry severity escalates with age: nominal → caution → stale", () => {
    const s = useSystemStore.getState();
    s.setTelemetryAge(0.3);
    expect(useSystemStore.getState().telemetrySeverity()).toBe("nominal");
    useSystemStore.getState().setTelemetryAge(2.5);
    expect(useSystemStore.getState().telemetrySeverity()).toBe("caution");
    useSystemStore.getState().setTelemetryAge(6);
    expect(useSystemStore.getState().telemetrySeverity()).toBe("stale");
  });

  it("tracks GPS fix quality and satellite count", () => {
    useSystemStore.getState().setGps("3d", 11);
    const s = useSystemStore.getState();
    expect(s.gpsFix).toBe("3d");
    expect(s.gpsSats).toBe(11);
  });

  it("heartbeat is bound to frame arrival, not a clock (stops when frames stop)", () => {
    const s = useSystemStore.getState();
    expect(useSystemStore.getState().lastFrameId).toBeNull();
    s.markFrame(100);
    expect(useSystemStore.getState().lastFrameId).toBe(100);
  });
});
