import { describe, it, expect, beforeEach } from "vitest";
import {
  useDroneCanRpcTraceStore,
  type RpcEvent,
} from "@/stores/dronecan/rpc-trace-store";
import { RingBuffer } from "@/lib/ring-buffer";

function makeEvent(over: Partial<RpcEvent> = {}): RpcEvent {
  return {
    t: Date.now(),
    kind: "request",
    direction: "out",
    dataTypeId: 11,
    dataTypeName: "uavcan.protocol.param.GetSet",
    srcNodeId: 127,
    dstNodeId: 10,
    ok: true,
    ...over,
  };
}

describe("useDroneCanRpcTraceStore", () => {
  beforeEach(() => {
    useDroneCanRpcTraceStore.setState({
      events: new RingBuffer<RpcEvent>(512),
      filters: {},
      _version: 0,
    });
  });

  it("pushEvent respects 512 cap", () => {
    const { pushEvent } = useDroneCanRpcTraceStore.getState();
    for (let i = 0; i < 700; i++) pushEvent(makeEvent());
    expect(useDroneCanRpcTraceStore.getState().events.length).toBe(512);
  });

  it("setFilters merges partial updates", () => {
    const { setFilters } = useDroneCanRpcTraceStore.getState();
    setFilters({ nodeId: 10 });
    setFilters({ type: "request" });
    setFilters({ errorsOnly: true });
    const f = useDroneCanRpcTraceStore.getState().filters;
    expect(f.nodeId).toBe(10);
    expect(f.type).toBe("request");
    expect(f.errorsOnly).toBe(true);
  });

  it("setFilters with undefined clears that field", () => {
    const { setFilters } = useDroneCanRpcTraceStore.getState();
    setFilters({ nodeId: 10, type: "response" });
    setFilters({ nodeId: undefined });
    const f = useDroneCanRpcTraceStore.getState().filters;
    expect(f.nodeId).toBeUndefined();
    expect(f.type).toBe("response");
  });

  it("clear() empties the buffer", () => {
    const { pushEvent, clear } = useDroneCanRpcTraceStore.getState();
    pushEvent(makeEvent());
    pushEvent(makeEvent());
    expect(useDroneCanRpcTraceStore.getState().events.length).toBe(2);
    clear();
    expect(useDroneCanRpcTraceStore.getState().events.length).toBe(0);
  });

  it("events keep latency and ok flags", () => {
    const { pushEvent } = useDroneCanRpcTraceStore.getState();
    pushEvent(makeEvent({ kind: "response", latencyMs: 12.5, ok: false }));
    const latest = useDroneCanRpcTraceStore.getState().events.latest();
    expect(latest?.latencyMs).toBe(12.5);
    expect(latest?.ok).toBe(false);
    expect(latest?.kind).toBe("response");
  });
});
