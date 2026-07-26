/**
 * Verifies the agent-client fetch deadline helpers: a timeout signal is
 * always attached, a caller signal is honoured alongside it, and an
 * already-aborted caller short-circuits.
 *
 * @license GPL-3.0-only
 */

import { describe, it, expect } from "vitest";
import {
  withTimeoutSignal,
  AGENT_FETCH_TIMEOUT_MS,
} from "@/lib/agent/agent-client/timeout";

describe("withTimeoutSignal", () => {
  it("returns a live, non-aborted signal by default", () => {
    const sig = withTimeoutSignal();
    expect(sig).toBeInstanceOf(AbortSignal);
    expect(sig.aborted).toBe(false);
  });

  it("exposes a sensible default deadline", () => {
    expect(AGENT_FETCH_TIMEOUT_MS).toBeGreaterThan(3000);
    expect(AGENT_FETCH_TIMEOUT_MS).toBeLessThanOrEqual(15000);
  });

  it("returns the caller signal unchanged when it is already aborted", () => {
    const caller = AbortSignal.abort();
    const sig = withTimeoutSignal(5000, caller);
    expect(sig.aborted).toBe(true);
  });

  it("aborts the combined signal when the caller aborts", () => {
    const ctrl = new AbortController();
    const sig = withTimeoutSignal(60000, ctrl.signal);
    expect(sig.aborted).toBe(false);
    ctrl.abort();
    expect(sig.aborted).toBe(true);
  });
});
