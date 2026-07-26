import { describe, expect, it } from "vitest";

import { LatencyMeter } from "./latency";

/* Glass-to-glass latency instrument (impl-plan Task 5.11 / M3). Records per-frame stage
 * timings (socket-receive → decoded → painted) and reports the distribution against the
 * ≤120 ms in-app budget. Pure + deterministic (times are injected), so the measurement
 * harness can feed known values and the assertion is exact. */

describe("LatencyMeter", () => {
  it("records a frame's end-to-end latency from injected stage timestamps", () => {
    const m = new LatencyMeter();
    m.mark(1, "socket", 1000);
    m.mark(1, "decoded", 1010);
    m.mark(1, "painted", 1040);
    m.commit(1);
    expect(m.count).toBe(1);
    expect(m.samples[0].totalMs).toBe(40); // painted - socket
  });

  it("computes per-stage sub-budgets (decode vs paint) for a frame", () => {
    const m = new LatencyMeter();
    m.mark(2, "socket", 0);
    m.mark(2, "decoded", 12);
    m.mark(2, "painted", 30);
    m.commit(2);
    const s = m.samples[0];
    expect(s.decodeMs).toBe(12); // decoded - socket
    expect(s.paintMs).toBe(18); // painted - decoded
  });

  it("reports p50/p95/max over many frames", () => {
    const m = new LatencyMeter();
    for (let i = 0; i < 100; i++) {
      m.mark(i, "socket", 0);
      m.mark(i, "painted", i + 1); // totals 1..100 ms
      m.commit(i);
    }
    const r = m.report();
    expect(r.count).toBe(100);
    expect(r.p50Ms).toBeGreaterThanOrEqual(50);
    expect(r.p50Ms).toBeLessThanOrEqual(51);
    expect(r.p95Ms).toBeGreaterThanOrEqual(95);
    expect(r.maxMs).toBe(100);
  });

  it("withinBudget is true only when p95 clears the budget", () => {
    const m = new LatencyMeter();
    for (let i = 0; i < 10; i++) {
      m.mark(i, "socket", 0);
      m.mark(i, "painted", 50); // all 50ms
      m.commit(i);
    }
    expect(m.report().withinBudgetMs(120)).toBe(true);
    expect(m.report().withinBudgetMs(40)).toBe(false);
  });

  it("ignores an incomplete frame (no painted mark) — never a fabricated sample", () => {
    const m = new LatencyMeter();
    m.mark(5, "socket", 0);
    m.commit(5); // no painted mark
    expect(m.count).toBe(0);
  });

  it("caps retained samples (bounded memory over a long mission)", () => {
    const m = new LatencyMeter(50);
    for (let i = 0; i < 200; i++) {
      m.mark(i, "socket", 0);
      m.mark(i, "painted", 10);
      m.commit(i);
    }
    expect(m.count).toBeLessThanOrEqual(50);
  });
});
