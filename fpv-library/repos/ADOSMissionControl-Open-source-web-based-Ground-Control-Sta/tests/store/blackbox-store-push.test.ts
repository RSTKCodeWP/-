/**
 * @module blackbox-store-push.test
 * @description Verifies the explicit cloud-push state machine on the Black Box
 * store: the push transitions, the reset on clear(), and the explicit-only
 * invariant — no filter / selection / refresh path may trigger a push.
 * @license GPL-3.0-only
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useBlackBoxStore } from "@/stores/blackbox-store";
import { useAgentConnectionStore } from "@/stores/agent-connection-store";
import type { PushResult } from "@/lib/agent/agent-client/logging";

const okResult: PushResult = {
  window_id: "win_99",
  sha256: "deadbeef",
  bytes: 2048,
  rows: 50,
  deduped: false,
  synced: true,
};

/** Install a minimal fake agent client whose `logging` exposes the methods
 * the store calls. Every read is a no-op so explicit-only can be asserted
 * (a push call would still go through pushWindow). */
function installFakeClient(pushImpl: () => Promise<PushResult>) {
  const pushWindow = vi.fn(pushImpl);
  const noop = vi.fn(async () => ({
    data: [],
    page: { next_cursor: null, count: 0 },
    meta: { source: "logd", v: 1, ts: "", db_lag_ms: 0 },
  }));
  const logging = {
    pushWindow,
    sessions: noop,
    query: noop,
    aggregate: noop,
    healthz: vi.fn(async () => ({
      ok: true,
      db_open: true,
      writer_alive: true,
      integrity: true,
      source: "logd",
    })),
    stats: vi.fn(async () => null),
  };
  useAgentConnectionStore.setState({
    client: { logging } as unknown as never,
  });
  return { pushWindow };
}

describe("blackbox-store push", () => {
  beforeEach(() => {
    useBlackBoxStore.getState().clear();
  });

  afterEach(() => {
    useAgentConnectionStore.setState({ client: null });
    vi.restoreAllMocks();
  });

  it("starts idle with no push result", () => {
    const s = useBlackBoxStore.getState();
    expect(s.pushState).toBe("idle");
    expect(s.lastPushResult).toBeNull();
    expect(s.pushError).toBeNull();
  });

  it("transitions idle -> done and records the ack on success", async () => {
    const { pushWindow } = installFakeClient(async () => okResult);
    const result = await useBlackBoxStore.getState().pushWindow();
    expect(result).toEqual(okResult);
    const s = useBlackBoxStore.getState();
    expect(s.pushState).toBe("done");
    expect(s.lastPushResult).toEqual(okResult);
    expect(s.pushError).toBeNull();
    // The store forwards the current selection + a zst format.
    expect(pushWindow).toHaveBeenCalledWith(
      expect.objectContaining({ format: "jsonl.zst" }),
    );
  });

  it("transitions to error and records the message on failure", async () => {
    installFakeClient(async () => {
      throw new Error("push failed 409");
    });
    const result = await useBlackBoxStore.getState().pushWindow();
    expect(result).toBeNull();
    const s = useBlackBoxStore.getState();
    expect(s.pushState).toBe("error");
    expect(s.pushError).toBe("push failed 409");
  });

  it("errors when no logging client is attached", async () => {
    useAgentConnectionStore.setState({ client: null });
    const result = await useBlackBoxStore.getState().pushWindow();
    expect(result).toBeNull();
    expect(useBlackBoxStore.getState().pushState).toBe("error");
  });

  it("resets push state on clear()", async () => {
    installFakeClient(async () => okResult);
    await useBlackBoxStore.getState().pushWindow();
    expect(useBlackBoxStore.getState().pushState).toBe("done");
    useBlackBoxStore.getState().clear();
    const s = useBlackBoxStore.getState();
    expect(s.pushState).toBe("idle");
    expect(s.lastPushResult).toBeNull();
    expect(s.pushError).toBeNull();
  });

  it("is explicit-only: setFilters, setSelectedSession, and refresh never push", async () => {
    const { pushWindow } = installFakeClient(async () => okResult);
    useBlackBoxStore.getState().setFilters({ level: "error" });
    useBlackBoxStore.getState().setSelectedSession("3");
    await useBlackBoxStore.getState().refresh();
    expect(pushWindow).not.toHaveBeenCalled();
  });
});
