import { describe, it, expect, beforeEach } from "vitest";
import { useMcpActivityStore } from "../mcp-activity-store";

beforeEach(() => {
  useMcpActivityStore.setState({ events: [], count: 0, channelState: "connecting", latestNav: null });
});

describe("mcp-activity-store", () => {
  it("ingests a completed event as a success row, bumps count, sets latestNav + live", () => {
    useMcpActivityStore.getState().ingest({
      tool: "params.set",
      args: { name: "X", value: 1 },
      node: "dev1",
      decision: "allowed",
      result: "ok",
      latencyMs: 10,
      tsUs: 1000,
    });
    const s = useMcpActivityStore.getState();
    expect(s.events).toHaveLength(1);
    expect(s.count).toBe(1);
    expect(s.channelState).toBe("live");
    expect(s.events[0].lifecycle).toBe("success");
    expect(s.events[0].summary).toBe("Set X → 1");
    expect(s.events[0].category).toBe("config");
    expect(s.latestNav?.tool).toBe("params.set");
  });

  it("treats a denied decision as an error row", () => {
    useMcpActivityStore.getState().ingest({ tool: "flight.arm", decision: "denied", node: "d", tsUs: 1 });
    expect(useMcpActivityStore.getState().events[0].lifecycle).toBe("error");
  });

  it("a running start does not drive latestNav; its completion merges in place by callId", () => {
    useMcpActivityStore
      .getState()
      .ingest({ tool: "mission.upload", phase: "started", callId: "c1", node: "d", tsUs: 1 });
    let s = useMcpActivityStore.getState();
    expect(s.events).toHaveLength(1);
    expect(s.events[0].lifecycle).toBe("running");
    expect(s.latestNav).toBeNull(); // a bare start never auto-navigates

    useMcpActivityStore
      .getState()
      .ingest({ tool: "mission.upload", callId: "c1", decision: "allowed", result: "ok", node: "d", tsUs: 2 });
    s = useMcpActivityStore.getState();
    expect(s.events).toHaveLength(1); // merged, not duplicated
    expect(s.events[0].lifecycle).toBe("success");
    expect(s.latestNav?.tool).toBe("mission.upload");
  });

  it("bounds the ring so a long session never grows without bound", () => {
    for (let i = 0; i < 520; i++) {
      useMcpActivityStore.getState().ingest({ tool: "status.get", node: "d", tsUs: i });
    }
    expect(useMcpActivityStore.getState().events.length).toBe(500);
    expect(useMcpActivityStore.getState().count).toBe(520);
  });
});
